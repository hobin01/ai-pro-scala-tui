from decimal import Decimal
from types import ModuleType

import pytest

from scala_backend.errors import ProviderError
from scala_backend.providers import FakeProvider, OpenAiProvider, calculate_usage


class RejectingModels:
    """OpenAI models.retrieve 실패를 재현하는 models client다."""

    def retrieve(self, model: str) -> None:
        """model 조회 실패를 발생시켜 validate 오류 경로를 재현한다."""
        raise RuntimeError(model)


class RejectingOpenAI:
    """OpenAiProvider 생성자가 받는 fake OpenAI client다."""

    def __init__(self, api_key: str) -> None:
        """OpenAI client 대역에 실패하는 models API를 붙인다."""
        del api_key
        self.models = RejectingModels()


class RejectingOpenAiModule(ModuleType):
    """openai 모듈 import를 fake client로 대체한다."""

    OpenAI = RejectingOpenAI


def test_usage_records_tokens_without_local_cost_estimate() -> None:
    """UsageRecord가 token 수를 기록하되 local 비용 추정은 0으로 두는지 확인한다."""
    usage = calculate_usage(
        prompt_tokens=1000,
        completion_tokens=500,
        price={"prompt_per_1k": 0.15, "completion_per_1k": 0.60},
    )

    assert usage.total_tokens == 1500
    assert usage.cost_usd == Decimal("0")


def test_fake_provider_is_deterministic() -> None:
    """Fake provider가 같은 입력에 재현 가능한 응답을 반환하는지 확인한다."""
    provider = FakeProvider()

    response = provider.complete("map clientip", "gpt-5.4-mini", None)
    vectors = provider.embed(["clientip"], "text-embedding-3-small")

    assert response.text == "gpt-5.4-mini: approved"
    assert response.usage.total_tokens > 0
    assert vectors == [[1.0, 2.0, 1.0]]


def test_openai_provider_validate_converts_sdk_error_to_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI validate 실패가 ProviderError로 감싸지는지 확인한다."""

    def fake_import_module(name: str) -> ModuleType:
        """openai module import를 실패 client module로 대체한다."""
        assert name == "openai"
        return RejectingOpenAiModule("openai")

    monkeypatch.setattr(
        "scala_backend.providers.importlib.import_module",
        fake_import_module,
    )
    provider = OpenAiProvider("sk-invalid")

    with pytest.raises(ProviderError, match="OpenAI API key is invalid"):
        provider.validate("gpt-5.4-mini")
