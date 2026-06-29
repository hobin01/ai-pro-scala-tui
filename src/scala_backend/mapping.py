from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from uuid import UUID

from scala_backend.cache import MappingCache, MappingDecision, cache_key
from scala_backend.config import DEFAULT_OPENAI_MODEL
from scala_backend.connectors import SiemConnector
from scala_backend.errors import ProviderError
from scala_backend.models import AgentName, FieldSample, SourceSelection
from scala_backend.normalization import recommend_mapping
from scala_backend.ocsf import OcsfField
from scala_backend.providers import LlmProvider
from scala_backend.runtime import request
from scala_backend.store import BackendStore, make_usage
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
        candidates: list[OcsfField] = []
        if decision.action == "map" and self._ocsf_index is not None:
            candidates = self._ocsf_index.query(_candidate_query(field), top_k=3)
            decision = _candidate_decision(field, candidates, decision)
        decision = self._agent_decision(run_id, field, candidates, decision)
        if decision.action == "map" and field.name in {"clientip", "src_ip"}:
            feedback = _feedback(run_id, field, decision)
            while True:
                response = await request(peer, "feedback.request", feedback)
                if response.get("decision") == "keep_raw":
                    return (
                        MappingDecision(field.name, field.type, "keep_raw", None, None),
                        True,
                    )
                if response.get("decision") != "comment":
                    return decision, True
                comment = response.get("comment")
                comment_text = comment if isinstance(comment, str) else None
                if comment_text is not None:
                    lowered = comment_text.lower()
                    if any(
                        phrase in lowered
                        for phrase in (
                            "keep_raw",
                            "keep raw",
                            "custom_attr",
                            "unmapped",
                            "do not map",
                            "don't map",
                        )
                    ):
                        decision = MappingDecision(
                            field.name, field.type, "keep_raw", None, None
                        )
                feedback = _feedback(
                    run_id,
                    field,
                    decision,
                    comment_text,
                )
        return decision, False

    def _agent_decision(
        self,
        run_id: UUID,
        field: FieldSample,
        candidates: list[OcsfField],
        fallback: MappingDecision,
    ) -> MappingDecision:
        if self._llm_provider is None:
            return fallback
        settings = self._store.get_settings()
        model = _agent_model(settings, AgentName.NORMALIZATION)
        prompt = _agent_prompt(
            settings,
            AgentName.NORMALIZATION,
            _mapping_prompt(field, candidates, fallback),
        )
        response = self._llm_provider.complete(prompt, model, None)
        usage = response.usage
        self._store.add_usage(
            make_usage(
                run_id,
                AgentName.NORMALIZATION,
                f"mapped field {field.name}",
                model,
                usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            ),
        )
        return _parse_agent_decision(field, response.text)

    def _fields_from_source(self, source: SourceSelection) -> list[FieldSample]:
        return self._connectors[source.solution].fetch_schema_samples(source.index)


def _feedback(
    run_id: UUID,
    field: FieldSample,
    decision: MappingDecision,
    comment: str | None = None,
) -> dict[str, object]:
    why = "name and value look like a source IP"
    if comment is not None:
        why = f"{why} (updated); user comment: {comment}"
    if decision.action == "keep_raw":
        why = "user comment requested raw preservation (updated)"
        if comment is not None:
            why = f"{why}: {comment}"
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
            "why": why,
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
    if top.name in {
        "src_endpoint.ip",
        "dst_endpoint.port",
        "activity_name",
        "raw_data",
        "time",
    }:
        return MappingDecision(
            source_field=field.name,
            source_type=field.type,
            action="map",
            ocsf_field=top.name,
            ocsf_type=top.type_name,
        )
    return fallback


def _agent_model(settings: dict[str, object], agent: AgentName) -> str:
    value = settings.get(f"agent.{agent.value}.model")
    return value if isinstance(value, str) else DEFAULT_OPENAI_MODEL


def _agent_prompt(
    settings: dict[str, object],
    agent: AgentName,
    task_prompt: str,
) -> str:
    system_prompt = settings.get(f"agent.{agent.value}.system_prompt")
    if not isinstance(system_prompt, str):
        system_prompt = f"You are the SCALA {agent.value} agent."
    return f"{system_prompt}\n\n{task_prompt}"


def _mapping_prompt(
    field: FieldSample,
    candidates: list[OcsfField],
    fallback: MappingDecision,
) -> str:
    candidate_payload = [
        {
            "name": candidate.name,
            "type": candidate.type_name,
            "caption": candidate.caption,
        }
        for candidate in candidates[:5]
    ]
    payload = {
        "task": "Choose the best OCSF mapping for one source field.",
        "source_field": {
            "name": field.name,
            "type": field.type,
            "samples": field.samples,
        },
        "ocsf_candidates": candidate_payload,
        "fallback": asdict(fallback),
        "rules": [
            "Return JSON only.",
            "Use action=map only when the OCSF field is semantically correct.",
            "Use action=keep_raw for vendor-specific or ambiguous fields.",
            "Never drop data.",
        ],
        "response_schema": {
            "action": "map | keep_raw",
            "ocsf_field": "string or null",
            "ocsf_type": "string or null",
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _parse_agent_decision(
    field: FieldSample,
    text: str,
) -> MappingDecision:
    try:
        payload = json.loads(_extract_json(text))
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "Normalization agent returned invalid mapping JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderError("Normalization agent returned invalid mapping JSON")
    action = payload.get("action")
    if action == "keep_raw":
        return MappingDecision(field.name, field.type, "keep_raw", None, None)
    if action != "map":
        raise ProviderError("Normalization agent returned invalid mapping action")
    ocsf_field = payload.get("ocsf_field")
    ocsf_type = payload.get("ocsf_type")
    if not isinstance(ocsf_field, str) or not ocsf_field:
        raise ProviderError("Normalization agent returned invalid OCSF field")
    if ocsf_type is not None and not isinstance(ocsf_type, str):
        raise ProviderError("Normalization agent returned invalid OCSF type")
    return MappingDecision(field.name, field.type, "map", ocsf_field, ocsf_type)


def _extract_json(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end >= start:
        return value[start : end + 1]
    return value
