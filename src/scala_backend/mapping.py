from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from scala_backend.cache import MappingCache, MappingDecision, cache_key
from scala_backend.connectors import SiemConnector
from scala_backend.models import AgentName, FieldSample, SourceSelection
from scala_backend.normalization import recommend_mapping
from scala_backend.ocsf import OcsfField
from scala_backend.providers import LlmProvider
from scala_backend.runtime import request
from scala_backend.store import BackendStore, make_usage
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


@dataclass(frozen=True)
class MappingResult:
    decisions: list[MappingDecision]
    cached_count: int
    feedback_requested: bool


class MappingDecider:
    def __init__(
        self,
        store: BackendStore,
        connectors: dict[str, SiemConnector],
        cache: MappingCache,
        ocsf_index: ChromaOcsfIndex | None = None,
        llm_provider: LlmProvider | None = None,
    ) -> None:
        self._store = store
        self._connectors = connectors
        self._cache = cache
        self._ocsf_index = ocsf_index
        self._llm_provider = llm_provider

    async def decide(
        self,
        run_id: UUID,
        sources: list[SourceSelection],
        peer: object,
    ) -> MappingResult:
        decisions: list[MappingDecision] = []
        cached_count = 0
        feedback_requested = False
        settings = self._store.get_settings()
        for source in sources:
            source_url = _source_url(settings, source.solution)
            for field in self._fields_from_source(source):
                key = cache_key(source_url, source.index, field.name, field.type)
                cached = self._cache.get(key)
                if cached is not None:
                    cached_count += 1
                    decisions.append(cached)
                    continue
                decision, requested = await self._decide_uncached(
                    run_id, field, settings, peer
                )
                feedback_requested = feedback_requested or requested
                self._cache.set(key, decision)
                decisions.append(decision)
        return MappingResult(decisions, cached_count, feedback_requested)

    async def _decide_uncached(
        self,
        run_id: UUID,
        field: FieldSample,
        settings: dict[str, object],
        peer: object,
    ) -> tuple[MappingDecision, bool]:
        decision = recommend_mapping(field)
        if decision.action == "map" and self._ocsf_index is not None:
            candidates = self._ocsf_index.query(_candidate_query(field), top_k=3)
            decision = _candidate_decision(field, candidates, decision)
        if decision.action == "map":
            self._record_llm_usage(run_id, field, settings)
        if decision.action == "map" and field.name in {"clientip", "src_ip"}:
            response = await request(
                peer,
                "feedback.request",
                _feedback(run_id, field, decision),
            )
            if response.get("decision") == "keep_raw":
                return (
                    recommend_mapping(FieldSample(name="unknown", type=field.type)),
                    True,
                )
            return decision, True
        return decision, False

    def _fields_from_source(self, source: SourceSelection) -> list[FieldSample]:
        return self._connectors[source.solution].fetch_schema_samples(source.index)

    def _record_llm_usage(
        self,
        run_id: UUID,
        field: FieldSample,
        settings: dict[str, object],
    ) -> int:
        if self._llm_provider is None:
            return 0
        model = _model(settings, "schema_profiler")
        price = _price(settings, model)
        response = self._llm_provider.complete(_candidate_query(field), model, price)
        usage = response.usage
        self._store.add_usage(
            make_usage(
                run_id,
                AgentName.SCHEMA_PROFILER,
                f"profiled {field.name}",
                model,
                usage.total_tokens,
                usage.cost_usd,
            ),
        )
        return usage.total_tokens


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


def _model(settings: dict[str, object], agent: str) -> str:
    value = settings.get(f"agent.{agent}.model")
    return value if isinstance(value, str) else "gpt-5-mini"


def _price(settings: dict[str, object], model: str) -> dict[str, float] | None:
    value = settings.get(f"model.{model}.price")
    if not isinstance(value, dict):
        return None
    prompt = value.get("prompt_per_1k")
    completion = value.get("completion_per_1k")
    if not isinstance(prompt, int | float) or not isinstance(completion, int | float):
        return None
    return {"prompt_per_1k": float(prompt), "completion_per_1k": float(completion)}
