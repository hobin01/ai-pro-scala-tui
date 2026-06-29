from decimal import Decimal
from types import ModuleType

import pytest

from scala_backend.errors import ProviderError
from scala_backend.providers import FakeProvider, OpenAiProvider, calculate_usage


class RejectingModels:
    def retrieve(self, model: str) -> None:
        raise RuntimeError(model)


class RejectingOpenAI:
    def __init__(self, api_key: str) -> None:
        del api_key
        self.models = RejectingModels()


class RejectingOpenAiModule(ModuleType):
    OpenAI = RejectingOpenAI


def test_usage_records_tokens_without_local_cost_estimate() -> None:
    usage = calculate_usage(
        prompt_tokens=1000,
        completion_tokens=500,
        price={"prompt_per_1k": 0.15, "completion_per_1k": 0.60},
    )

    assert usage.total_tokens == 1500
    assert usage.cost_usd == Decimal("0")


def test_fake_provider_is_deterministic() -> None:
    provider = FakeProvider()

    response = provider.complete("map clientip", "gpt-5.4-mini", None)
    vectors = provider.embed(["clientip"], "text-embedding-3-small")

    assert response.text == "gpt-5.4-mini: approved"
    assert response.usage.total_tokens > 0
    assert vectors == [[1.0, 2.0, 1.0]]


def test_openai_provider_validate_converts_sdk_error_to_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_import_module(name: str) -> ModuleType:
        assert name == "openai"
        return RejectingOpenAiModule("openai")

    monkeypatch.setattr(
        "scala_backend.providers.importlib.import_module",
        fake_import_module,
    )
    provider = OpenAiProvider("sk-invalid")

    with pytest.raises(ProviderError, match="OpenAI API key is invalid"):
        provider.validate("gpt-5.4-mini")
