from uuid import uuid4

from scala_backend.models import AgentName
from scala_backend.store import (
    InMemoryStore,
    aggregate_usage,
    make_usage,
    seed_dev_settings,
)


def test_seed_dev_settings_is_explicit() -> None:
    store = InMemoryStore()

    assert store.get_settings() == {}

    seed_dev_settings(store)

    assert store.get_settings()["source.splunk.indices"] == ["main"]
    assert "agent.schema_profiler.system_prompt" in store.get_settings()


def test_monitoring_aggregate_contains_all_agents() -> None:
    run_id = uuid4()
    usage = [make_usage(run_id, AgentName.LOAD, "loaded 1 docs")]

    result = aggregate_usage(usage, "all_time")

    assert result["total"]["runs"] == 1
    assert len(result["agents"]) == 7
    load_row = next(row for row in result["agents"] if row["agent"] == "load")
    assert load_row["tokens"] == 0
    assert load_row["cost"] == 0.0
