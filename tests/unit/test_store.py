from decimal import Decimal
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
    """개발 기본 settings seed 값이 명시적으로 저장되는지 확인한다."""
    store = InMemoryStore()

    assert store.get_settings() == {}

    seed_dev_settings(store)

    assert store.get_settings()["source.elasticsearch.indices"] == [
        "scala-es-network",
        "scala-es-endpoint",
    ]
    assert store.get_settings()["source.splunk.indices"] == ["main", "security"]
    assert store.get_settings()["agent.normalization.model"] == DEFAULT_OPENAI_MODEL
    assert (
        store.get_settings()[f"model.{DEFAULT_OPENAI_MODEL}.input_cost_per_1m"] == 0.75
    )
    assert "agent.schema_profiler.system_prompt" in store.get_settings()


def test_agent_model_settings_applies_one_model_to_all_llm_agents() -> None:
    """agent model helper가 하나의 model을 모든 LLM agent에 적용하는지 확인한다."""
    settings = agent_model_settings("gpt-custom-mini")

    assert settings == {
        "agent.orchestrator.model": "gpt-custom-mini",
        "agent.schema_profiler.model": "gpt-custom-mini",
        "agent.normalization.model": "gpt-custom-mini",
        "agent.validator.model": "gpt-custom-mini",
    }


def test_monitoring_aggregate_contains_all_agents() -> None:
    """monitoring 집계가 모든 Scala-agent별 usage bucket을 포함하는지 확인한다."""
    run_id = uuid4()
    usage = [make_usage(run_id, AgentName.LOAD, "loaded 1 docs")]

    result = aggregate_usage(usage, "all_time")

    assert result["total"]["runs"] == 1
    assert len(result["agents"]) == 7
    load_row = next(row for row in result["agents"] if row["agent"] == "load")
    assert load_row["tokens"] == 0
    assert load_row["cost"] == 0.0


def test_monitoring_aggregate_sums_agent_costs() -> None:
    run_id = uuid4()
    usage = [
        make_usage(run_id, AgentName.ORCHESTRATOR, "planned", "gpt", 10),
        make_usage(
            run_id,
            AgentName.NORMALIZATION,
            "mapped",
            "gpt",
            20,
            cost=Decimal("0.12"),
        ),
    ]

    result = aggregate_usage(usage, "all_time")

    assert result["total"]["cost"] == 0.12
    assert result["total"]["cost_source"] == "stored_usage"
    normalization = next(
        row for row in result["agents"] if row["agent"] == "normalization"
    )
    assert normalization["cost"] == 0.12
