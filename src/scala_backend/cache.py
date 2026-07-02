from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class MappingDecision:
    """source field 하나에 대한 OCSF mapping 결정이다."""

    source_field: str
    source_type: str
    action: str
    ocsf_field: str | None
    ocsf_type: str | None


@dataclass(frozen=True)
class CacheWrite:
    """Caching agent가 Redis에 반영할 매핑 결정을 담는다."""

    key: str
    decision: MappingDecision


class MappingCache(Protocol):
    """mapping 결정 cache 구현이 제공해야 하는 get/set 계약이다."""

    def get(self, key: str) -> MappingDecision | None:
        """cache key에 저장된 mapping 결정을 읽는다."""
        ...

    def set(self, key: str, decision: MappingDecision) -> None:
        """cache key에 mapping 결정을 저장한다."""
        ...


class RedisClient(Protocol):
    """RedisMappingCache가 의존하는 Redis get/set 최소 surface다."""

    def get(self, name: str) -> bytes | str | None:
        """Redis key의 raw payload를 읽는다."""
        ...

    def set(self, name: str, value: str) -> object:
        """Redis key에 JSON 문자열 payload를 저장한다."""
        ...


class InMemoryMappingCache:
    """테스트와 memory mode에서 mapping 결정을 dict에 보관한다."""

    def __init__(self) -> None:
        """mapping decision 저장용 in-memory dict를 준비한다."""
        self._items: dict[str, MappingDecision] = {}

    def get(self, key: str) -> MappingDecision | None:
        """dict에서 cache key의 mapping 결정을 읽는다."""
        return self._items.get(key)

    def set(self, key: str, decision: MappingDecision) -> None:
        """dict에 cache key와 mapping 결정을 저장한다."""
        self._items[key] = decision


class RedisMappingCache:
    """Redis에 mapping 결정을 JSON으로 저장하는 cache 구현이다."""

    def __init__(
        self,
        client: RedisClient | None = None,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """주입된 Redis client가 없으면 redis_url로 client를 만든다."""
        self._client: RedisClient
        if client is None:
            import redis

            self._client = redis.Redis.from_url(redis_url)
        else:
            self._client = client

    def get(self, key: str) -> MappingDecision | None:
        """Redis JSON payload를 MappingDecision으로 복원한다."""
        payload = self._client.get(key)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode()
        return MappingDecision(**json.loads(payload))

    def set(self, key: str, decision: MappingDecision) -> None:
        """MappingDecision을 JSON payload로 직렬화해 Redis에 저장한다."""
        self._client.set(key, json.dumps(asdict(decision)))


def cache_key(source_url: str, index: str, field_name: str, field_type: str) -> str:
    """source URL, index, field, type을 안정적인 Redis key로 결합한다."""
    return "|".join([source_url, index, field_name, field_type])
