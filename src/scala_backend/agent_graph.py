from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph


def _merge_sequence(left: list[str], right: list[str]) -> list[str]:
    """PRD agent 흐름 trace의 merge sequence 보조 경로를 분리한다."""
    return [*left, *right]


class AgentGraphState(TypedDict):
    """PRD mermaid graph 실행 중 node trace와 분기 플래그를 보관한다."""

    run_id: str
    stages: Annotated[list[str], _merge_sequence]
    nodes: Annotated[list[str], _merge_sequence]
    cache_hit: NotRequired[bool]
    cache_miss: NotRequired[bool]
    needs_feedback: NotRequired[bool]


AGENT_STAGE_ORDER = (
    "orchestrator",
    "schema_profiler",
    "normalization",
    "validator",
    "load",
    "caching",
    "lineage",
)


def build_agent_graph() -> Any:
    """build agent graph 구성을 만든다."""
    builder = StateGraph(AgentGraphState)
    for node, stage in _runtime_nodes():
        builder.add_node(node, cast("Any", _stage_node(node, stage)))

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
    return builder.compile()


def run_agent_graph(
    run_id: str,
    *,
    cache_hit: bool = False,
    cache_miss: bool = True,
    needs_feedback: bool = False,
) -> AgentGraphState:
    """캐시 hit/miss와 feedback 플래그로 LangGraph trace를 실행한다."""
    graph = build_agent_graph()
    result = graph.invoke(
        {
            "run_id": run_id,
            "stages": [],
            "nodes": [],
            "cache_hit": cache_hit,
            "cache_miss": cache_miss,
            "needs_feedback": needs_feedback,
        },
    )
    return AgentGraphState(
        run_id=str(result["run_id"]),
        stages=list(result["stages"]),
        nodes=list(result["nodes"]),
        cache_hit=bool(result.get("cache_hit", False)),
        cache_miss=bool(result.get("cache_miss", True)),
        needs_feedback=bool(result.get("needs_feedback", False)),
    )


def _runtime_nodes() -> tuple[tuple[str, str | None], ...]:
    """PRD agent 흐름 trace의 runtime nodes 보조 경로를 분리한다."""
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


def _stage_node(
    node_name: str,
    stage: str | None,
) -> Callable[[AgentGraphState], dict[str, list[str]]]:
    """PRD agent 흐름 trace의 stage node 보조 경로를 분리한다."""

    def node(_state: AgentGraphState) -> dict[str, list[str]]:
        """LangGraph 실행 기록에 현재 노드와 agent stage를 추가한다."""
        update = {"nodes": [node_name]}
        if stage is not None:
            update["stages"] = [stage]
        return update

    return node


def _cache_route(state: AgentGraphState) -> str | list[str]:
    """PRD agent 흐름 trace의 cache route 보조 경로를 분리한다."""
    has_hit = state.get("cache_hit", False)
    has_miss = state.get("cache_miss", True)
    if has_hit and has_miss:
        return ["hit", "miss"]
    return "hit" if has_hit else "miss"


def _feedback_route(state: AgentGraphState) -> str:
    """PRD agent 흐름 trace의 feedback route 보조 경로를 분리한다."""
    return "feedback" if state.get("needs_feedback", False) else "valid"


def _cache_branch_route(state: AgentGraphState) -> str:
    """PRD agent 흐름 trace의 cache branch route 보조 경로를 분리한다."""
    return "wait" if state.get("cache_miss", True) else "final"


def _miss_branch_route(state: AgentGraphState) -> str:
    """PRD agent 흐름 trace의 miss branch route 보조 경로를 분리한다."""
    return "wait" if state.get("cache_hit", False) else "final"
