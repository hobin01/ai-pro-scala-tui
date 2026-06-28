from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from scala_backend.cache import MappingCache, MappingDecision, cache_key
from scala_backend.connectors import SiemConnector
from scala_backend.models import FieldSample, SourceSelection
from scala_backend.normalization import recommend_mapping
from scala_backend.ocsf import OcsfField
from scala_backend.runtime import request
from scala_backend.store import BackendStore
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


@dataclass(frozen=True)
class CacheWrite:
    key: str
    decision: MappingDecision


@dataclass(frozen=True)
class MappingResult:
    decisions: list[MappingDecision]
    cache_hit_count: int
    cache_miss_count: int
    cache_writes: list[CacheWrite]
    feedback_requested: bool

    @property
    def cached_count(self) -> int:
        return self.cache_hit_count


class MappingDecider:
    def __init__(
        self,
        store: BackendStore,
        connectors: dict[str, SiemConnector],
        cache: MappingCache,
        ocsf_index: ChromaOcsfIndex | None = None,
    ) -> None:
        self._store = store
        self._connectors = connectors
        self._cache = cache
        self._ocsf_index = ocsf_index

    async def decide(
        self,
        run_id: UUID,
        sources: list[SourceSelection],
        peer: object,
    ) -> MappingResult:
        decisions: list[MappingDecision] = []
        cache_hit_count = 0
        cache_miss_count = 0
        cache_writes: list[CacheWrite] = []
        feedback_requested = False
        settings = self._store.get_settings()
        for source in sources:
            source_url = _source_url(settings, source.solution)
            for field in self._fields_from_source(source):
                key = cache_key(source_url, source.index, field.name, field.type)
                cached = self._cache.get(key)
                if cached is not None:
                    cache_hit_count += 1
                    decisions.append(cached)
                    continue
                decision, requested = await self._decide_uncached(run_id, field, peer)
                feedback_requested = feedback_requested or requested
                cache_miss_count += 1
                cache_writes.append(CacheWrite(key, decision))
                decisions.append(decision)
        return MappingResult(
            decisions,
            cache_hit_count,
            cache_miss_count,
            cache_writes,
            feedback_requested,
        )

    async def _decide_uncached(
        self,
        run_id: UUID,
        field: FieldSample,
        peer: object,
    ) -> tuple[MappingDecision, bool]:
        decision = recommend_mapping(field)
        if decision.action == "map" and self._ocsf_index is not None:
            candidates = self._ocsf_index.query(_candidate_query(field), top_k=3)
            decision = _candidate_decision(field, candidates, decision)
        if decision.action == "map" and field.name in {"clientip", "src_ip"}:
            response = await request(
                peer,
                "feedback.request",
                _feedback(run_id, field, decision),
            )
            if response.get("decision") == "keep_raw":
                return (
                    MappingDecision(field.name, field.type, "keep_raw", None, None),
                    True,
                )
            return decision, True
        return decision, False

    def _fields_from_source(self, source: SourceSelection) -> list[FieldSample]:
        return self._connectors[source.solution].fetch_schema_samples(source.index)

def _feedback(
    run_id: UUID,
    field: FieldSample,
    decision: MappingDecision,
) -> dict[str, object]:
    return {
        "run_id": str(run_id),
        "field": {
            "source_field": field.name,
            "type": field.type,
            "samples": field.samples,
        },
        "recommendation": {
            "ocsf_field": decision.ocsf_field,
            "ocsf_type": decision.ocsf_type,
            "action": decision.action,
            "why": "name and value look like a source IP",
        },
        "options": ["approve", "keep_raw", "comment"],
    }


def _source_url(settings: dict[str, object], solution: str) -> str:
    value = settings.get(f"source.{solution}.url")
    return value if isinstance(value, str) else solution


def _candidate_query(field: FieldSample) -> str:
    samples = " ".join(str(sample) for sample in field.samples[:3])
    return f"{field.name} {field.type} {samples}"


def _candidate_decision(
    field: FieldSample,
    candidates: list[OcsfField],
    fallback: MappingDecision,
) -> MappingDecision:
    if not candidates:
        return fallback
    top = candidates[0]
    if top.name in {"src_endpoint.ip", "dst_endpoint.port", "activity_name"}:
        return MappingDecision(
            source_field=field.name,
            source_type=field.type,
            action="map",
            ocsf_field=top.name,
            ocsf_type=top.type_name,
        )
    return fallback
