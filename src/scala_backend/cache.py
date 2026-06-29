from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class MappingDecision:
    """MappingDecision 객체의 책임을 정의한다."""

    source_field: str
    source_type: str
    action: str
    ocsf_field: str | None
    ocsf_type: str | None


class MappingCache(Protocol):
    """MappingCache 객체의 책임을 정의한다."""

    def get(self, key: str) -> MappingDecision | None:
        """get 동작을 처리한다."""
        ...

    def set(self, key: str, decision: MappingDecision) -> None:
        """set 동작을 처리한다."""
        ...


class RedisClient(Protocol):
    """RedisClient 호출 계약을 정의한다."""

    def get(self, name: str) -> bytes | str | None:
        """get 동작을 처리한다."""
        ...

    def set(self, name: str, value: str) -> object:
        """set 동작을 처리한다."""
        ...


class InMemoryMappingCache:
    """InMemoryMappingCache 객체의 책임을 정의한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self._items: dict[str, MappingDecision] = {}

    def get(self, key: str) -> MappingDecision | None:
        """get 동작을 처리한다."""
        return self._items.get(key)

    def set(self, key: str, decision: MappingDecision) -> None:
        """set 동작을 처리한다."""
        self._items[key] = decision


class RedisMappingCache:
    """RedisMappingCache 객체의 책임을 정의한다."""

    def __init__(
        self,
        client: RedisClient | None = None,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """객체 초기 상태를 준비한다."""
        self._client: RedisClient
        if client is None:
            import redis

            self._client = redis.Redis.from_url(redis_url)
        else:
            self._client = client

    def get(self, key: str) -> MappingDecision | None:
        """get 동작을 처리한다."""
        payload = self._client.get(key)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode()
        return MappingDecision(**json.loads(payload))

    def set(self, key: str, decision: MappingDecision) -> None:
        """set 동작을 처리한다."""
        self._client.set(key, json.dumps(asdict(decision)))


def cache_key(source_url: str, index: str, field_name: str, field_type: str) -> str:
    """cache key 동작을 처리한다."""
    return "|".join([source_url, index, field_name, field_type])
