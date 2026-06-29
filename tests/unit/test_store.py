from uuid import uuid4

from scala_backend.config import DEFAULT_OPENAI_MODEL
from scala_backend.models import AgentName
from scala_backend.store import (
    InMemoryStore,
    agent_model_settings,
    aggregate_usage,
    make_usage,
    seed_dev_settings,
)


def test_seed_dev_settings_is_explicit() -> None:
    """seed dev settings is explicit 동작을 검증한다."""
    store = InMemoryStore()

    assert store.get_settings() == {}

    seed_dev_settings(store)

    assert store.get_settings()["source.splunk.indices"] == ["main"]
    assert store.get_settings()["agent.normalization.model"] == DEFAULT_OPENAI_MODEL
    assert "agent.schema_profiler.system_prompt" in store.get_settings()


def test_agent_model_settings_applies_one_model_to_all_llm_agents() -> None:
    """agent model settings applies one model to all llm agents 동작을 검증한다."""
    settings = agent_model_settings("gpt-custom-mini")

    assert settings == {
        "agent.orchestrator.model": "gpt-custom-mini",
        "agent.schema_profiler.model": "gpt-custom-mini",
        "agent.normalization.model": "gpt-custom-mini",
        "agent.validator.model": "gpt-custom-mini",
    }


def test_monitoring_aggregate_contains_all_agents() -> None:
    """monitoring aggregate contains all agents 동작을 검증한다."""
    run_id = uuid4()
    usage = [make_usage(run_id, AgentName.LOAD, "loaded 1 docs")]

    result = aggregate_usage(usage, "all_time")

    assert result["total"]["runs"] == 1
    assert len(result["agents"]) == 7
    load_row = next(row for row in result["agents"] if row["agent"] == "load")
    assert load_row["tokens"] == 0
    assert load_row["cost"] == 0.0
