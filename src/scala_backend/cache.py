from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class MappingDecision:
    """필드 매핑 캐시에서 함께 이동해야 하는 상태를 묶는다."""

    source_field: str
    source_type: str
    action: str
    ocsf_field: str | None
    ocsf_type: str | None


class MappingCache(Protocol):
    """필드 매핑 캐시에서 함께 이동해야 하는 상태를 묶는다."""

    def get(self, key: str) -> MappingDecision | None:
        """필드 매핑 캐시에서 필요한 get 결과를 읽어 온다."""
        ...

    def set(self, key: str, decision: MappingDecision) -> None:
        """필드 매핑 캐시의 set 변경을 저장 계층에 반영한다."""
        ...


class RedisClient(Protocol):
    """필드 매핑 캐시에서 외부 구현체가 제공할 메서드를 명시한다."""

    def get(self, name: str) -> bytes | str | None:
        """필드 매핑 캐시에서 필요한 get 결과를 읽어 온다."""
        ...

    def set(self, name: str, value: str) -> object:
        """필드 매핑 캐시의 set 변경을 저장 계층에 반영한다."""
        ...


class InMemoryMappingCache:
    """필드 매핑 캐시에서 함께 이동해야 하는 상태를 묶는다."""

    def __init__(self) -> None:
        """필드 매핑 캐시 인스턴스가 쓸 client, store, cache 참조를 연결한다."""
        self._items: dict[str, MappingDecision] = {}

    def get(self, key: str) -> MappingDecision | None:
        """필드 매핑 캐시에서 필요한 get 결과를 읽어 온다."""
        return self._items.get(key)

    def set(self, key: str, decision: MappingDecision) -> None:
        """필드 매핑 캐시의 set 변경을 저장 계층에 반영한다."""
        self._items[key] = decision


class RedisMappingCache:
    """필드 매핑 캐시에서 함께 이동해야 하는 상태를 묶는다."""

    def __init__(
        self,
        client: RedisClient | None = None,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """필드 매핑 캐시 인스턴스가 쓸 client, store, cache 참조를 연결한다."""
        self._client: RedisClient
        if client is None:
            import redis

            self._client = redis.Redis.from_url(redis_url)
        else:
            self._client = client

    def get(self, key: str) -> MappingDecision | None:
        """필드 매핑 캐시에서 필요한 get 결과를 읽어 온다."""
        payload = self._client.get(key)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode()
        return MappingDecision(**json.loads(payload))

    def set(self, key: str, decision: MappingDecision) -> None:
        """필드 매핑 캐시의 set 변경을 저장 계층에 반영한다."""
        self._client.set(key, json.dumps(asdict(decision)))


def cache_key(source_url: str, index: str, field_name: str, field_type: str) -> str:
    """source URL, index, field, type을 안정적인 Redis key로 결합한다."""
    return "|".join([source_url, index, field_name, field_type])
