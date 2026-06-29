from scala_backend.app_factory import create_app
from scala_backend.config import DEFAULT_OPENAI_MODEL, BackendConfig


def test_create_app_seeds_default_model_for_all_llm_agents() -> None:
    """create app seeds default model for all llm agents 동작을 검증한다."""
    app = create_app(BackendConfig())
    settings = app.store.get_settings()

    assert settings["agent.orchestrator.model"] == DEFAULT_OPENAI_MODEL
    assert settings["agent.schema_profiler.model"] == DEFAULT_OPENAI_MODEL
    assert settings["agent.normalization.model"] == DEFAULT_OPENAI_MODEL
    assert settings["agent.validator.model"] == DEFAULT_OPENAI_MODEL


def test_create_app_seeds_configured_model_for_all_llm_agents() -> None:
    """create app seeds configured model for all llm agents 동작을 검증한다."""
    app = create_app(BackendConfig(openai_model="gpt-custom-mini"))
    settings = app.store.get_settings()

    assert settings["agent.orchestrator.model"] == "gpt-custom-mini"
    assert settings["agent.schema_profiler.model"] == "gpt-custom-mini"
    assert settings["agent.normalization.model"] == "gpt-custom-mini"
    assert settings["agent.validator.model"] == "gpt-custom-mini"
