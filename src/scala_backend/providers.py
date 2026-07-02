from __future__ import annotations

import importlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from scala_backend.errors import ProviderError


@dataclass(frozen=True)
class ProviderUsage:
    """OpenAI 응답의 입력/출력 토큰과 로컬 비용 필드를 보관한다."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal


@dataclass(frozen=True)
class LlmResponse:
    """LLM 텍스트 응답과 provider usage를 함께 전달한다."""

    text: str
    usage: ProviderUsage


class LlmProvider(Protocol):
    """Normalization agent가 의존하는 LLM provider 메서드를 명시한다."""

    def validate(self, model: str) -> None:
        """provider가 key/model 사전 검사를 제공해야 함을 명시한다."""
        ...

    def complete(
        self, prompt: str, model: str, price: dict[str, float] | None
    ) -> LlmResponse:
        """단일 prompt를 실행해 텍스트와 token usage를 돌려줘야 함을 명시한다."""
        ...


class EmbeddingProvider(Protocol):
    """OCSF Chroma index가 사용할 embedding provider 형태를 명시한다."""

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """여러 OCSF 설명 문장을 embedding vector로 바꿔야 함을 명시한다."""
        ...


class FakeProvider:
    """테스트에서 LLM과 embedding 호출 횟수를 기록하는 provider 대역이다."""

    def __init__(self) -> None:
        """테스트가 호출 여부를 확인할 counter를 초기화한다."""
        self.complete_calls = 0
        self.embed_calls = 0

    def validate(self, model: str) -> None:
        """Fake provider에서는 모든 model을 사용 가능하다고 간주한다."""
        del model

    def complete(
        self, prompt: str, model: str, price: dict[str, float] | None
    ) -> LlmResponse:
        """prompt 길이에 비례한 fake usage와 승인 텍스트를 반환한다."""
        self.complete_calls += 1
        tokens = max(1, len(prompt.split()))
        usage = calculate_usage(tokens, 3, price)
        return LlmResponse(text=f"{model}: approved", usage=usage)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """텍스트와 model 길이로 deterministic fake vector를 만든다."""
        self.embed_calls += 1
        return [[float(len(text) % 7), float(len(model) % 5), 1.0] for text in texts]


class OpenAiProvider:
    """OpenAI responses와 embeddings API 호출을 감싼다."""

    def __init__(self, api_key: str) -> None:
        """Responses와 embeddings API에 쓸 OpenAI client를 준비한다."""
        module = importlib.import_module("openai")
        client_cls = module.OpenAI
        self._client = client_cls(api_key=api_key)

    def validate(self, model: str) -> None:
        """models.retrieve로 API key와 model 접근 가능성을 확인한다."""
        try:
            self._client.models.retrieve(model)
        except Exception as exc:
            raise ProviderError(
                "OpenAI API key is invalid or the configured model is unavailable"
            ) from exc

    def complete(
        self, prompt: str, model: str, price: dict[str, float] | None
    ) -> LlmResponse:
        """Responses API 결과에서 output_text와 token usage를 추출한다."""
        try:
            response = self._client.responses.create(model=model, input=prompt)
        except Exception as exc:
            raise ProviderError(exc.__class__.__name__) from exc
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return LlmResponse(
            text=str(getattr(response, "output_text", "")),
            usage=calculate_usage(prompt_tokens, completion_tokens, price),
        )

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embedding API 응답을 Chroma가 받는 float vector 목록으로 바꾼다."""
        try:
            response = self._client.embeddings.create(model=model, input=texts)
        except Exception as exc:
            raise ProviderError(exc.__class__.__name__) from exc
        return [list(item.embedding) for item in response.data]


def calculate_usage(
    prompt_tokens: int,
    completion_tokens: int,
    price: dict[str, float] | None,
) -> ProviderUsage:
    """provider 토큰 카운트를 내부 Usage 객체로 포장한다."""
    total = prompt_tokens + completion_tokens
    cost = Decimal("0")
    if price:
        prompt_per_1m = _rate(price, "input_per_1m", "prompt_per_1m")
        completion_per_1m = _rate(price, "output_per_1m", "completion_per_1m")
        cost += Decimal(prompt_tokens) * prompt_per_1m / Decimal(1_000_000)
        cost += Decimal(completion_tokens) * completion_per_1m / Decimal(1_000_000)
    return ProviderUsage(prompt_tokens, completion_tokens, total, cost)


def _rate(
    price: dict[str, float],
    per_1m_key: str,
    legacy_per_1k_key: str,
) -> Decimal:
    """가격 사전에서 지정 key의 token 단가를 Decimal로 읽는다."""
    if per_1m_key in price:
        return Decimal(str(price[per_1m_key]))
    if legacy_per_1k_key in price:
        return Decimal(str(price[legacy_per_1k_key])) * Decimal(1000)
    return Decimal("0")
