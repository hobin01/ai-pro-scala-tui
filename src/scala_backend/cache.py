from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class MappingDecision:
    source_field: str
    source_type: str
    action: str
    ocsf_field: str | None
    ocsf_type: str | None


class MappingCache(Protocol):
    def get(self, key: str) -> MappingDecision | None: ...

    def set(self, key: str, decision: MappingDecision) -> None: ...


class RedisClient(Protocol):
    def get(self, name: str) -> bytes | str | None: ...

    def set(self, name: str, value: str) -> object: ...


class InMemoryMappingCache:
    def __init__(self) -> None:
        self._items: dict[str, MappingDecision] = {}

    def get(self, key: str) -> MappingDecision | None:
        return self._items.get(key)

    def set(self, key: str, decision: MappingDecision) -> None:
        self._items[key] = decision


class RedisMappingCache:
    def __init__(
        self,
        client: RedisClient | None = None,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        if client is None:
            import redis

            self._client = redis.Redis.from_url(redis_url)
        else:
            self._client = client

    def get(self, key: str) -> MappingDecision | None:
        payload = self._client.get(key)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode()
        return MappingDecision(**json.loads(payload))

    def set(self, key: str, decision: MappingDecision) -> None:
        self._client.set(key, json.dumps(asdict(decision)))


def cache_key(source_url: str, index: str, field_name: str, field_type: str) -> str:
    return "|".join([source_url, index, field_name, field_type])
