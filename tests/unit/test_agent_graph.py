from scala_backend.agent_graph import (
    AGENT_STAGE_ORDER,
    build_agent_graph,
    run_agent_graph,
)


def test_langgraph_runtime_edges_follow_prd_mermaid_topology() -> None:
    graph = build_agent_graph().get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}

    for edge in (
        ("elasticsearch_siem", "siem_connector"),
        ("splunk_siem", "siem_connector"),
        ("future_siem", "siem_connector"),
        ("user_request", "orchestrator_request"),
        ("siem_connector", "orchestrator_request"),
        ("orchestrator_request", "schema_profiler"),
        ("schema_profiler", "redis_cache"),
        ("schema_profiler", "normalization_cached"),
        ("schema_profiler", "normalization_rules"),
        ("redis_cache", "chromadb_ocsf"),
        ("redis_cache", "cache_hit_mapping"),
        ("cache_hit_mapping", "normalization_cached"),
        ("chromadb_ocsf", "normalization_rules"),
        ("normalization_rules", "validator_check"),
        ("validator_check", "orchestrator_feedback_request"),
        ("orchestrator_feedback_request", "user_feedback"),
        ("user_feedback", "orchestrator_feedback_result"),
        ("orchestrator_feedback_result", "validator_final"),
        ("validator_final", "normalization_validated"),
        ("normalization_cached", "cache_branch_complete"),
        ("normalization_validated", "miss_branch_complete"),
        ("cache_branch_complete", "normalization_final"),
        ("miss_branch_complete", "normalization_final"),
        ("normalization_final", "load"),
        ("normalization_final", "caching"),
        ("normalization_final", "lineage"),
        ("load", "opensearch"),
        ("load", "lineage"),
        ("caching", "redis_cache_write"),
        ("lineage", "postgresql"),
        ("opensearch", "processing_agents"),
        ("redis_cache_write", "processing_agents"),
        ("postgresql", "processing_agents"),
        ("processing_agents", "orchestrator_result"),
        ("orchestrator_result", "user_result"),
    ):
        assert edge in edges


def test_agent_graph_runs_default_prd_path() -> None:
    state = run_agent_graph("run-1")

    assert state["run_id"] == "run-1"
    assert set(state["stages"]) == set(AGENT_STAGE_ORDER)
    assert state["stages"][0] == "orchestrator"
    assert state["stages"][-1] == "orchestrator"
    assert "siem_connector" in state["nodes"]
    assert "redis_cache" in state["nodes"]
    assert "chromadb_ocsf" in state["nodes"]
    assert "opensearch" in state["nodes"]
    assert "postgresql" in state["nodes"]
    assert "processing_agents" in state["nodes"]


def test_agent_graph_cache_hit_skips_rag_validator_and_feedback() -> None:
    state = run_agent_graph("run-1", cache_hit=True, cache_miss=False)

    assert "chromadb_ocsf" not in state["nodes"]
    assert "validator" not in state["stages"]
    assert "orchestrator_feedback_request" not in state["nodes"]
    assert "user_feedback" not in state["nodes"]


def test_agent_graph_feedback_routes_through_orchestrator() -> None:
    state = run_agent_graph("run-1", needs_feedback=True)

    assert "orchestrator_feedback_request" in state["nodes"]
    assert "user_feedback" in state["nodes"]
    assert "orchestrator_feedback_result" in state["nodes"]
    assert state["stages"].count("validator") == 2
    assert state["nodes"][-1] == "user_result"


def test_agent_graph_mixed_cache_hit_and_miss_keeps_feedback_path() -> None:
    state = run_agent_graph(
        "run-1",
        cache_hit=True,
        cache_miss=True,
        needs_feedback=True,
    )

    assert "cache_hit_mapping" in state["nodes"]
    assert "chromadb_ocsf" in state["nodes"]
    assert "user_feedback" in state["nodes"]
    assert state["nodes"].count("normalization_final") == 1
    assert state["nodes"].count("processing_agents") == 1
