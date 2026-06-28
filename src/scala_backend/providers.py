from __future__ import annotations

import importlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from scala_backend.errors import ProviderError


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal


@dataclass(frozen=True)
class LlmResponse:
    text: str
    usage: ProviderUsage


class LlmProvider(Protocol):
    def complete(
        self, prompt: str, model: str, price: dict[str, float] | None
    ) -> LlmResponse: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], model: str) -> list[list[float]]: ...


class FakeProvider:
    def __init__(self) -> None:
        self.complete_calls = 0
        self.embed_calls = 0

    def complete(
        self, prompt: str, model: str, price: dict[str, float] | None
    ) -> LlmResponse:
        self.complete_calls += 1
        tokens = max(1, len(prompt.split()))
        usage = calculate_usage(tokens, 3, price)
        return LlmResponse(text=f"{model}: approved", usage=usage)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        self.embed_calls += 1
        return [[float(len(text) % 7), float(len(model) % 5), 1.0] for text in texts]


class OpenAiProvider:
    def __init__(self, api_key: str) -> None:
        module = importlib.import_module("openai")
        client_cls = module.OpenAI
        self._client = client_cls(api_key=api_key)

    def complete(
        self, prompt: str, model: str, price: dict[str, float] | None
    ) -> LlmResponse:
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
    total = prompt_tokens + completion_tokens
    prompt_price = Decimal(str((price or {}).get("prompt_per_1k", 0)))
    completion_price = Decimal(str((price or {}).get("completion_per_1k", 0)))
    cost = Decimal(prompt_tokens) * prompt_price / Decimal(1000) + Decimal(
        completion_tokens
    ) * completion_price / Decimal(1000)
    return ProviderUsage(prompt_tokens, completion_tokens, total, cost)
