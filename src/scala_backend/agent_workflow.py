from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, NotRequired, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from scala_backend.cache import MappingCache, MappingDecision, cache_key
from scala_backend.connectors import SiemConnector
from scala_backend.errors import ProviderError
from scala_backend.ids import stable_opensearch_id
from scala_backend.mapping import CacheWrite
from scala_backend.models import (
    AgentName,
    FieldSample,
    JsonObject,
    LineageRecord,
    RawDocument,
    SourceSelection,
)
from scala_backend.normalization import apply_mapping
from scala_backend.ocsf import OcsfField
from scala_backend.output.opensearch import OpenSearchLoader
from scala_backend.providers import LlmProvider, ProviderUsage
from scala_backend.runtime import request
from scala_backend.store import BackendStore, make_usage
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


def _merge_sequence(left: list[Any], right: list[Any]) -> list[Any]:
    return [*left, *right]


@dataclass(frozen=True)
class FieldWorkItem:
    source_url: str
    source: SourceSelection
    field: FieldSample
    key: str
    candidates: tuple[OcsfField, ...] = ()


@dataclass(frozen=True)
class NormalizedRecord:
    raw: RawDocument
    document: JsonObject
    opensearch_id: str


@dataclass(frozen=True)
class AgentWorkflowResult:
    decisions: list[MappingDecision]
    cache_hit_count: int
    cache_miss_count: int
    feedback_requested: bool
    loaded: int
    cached: int
    mapped: int
    kept_raw: int
    lineage_refs: list[dict[str, str]]


@dataclass
class UsageTotals:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Decimal = Decimal("0")

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, usage: ProviderUsage) -> None:
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.cost_usd += usage.cost_usd


class AgentWorkflowState(TypedDict):
    run_id: str
    stages: Annotated[list[str], _merge_sequence]
    nodes: Annotated[list[str], _merge_sequence]
    sources: list[SourceSelection]
    documents: NotRequired[list[RawDocument]]
    field_items: NotRequired[list[FieldWorkItem]]
    miss_items: NotRequired[list[FieldWorkItem]]
    cached_decisions: Annotated[list[MappingDecision], _merge_sequence]
    normalization_decisions: Annotated[list[MappingDecision], _merge_sequence]
    feedback_decisions: NotRequired[list[MappingDecision]]
    cache_writes: Annotated[list[CacheWrite], _merge_sequence]
    cache_hit: NotRequired[bool]
    cache_miss: NotRequired[bool]
    needs_feedback: NotRequired[bool]
    feedback_requested: NotRequired[bool]
    feedback_payload: NotRequired[JsonObject]
    normalized_records: NotRequired[list[NormalizedRecord]]
    loaded_records: NotRequired[list[NormalizedRecord]]
    decisions: NotRequired[list[MappingDecision]]
    loaded: NotRequired[int]
    cached: NotRequired[int]
    mapped: NotRequired[int]
    kept_raw: NotRequired[int]
    lineage_refs: NotRequired[list[dict[str, str]]]


class AgentWorkflowRunner:
    def __init__(
        self,
        store: BackendStore,
        connectors: dict[str, SiemConnector],
        cache: MappingCache,
        opensearch: OpenSearchLoader | None,
        ocsf_index: ChromaOcsfIndex | None,
        llm_provider: LlmProvider | None,
    ) -> None:
        self._store = store
        self._connectors = connectors
        self._cache = cache
        self._opensearch = opensearch
        self._ocsf_index = ocsf_index
        self._llm_provider = llm_provider

    async def run(
        self,
        run_id: UUID,
        sources: list[SourceSelection],
        peer: object,
    ) -> AgentWorkflowResult:
        if self._llm_provider is None:
            raise ProviderError("OpenAI API key is not configured")
        graph = self._build_graph(peer)
        result = await graph.ainvoke(
            {
                "run_id": str(run_id),
                "stages": [],
                "nodes": [],
                "sources": sources,
                "cached_decisions": [],
                "normalization_decisions": [],
                "cache_writes": [],
            },
        )
        decisions = list(result.get("decisions", []))
        return AgentWorkflowResult(
            decisions=decisions,
            cache_hit_count=len(result.get("cached_decisions", [])),
            cache_miss_count=len(result.get("miss_items", [])),
            feedback_requested=bool(result.get("feedback_requested", False)),
            loaded=int(result.get("loaded", 0)),
            cached=int(result.get("cached", 0)),
            mapped=int(result.get("mapped", 0)),
            kept_raw=int(result.get("kept_raw", 0)),
            lineage_refs=list(result.get("lineage_refs", [])),
        )

    def _build_graph(self, peer: object) -> Any:
        builder = StateGraph(AgentWorkflowState)
        custom_nodes = {
            "siem_connector",
            "orchestrator_request",
            "schema_profiler",
            "redis_cache",
            "cache_hit_mapping",
            "chromadb_ocsf",
            "normalization_rules",
            "validator_check",
            "orchestrator_feedback_request",
            "user_feedback",
            "orchestrator_feedback_result",
            "validator_final",
            "normalization_final",
            "load",
            "caching",
            "lineage",
            "orchestrator_result",
        }
        for node, stage in _runtime_nodes():
            if node not in custom_nodes:
                builder.add_node(node, self._stage_node(node, stage))
        builder.add_node("siem_connector", cast("Any", self._siem_connector))
        builder.add_node(
            "orchestrator_request", cast("Any", self._orchestrator_request)
        )
        builder.add_node("schema_profiler", cast("Any", self._schema_profiler))
        builder.add_node("redis_cache", cast("Any", self._redis_cache))
        builder.add_node("cache_hit_mapping", cast("Any", self._cache_hit_mapping))
        builder.add_node("chromadb_ocsf", cast("Any", self._chromadb_ocsf))
        builder.add_node("normalization_rules", cast("Any", self._normalization_rules))
        builder.add_node("validator_check", cast("Any", self._validator_check))
        builder.add_node(
            "orchestrator_feedback_request",
            cast("Any", self._orchestrator_feedback_request),
        )
        builder.add_node("user_feedback", self._user_feedback(peer))
        builder.add_node(
            "orchestrator_feedback_result",
            cast("Any", self._orchestrator_feedback_result),
        )
        builder.add_node("validator_final", cast("Any", self._validator_final))
        builder.add_node("normalization_final", cast("Any", self._normalization_final))
        builder.add_node("load", cast("Any", self._load))
        builder.add_node("caching", cast("Any", self._caching))
        builder.add_node("lineage", cast("Any", self._lineage))
        builder.add_node("orchestrator_result", cast("Any", self._orchestrator_result))
        _wire_prd_edges(builder)
        return builder.compile()

    def _stage_node(self, node_name: str, stage: str | None) -> Any:
        def node(_state: AgentWorkflowState) -> dict[str, list[str]]:
            update = {"nodes": [node_name]}
            if stage is not None:
                update["stages"] = [stage]
            return update

        return node

    def _siem_connector(self, state: AgentWorkflowState) -> dict[str, object]:
        docs: list[RawDocument] = []
        for source in state["sources"]:
            docs.extend(
                list(self._connectors[source.solution].iter_documents(source.index))
            )
        return {"nodes": ["siem_connector"], "documents": docs}

    def _orchestrator_request(self, state: AgentWorkflowState) -> dict[str, list[str]]:
        docs = state.get("documents", [])
        self._complete_agent(
            UUID(state["run_id"]),
            AgentName.ORCHESTRATOR,
            _orchestrator_start_prompt(state["sources"], docs),
            f"accepted {len(docs)} source documents",
        )
        return {"nodes": ["orchestrator_request"], "stages": ["orchestrator"]}

    def _schema_profiler(self, state: AgentWorkflowState) -> dict[str, object]:
        settings = self._store.get_settings()
        items: list[FieldWorkItem] = []
        for source in state["sources"]:
            source_url = _source_url(settings, source.solution)
            for field in self._connectors[source.solution].fetch_schema_samples(
                source.index
            ):
                key = cache_key(source_url, source.index, field.name, field.type)
                items.append(FieldWorkItem(source_url, source, field, key))
        self._complete_agent(
            UUID(state["run_id"]),
            AgentName.SCHEMA_PROFILER,
            _schema_profile_prompt(items),
            f"profiled {len(items)} source fields",
        )
        return {
            "nodes": ["schema_profiler"],
            "stages": ["schema_profiler"],
            "field_items": items,
        }

    def _redis_cache(self, state: AgentWorkflowState) -> dict[str, object]:
        cached: list[MappingDecision] = []
        misses: list[FieldWorkItem] = []
        for item in state.get("field_items", []):
            decision = self._cache.get(item.key)
            if decision is None:
                misses.append(item)
            else:
                cached.append(decision)
        return {
            "nodes": ["redis_cache"],
            "cached_decisions": cached,
            "miss_items": misses,
            "cache_hit": len(cached) > 0,
            "cache_miss": len(misses) > 0,
        }

    def _cache_hit_mapping(self, _state: AgentWorkflowState) -> dict[str, list[str]]:
        return {"nodes": ["cache_hit_mapping"]}

    def _chromadb_ocsf(self, state: AgentWorkflowState) -> dict[str, object]:
        enriched: list[FieldWorkItem] = []
        for item in state.get("miss_items", []):
            candidates: tuple[OcsfField, ...] = ()
            if self._ocsf_index is not None:
                candidates = tuple(
                    self._ocsf_index.query(_candidate_query(item.field), top_k=5)
                )
            enriched.append(
                FieldWorkItem(
                    item.source_url,
                    item.source,
                    item.field,
                    item.key,
                    candidates,
                ),
            )
        return {"nodes": ["chromadb_ocsf"], "miss_items": enriched}

    def _normalization_rules(self, state: AgentWorkflowState) -> dict[str, object]:
        totals = UsageTotals()
        decisions: list[MappingDecision] = []
        writes: list[CacheWrite] = []
        settings = self._store.get_settings()
        model = _agent_model(settings, AgentName.NORMALIZATION)
        price = _model_price(settings, model)
        assert self._llm_provider is not None
        miss_items = state.get("miss_items", [])
        if miss_items:
            prompt = _agent_prompt(
                settings,
                AgentName.NORMALIZATION,
                _normalization_batch_prompt(miss_items),
            )
            response = self._llm_provider.complete(prompt, model, price)
            totals.add(response.usage)
            decisions = _parse_mapping_decisions(miss_items, response.text)
            writes = [
                CacheWrite(item.key, decision)
                for item, decision in zip(miss_items, decisions, strict=True)
            ]
        self._record_usage(
            UUID(state["run_id"]),
            AgentName.NORMALIZATION,
            f"generated {len(decisions)} mapping rules",
            model,
            totals,
        )
        return {
            "nodes": ["normalization_rules"],
            "stages": ["normalization"],
            "normalization_decisions": decisions,
            "cache_writes": writes,
        }

    def _validator_check(self, state: AgentWorkflowState) -> dict[str, object]:
        decisions = list(state.get("normalization_decisions", []))
        text = self._complete_agent(
            UUID(state["run_id"]),
            AgentName.VALIDATOR,
            _validator_prompt(decisions),
            f"validated {len(decisions)} mapping rules",
        )
        feedback = _parse_validator_feedback(text, decisions)
        if feedback is not None:
            feedback["run_id"] = state["run_id"]
        return {
            "nodes": ["validator_check"],
            "stages": ["validator"],
            "needs_feedback": feedback is not None,
            "feedback_payload": feedback or {},
            "feedback_requested": feedback is not None,
        }

    def _orchestrator_feedback_request(
        self,
        state: AgentWorkflowState,
    ) -> dict[str, list[str]]:
        self._complete_agent(
            UUID(state["run_id"]),
            AgentName.ORCHESTRATOR,
            _feedback_prompt(state.get("feedback_payload", {})),
            "requested human feedback",
        )
        return {"nodes": ["orchestrator_feedback_request"], "stages": ["orchestrator"]}

    def _user_feedback(self, peer: object) -> Any:
        async def node(state: AgentWorkflowState) -> dict[str, object]:
            response = await request(
                peer, "feedback.request", state.get("feedback_payload", {})
            )
            return {"nodes": ["user_feedback"], "feedback_payload": response}

        return node

    def _orchestrator_feedback_result(
        self,
        state: AgentWorkflowState,
    ) -> dict[str, object]:
        decisions = _apply_feedback(
            state.get("normalization_decisions", []),
            state.get("feedback_payload", {}),
        )
        self._complete_agent(
            UUID(state["run_id"]),
            AgentName.ORCHESTRATOR,
            json.dumps({"feedback": state.get("feedback_payload", {})}, sort_keys=True),
            "applied human feedback",
        )
        return {
            "nodes": ["orchestrator_feedback_result"],
            "stages": ["orchestrator"],
            "feedback_decisions": decisions,
        }

    def _validator_final(self, state: AgentWorkflowState) -> dict[str, object]:
        decisions = state.get(
            "feedback_decisions", state.get("normalization_decisions", [])
        )
        self._complete_agent(
            UUID(state["run_id"]),
            AgentName.VALIDATOR,
            _validator_prompt(decisions),
            f"final validated {len(decisions)} mapping rules",
        )
        return {"nodes": ["validator_final"], "stages": ["validator"]}

    def _normalization_final(self, state: AgentWorkflowState) -> dict[str, object]:
        miss_decisions = state.get(
            "feedback_decisions", state.get("normalization_decisions", [])
        )
        decisions = [*state.get("cached_decisions", []), *miss_decisions]
        normalized_records: list[NormalizedRecord] = []
        for doc in state.get("documents", []):
            normalized = apply_mapping(doc.body, decisions)
            normalized_records.append(
                NormalizedRecord(doc, normalized, stable_opensearch_id(doc)),
            )
        mapped = sum(1 for decision in decisions if decision.action == "map")
        kept_raw = sum(1 for decision in decisions if decision.action == "keep_raw")
        return {
            "nodes": ["normalization_final"],
            "stages": ["normalization"],
            "decisions": decisions,
            "normalized_records": normalized_records,
            "mapped": mapped,
            "kept_raw": kept_raw,
        }

    def _load(self, state: AgentWorkflowState) -> dict[str, object]:
        settings = self._store.get_settings()
        index = _opensearch_index(settings)
        loaded_records: list[NormalizedRecord] = []
        for record in state.get("normalized_records", []):
            doc_id = record.opensearch_id
            if self._opensearch is not None:
                doc_id = self._opensearch.index_normalized(
                    index, doc_id, record.document
                )
            loaded_records.append(NormalizedRecord(record.raw, record.document, doc_id))
        self._store.add_usage(
            make_usage(
                UUID(state["run_id"]),
                AgentName.LOAD,
                f"loaded {len(loaded_records)} docs",
            ),
        )
        return {
            "nodes": ["load"],
            "stages": ["load"],
            "loaded_records": loaded_records,
            "loaded": len(loaded_records),
        }

    def _caching(self, state: AgentWorkflowState) -> dict[str, object]:
        writes = state.get("cache_writes", [])
        for write in writes:
            self._cache.set(write.key, write.decision)
        self._store.add_usage(
            make_usage(
                UUID(state["run_id"]),
                AgentName.CACHING,
                f"cached {len(writes)} mappings",
            ),
        )
        return {"nodes": ["caching"], "stages": ["caching"], "cached": len(writes)}

    def _lineage(self, state: AgentWorkflowState) -> dict[str, object]:
        settings = self._store.get_settings()
        index = _opensearch_index(settings)
        refs: list[dict[str, str]] = []
        for record in state.get("loaded_records", []):
            self._store.add_lineage(
                LineageRecord(
                    run_id=UUID(state["run_id"]),
                    source_solution=record.raw.source_solution,
                    source_index=record.raw.source_index,
                    source_doc_id=record.raw.source_doc_id,
                    opensearch_index=index,
                    opensearch_id=record.opensearch_id,
                    raw_document=record.raw.body,
                    normalized_document=record.document,
                    created_at=datetime.now(UTC),
                ),
            )
            refs.append(
                {
                    "source_solution": record.raw.source_solution,
                    "source_index": record.raw.source_index,
                    "source_doc_id": record.raw.source_doc_id,
                    "opensearch_id": record.opensearch_id,
                },
            )
        self._store.add_usage(
            make_usage(
                UUID(state["run_id"]),
                AgentName.LINEAGE,
                f"recorded {len(refs)} lineage rows",
            ),
        )
        return {"nodes": ["lineage"], "stages": ["lineage"], "lineage_refs": refs}

    def _orchestrator_result(
        self,
        state: AgentWorkflowState,
    ) -> dict[str, list[str]]:
        self._complete_agent(
            UUID(state["run_id"]),
            AgentName.ORCHESTRATOR,
            _orchestrator_result_prompt(state),
            f"reported {state.get('loaded', 0)} loaded docs",
        )
        return {"nodes": ["orchestrator_result"], "stages": ["orchestrator"]}

    def _complete_agent(
        self,
        run_id: UUID,
        agent: AgentName,
        task_prompt: str,
        activity: str,
    ) -> str:
        settings = self._store.get_settings()
        model = _agent_model(settings, agent)
        price = _model_price(settings, model)
        prompt = _agent_prompt(settings, agent, task_prompt)
        assert self._llm_provider is not None
        response = self._llm_provider.complete(prompt, model, price)
        totals = UsageTotals()
        totals.add(response.usage)
        self._record_usage(run_id, agent, activity, model, totals)
        return response.text

    def _record_usage(
        self,
        run_id: UUID,
        agent: AgentName,
        activity: str,
        model: str,
        totals: UsageTotals,
    ) -> None:
        self._store.add_usage(
            make_usage(
                run_id,
                agent,
                activity,
                model,
                totals.total_tokens,
                totals.cost_usd,
                prompt_tokens=totals.prompt_tokens,
                completion_tokens=totals.completion_tokens,
            ),
        )


def _wire_prd_edges(builder: StateGraph[AgentWorkflowState]) -> None:
    builder.add_edge(START, "elasticsearch_siem")
    builder.add_edge(START, "splunk_siem")
    builder.add_edge(START, "future_siem")
    builder.add_edge(START, "user_request")
    builder.add_edge(
        ["elasticsearch_siem", "splunk_siem", "future_siem"], "siem_connector"
    )
    builder.add_edge(["user_request", "siem_connector"], "orchestrator_request")
    builder.add_edge("orchestrator_request", "schema_profiler")
    builder.add_edge("schema_profiler", "redis_cache")
    builder.add_conditional_edges(
        "redis_cache",
        _cache_route,
        {"hit": "cache_hit_mapping", "miss": "chromadb_ocsf"},
    )
    builder.add_edge(["schema_profiler", "cache_hit_mapping"], "normalization_cached")
    builder.add_edge(["schema_profiler", "chromadb_ocsf"], "normalization_rules")
    builder.add_edge("normalization_rules", "validator_check")
    builder.add_conditional_edges(
        "validator_check",
        _feedback_route,
        {
            "feedback": "orchestrator_feedback_request",
            "valid": "normalization_validated",
        },
    )
    builder.add_edge("orchestrator_feedback_request", "user_feedback")
    builder.add_edge("user_feedback", "orchestrator_feedback_result")
    builder.add_edge("orchestrator_feedback_result", "validator_final")
    builder.add_edge("validator_final", "normalization_validated")
    builder.add_conditional_edges(
        "normalization_cached",
        _cache_branch_route,
        {"wait": "cache_branch_complete", "final": "normalization_final"},
    )
    builder.add_conditional_edges(
        "normalization_validated",
        _miss_branch_route,
        {"wait": "miss_branch_complete", "final": "normalization_final"},
    )
    builder.add_edge(
        ["cache_branch_complete", "miss_branch_complete"], "normalization_final"
    )
    builder.add_edge("normalization_final", "load")
    builder.add_edge("normalization_final", "caching")
    builder.add_edge("load", "opensearch")
    builder.add_edge(["normalization_final", "load"], "lineage")
    builder.add_edge("caching", "redis_cache_write")
    builder.add_edge("lineage", "postgresql")
    builder.add_edge(
        ["opensearch", "redis_cache_write", "postgresql"], "processing_agents"
    )
    builder.add_edge("processing_agents", "orchestrator_result")
    builder.add_edge("orchestrator_result", "user_result")
    builder.add_edge("user_result", END)


def _runtime_nodes() -> tuple[tuple[str, str | None], ...]:
    return (
        ("elasticsearch_siem", None),
        ("splunk_siem", None),
        ("future_siem", None),
        ("user_request", None),
        ("siem_connector", None),
        ("orchestrator_request", "orchestrator"),
        ("schema_profiler", "schema_profiler"),
        ("redis_cache", None),
        ("cache_hit_mapping", None),
        ("chromadb_ocsf", None),
        ("normalization_rules", "normalization"),
        ("validator_check", "validator"),
        ("orchestrator_feedback_request", "orchestrator"),
        ("user_feedback", None),
        ("orchestrator_feedback_result", "orchestrator"),
        ("validator_final", "validator"),
        ("normalization_validated", "normalization"),
        ("normalization_cached", "normalization"),
        ("cache_branch_complete", None),
        ("miss_branch_complete", None),
        ("normalization_final", "normalization"),
        ("load", "load"),
        ("opensearch", None),
        ("caching", "caching"),
        ("redis_cache_write", None),
        ("lineage", "lineage"),
        ("postgresql", None),
        ("processing_agents", None),
        ("orchestrator_result", "orchestrator"),
        ("user_result", None),
    )


def _cache_route(state: AgentWorkflowState) -> str | list[str]:
    has_hit = state.get("cache_hit", False)
    has_miss = state.get("cache_miss", True)
    if has_hit and has_miss:
        return ["hit", "miss"]
    return "miss" if has_miss else "hit"


def _feedback_route(state: AgentWorkflowState) -> str:
    return "feedback" if state.get("needs_feedback", False) else "valid"


def _cache_branch_route(state: AgentWorkflowState) -> str:
    return "wait" if state.get("cache_miss", True) else "final"


def _miss_branch_route(state: AgentWorkflowState) -> str:
    return "wait" if state.get("cache_hit", False) else "final"


def _source_url(settings: dict[str, object], solution: str) -> str:
    value = settings.get(f"source.{solution}.url")
    return value if isinstance(value, str) else solution


def _agent_model(settings: dict[str, object], agent: AgentName) -> str:
    value = settings.get(f"agent.{agent.value}.model")
    if isinstance(value, str) and value:
        return value
    raise ProviderError(f"{agent.value} model is not configured")


def _agent_prompt(
    settings: dict[str, object], agent: AgentName, task_prompt: str
) -> str:
    system_prompt = settings.get(f"agent.{agent.value}.system_prompt")
    if not isinstance(system_prompt, str):
        system_prompt = f"You are the SCALA {agent.value} agent."
    return f"{system_prompt}\n\n{task_prompt}"


def _model_price(settings: dict[str, object], model: str) -> dict[str, float] | None:
    input_cost = _float_setting(settings.get(f"model.{model}.input_cost_per_1m"))
    output_cost = _float_setting(settings.get(f"model.{model}.output_cost_per_1m"))
    if input_cost is None and output_cost is None:
        return None
    return {
        "input_per_1m": input_cost or 0.0,
        "output_per_1m": output_cost or 0.0,
    }


def _float_setting(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    return None


def _opensearch_index(settings: dict[str, object]) -> str:
    value = settings.get("output.opensearch.index")
    return value if isinstance(value, str) else "scala-normalized"


def _candidate_query(field: FieldSample) -> str:
    samples = " ".join(str(sample) for sample in field.samples[:3])
    return f"{field.name} {field.type} {samples}"


def _orchestrator_start_prompt(
    sources: list[SourceSelection],
    docs: list[RawDocument],
) -> str:
    payload = {
        "task": "Acknowledge and plan one SCALA normalization pipeline run.",
        "sources": [source.model_dump(mode="json") for source in sources],
        "document_count": len(docs),
        "rules": ["Return a concise JSON object.", "Do not ask for user input yet."],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _schema_profile_prompt(items: list[FieldWorkItem]) -> str:
    payload = {
        "task": "Profile source fields before OCSF normalization.",
        "fields": [
            {
                "solution": item.source.solution,
                "index": item.source.index,
                "name": item.field.name,
                "type": item.field.type,
                "samples": item.field.samples,
            }
            for item in items
        ],
        "rules": [
            "Classify likely OCSF, vendor custom, missing, and ambiguous fields.",
            "Return JSON only.",
            "Do not make final mapping decisions.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _normalization_batch_prompt(items: list[FieldWorkItem]) -> str:
    payload = {
        "task": "Generate OCSF mapping decisions for cache-miss fields.",
        "fields": [
            _normalization_field_payload(position, item)
            for position, item in enumerate(items, start=1)
        ],
        "known_ocsf_targets": [
            "time",
            "raw_data",
            "src_endpoint.ip",
            "dst_endpoint.ip",
            "dst_endpoint.port",
            "activity_name",
            "severity",
            "actor.user.name",
            "device.hostname",
            "process.name",
            "process.pid",
            "file.path",
            "file.hash.sha256",
            "url.url",
            "http_request.user_agent",
            "network.protocol_name",
            "traffic.bytes_in",
            "traffic.bytes_out",
        ],
        "rules": [
            "Return JSON only.",
            "Return exactly one decision for every field item_id.",
            "Copy each item_id exactly in the matching decision.",
            "Use action=map only when one canonical target is semantically correct.",
            "Use action=keep_raw for vendor-specific, duplicated, or ambiguous fields.",
            "Never drop data.",
        ],
        "response_schema": {
            "decisions": [
                {
                    "item_id": "field-001",
                    "source_field": "string",
                    "action": "map | keep_raw",
                    "ocsf_field": "string or null",
                    "ocsf_type": "string or null",
                },
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _normalization_field_payload(position: int, item: FieldWorkItem) -> JsonObject:
    return {
        "item_id": _normalization_item_id(position),
        "solution": item.source.solution,
        "index": item.source.index,
        "source_field": item.field.name,
        "source_type": item.field.type,
        "samples": item.field.samples,
        "ocsf_candidates": [
            {
                "name": candidate.name,
                "type": candidate.type_name,
                "caption": candidate.caption,
            }
            for candidate in item.candidates
        ],
    }


def _normalization_item_id(position: int) -> str:
    return f"field-{position:03d}"


def _validator_prompt(decisions: list[MappingDecision]) -> str:
    payload = {
        "task": "Validate SCALA mapping decisions.",
        "decisions": [asdict(decision) for decision in decisions],
        "rules": [
            "Return JSON only.",
            "Use status=valid when the mapping preserves data and is coherent.",
            "Use status=feedback_required only for ambiguous or risky mappings.",
        ],
        "response_schema": {
            "status": "valid | feedback_required",
            "feedback_request": {
                "source_field": "string",
                "question": "string",
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _feedback_prompt(payload: JsonObject) -> str:
    return json.dumps(
        {"task": "Prepare a concise human feedback request.", "feedback": payload},
        ensure_ascii=False,
        sort_keys=True,
    )


def _orchestrator_result_prompt(state: AgentWorkflowState) -> str:
    payload = {
        "task": "Summarize final SCALA pipeline result for the user.",
        "loaded": state.get("loaded", 0),
        "cached": state.get("cached", 0),
        "lineage": len(state.get("lineage_refs", [])),
        "mapped": state.get("mapped", 0),
        "kept_raw": state.get("kept_raw", 0),
        "rules": ["Return JSON only.", "Do not include secrets."],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _parse_mapping_decisions(
    items: list[FieldWorkItem],
    text: str,
) -> list[MappingDecision]:
    try:
        payload = json.loads(_extract_json(text))
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "Normalization agent returned invalid mapping JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderError("Normalization agent returned invalid mapping JSON")
    raw_decisions = payload.get("decisions")
    if not isinstance(raw_decisions, list):
        raise ProviderError("Normalization agent returned invalid mapping JSON")
    decisions_by_id = _decisions_by_key(raw_decisions, "item_id")
    decisions_by_field = _decision_buckets_by_field(raw_decisions)
    decisions: list[MappingDecision] = []
    for position, item in enumerate(items, start=1):
        item_id = _normalization_item_id(position)
        decision_payload = decisions_by_id.get(item_id)
        if not isinstance(decision_payload, dict):
            decision_payload = _pop_decision_by_field(
                decisions_by_field, item.field.name
            )
        if not isinstance(decision_payload, dict):
            raise ProviderError("Normalization agent omitted a mapping decision")
        decisions.append(_parse_mapping_decision_payload(item.field, decision_payload))
    return decisions


def _decisions_by_key(
    raw_decisions: list[object],
    key: str,
) -> dict[str, dict[str, object]]:
    decisions: dict[str, dict[str, object]] = {}
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        raw_key = item.get(key)
        if isinstance(raw_key, str) and raw_key:
            decisions[raw_key] = item
    return decisions


def _decision_buckets_by_field(
    raw_decisions: list[object],
) -> dict[str, list[dict[str, object]]]:
    decisions: dict[str, list[dict[str, object]]] = {}
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        source_field = item.get("source_field")
        if isinstance(source_field, str) and source_field:
            decisions.setdefault(source_field, []).append(item)
    return decisions


def _pop_decision_by_field(
    decisions: dict[str, list[dict[str, object]]],
    source_field: str,
) -> dict[str, object] | None:
    matches = decisions.get(source_field)
    if not matches:
        return None
    return matches.pop(0)


def _parse_mapping_decision_payload(
    field: FieldSample,
    payload: dict[str, object],
) -> MappingDecision:
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


def _parse_validator_feedback(
    text: str,
    decisions: list[MappingDecision],
) -> JsonObject | None:
    try:
        payload = json.loads(_extract_json(text))
    except json.JSONDecodeError as exc:
        raise ProviderError("Validator agent returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ProviderError("Validator agent returned invalid JSON")
    if payload.get("status") != "feedback_required":
        return None
    request_payload = payload.get("feedback_request")
    if not isinstance(request_payload, dict):
        request_payload = {}
    field_name = str(request_payload.get("source_field") or "")
    decision = _decision_for_feedback(decisions, field_name)
    return {
        "field": {
            "source_field": decision.source_field,
            "type": decision.source_type,
            "samples": [],
        },
        "recommendation": {
            "ocsf_field": decision.ocsf_field,
            "ocsf_type": decision.ocsf_type,
            "action": decision.action,
            "why": str(
                request_payload.get("question") or "Validator requested review."
            ),
        },
        "options": ["approve", "keep_raw", "comment"],
    }


def _decision_for_feedback(
    decisions: list[MappingDecision],
    field_name: str,
) -> MappingDecision:
    for decision in decisions:
        if decision.source_field == field_name:
            return decision
    if decisions:
        return decisions[0]
    return MappingDecision("unknown", "unknown", "keep_raw", None, None)


def _apply_feedback(
    decisions: list[MappingDecision],
    feedback: JsonObject,
) -> list[MappingDecision]:
    field_payload = feedback.get("field")
    field_name = ""
    if isinstance(field_payload, dict):
        field_name = str(field_payload.get("source_field") or "")
    response = str(feedback.get("decision") or "").lower()
    comment = str(feedback.get("comment") or "").lower()
    keep_raw = response == "keep_raw" or "keep_raw" in comment or "keep raw" in comment
    if not keep_raw or not field_name:
        return list(decisions)
    updated: list[MappingDecision] = []
    for decision in decisions:
        if decision.source_field == field_name:
            updated.append(
                MappingDecision(
                    decision.source_field, decision.source_type, "keep_raw", None, None
                ),
            )
        else:
            updated.append(decision)
    return updated


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
