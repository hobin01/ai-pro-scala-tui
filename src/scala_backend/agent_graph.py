from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph


class AgentGraphState(TypedDict):
    run_id: str
    stages: list[str]


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
    builder = StateGraph(AgentGraphState)
    previous = START
    for stage in AGENT_STAGE_ORDER:
        builder.add_node(stage, cast("Any", _stage_node(stage)))
        builder.add_edge(previous, stage)
        previous = stage
    builder.add_edge(previous, END)
    return builder.compile()


def run_agent_graph(run_id: str) -> AgentGraphState:
    graph = build_agent_graph()
    result = graph.invoke({"run_id": run_id, "stages": []})
    return AgentGraphState(run_id=str(result["run_id"]), stages=list(result["stages"]))


def _stage_node(stage: str) -> Callable[[AgentGraphState], AgentGraphState]:
    def node(state: AgentGraphState) -> AgentGraphState:
        return {
            "run_id": state["run_id"],
            "stages": [*state.get("stages", []), stage],
        }

    return node
