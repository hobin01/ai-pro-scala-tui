from scala_backend.agent_graph import AGENT_STAGE_ORDER, run_agent_graph


def test_agent_graph_runs_all_scala_agent_nodes() -> None:
    state = run_agent_graph("run-1")

    assert state["run_id"] == "run-1"
    assert state["stages"] == list(AGENT_STAGE_ORDER)
