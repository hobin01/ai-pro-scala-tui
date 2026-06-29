from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    def __init__(
        self,
        api_key: str,
        *,
        admin_api_key: str | None = None,
        cost_api_key_id: str | None = None,
        cost_project_id: str | None = None,
    ) -> None:
        module = importlib.import_module("openai")
        client_cls = module.OpenAI
        self._client = client_cls(api_key=api_key)
        self._cost_api_key = admin_api_key or api_key
        self._cost_api_key_id = cost_api_key_id
        self._cost_project_id = cost_project_id

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

    def organization_cost_usd(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Decimal:
        params: dict[str, object] = {
            "start_time": int(start_time.timestamp()),
            "end_time": int(end_time.timestamp()),
            "bucket_width": "1d",
            "limit": 180,
        }
        if self._cost_api_key_id:
            params["api_key_ids[]"] = self._cost_api_key_id
        if self._cost_project_id:
            params["project_ids[]"] = self._cost_project_id
        url = "https://api.openai.com/v1/organization/costs?" + urlencode(
            params,
            doseq=True,
        )
        request = Request(
            url,
            headers={"Authorization": f"Bearer {self._cost_api_key}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(exc.__class__.__name__) from exc
        return _sum_cost_payload(payload)


def calculate_usage(
    prompt_tokens: int,
    completion_tokens: int,
    price: dict[str, float] | None,
) -> ProviderUsage:
    total = prompt_tokens + completion_tokens
    del price
    return ProviderUsage(prompt_tokens, completion_tokens, total, Decimal("0"))


def _sum_cost_payload(payload: object) -> Decimal:
    total = Decimal("0")
    if not isinstance(payload, dict):
        return total
    buckets = payload.get("data")
    if not isinstance(buckets, list):
        return total
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        results = bucket.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            amount = result.get("amount")
            if not isinstance(amount, dict):
                continue
            if amount.get("currency") not in {None, "usd"}:
                continue
            value = amount.get("value")
            if isinstance(value, int | float | str):
                total += Decimal(str(value))
    return total
