from decimal import Decimal
from types import ModuleType

import pytest

from scala_backend.errors import ProviderError
from scala_backend.providers import FakeProvider, OpenAiProvider, calculate_usage


class RejectingModels:
    """RejectingModels 테스트 대상을 표현한다."""

    def retrieve(self, model: str) -> None:
        """retrieve 동작을 처리한다."""
        raise RuntimeError(model)


class RejectingOpenAI:
    """RejectingOpenAI 테스트 대상을 표현한다."""

    def __init__(self, api_key: str) -> None:
        """객체 초기 상태를 준비한다."""
        del api_key
        self.models = RejectingModels()


class RejectingOpenAiModule(ModuleType):
    """RejectingOpenAiModule 테스트 대상을 표현한다."""

    OpenAI = RejectingOpenAI


def test_usage_records_tokens_without_local_cost_estimate() -> None:
    """usage records tokens without local cost estimate 동작을 검증한다."""
    usage = calculate_usage(
        prompt_tokens=1000,
        completion_tokens=500,
        price={"prompt_per_1k": 0.15, "completion_per_1k": 0.60},
    )

    assert usage.total_tokens == 1500
    assert usage.cost_usd == Decimal("0")


def test_fake_provider_is_deterministic() -> None:
    """fake provider is deterministic 동작을 검증한다."""
    provider = FakeProvider()

    response = provider.complete("map clientip", "gpt-5.4-mini", None)
    vectors = provider.embed(["clientip"], "text-embedding-3-small")

    assert response.text == "gpt-5.4-mini: approved"
    assert response.usage.total_tokens > 0
    assert vectors == [[1.0, 2.0, 1.0]]


def test_openai_provider_validate_converts_sdk_error_to_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """openai provider validate converts sdk error to provider error 동작을 검증한다."""

    def fake_import_module(name: str) -> ModuleType:
        """fake import module 동작을 처리한다."""
        assert name == "openai"
        return RejectingOpenAiModule("openai")

    monkeypatch.setattr(
        "scala_backend.providers.importlib.import_module",
        fake_import_module,
    )
    provider = OpenAiProvider("sk-invalid")

    with pytest.raises(ProviderError, match="OpenAI API key is invalid"):
        provider.validate("gpt-5.4-mini")
