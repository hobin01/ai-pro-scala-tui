from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pytest

from scala_backend.cache import MappingDecision, cache_key
from scala_backend.config import BackendConfig
from scala_backend.evaluation.performance import (
    ES_NETWORK_INDEX,
    OPENSEARCH_INDEX,
    export_performance_results,
)


def test_export_performance_results_writes_runtime_actual_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis/PostgreSQL actual 결과가 평가 입력 파일로 export되는지 확인한다."""
    cache_payload = {
        cache_key(
            "http://elasticsearch:9200",
            ES_NETWORK_INDEX,
            "src_ip",
            "string",
        ): json.dumps(
            asdict(
                MappingDecision(
                    source_field="src_ip",
                    source_type="string",
                    action="map",
                    ocsf_field="src_endpoint.ip",
                    ocsf_type="ip",
                )
            ),
        ),
        cache_key(
            "http://elasticsearch:9200",
            "scala-es-network",
            "src_ip",
            "string",
        ): json.dumps({}),
    }
    redis_client = FakeRedisScanClient(cache_payload)
    cursor = FakeLineageCursor(
        rows=[
            (
                "elasticsearch",
                ES_NETWORK_INDEX,
                "es-network-000001",
                OPENSEARCH_INDEX,
                "os-1",
            ),
            (
                "elasticsearch",
                "scala-es-network",
                "dev-1",
                OPENSEARCH_INDEX,
                "dev-os-1",
            ),
        ]
    )
    monkeypatch.setattr(
        "scala_backend.evaluation.exporter.psycopg.connect",
        fake_lineage_connect(FakeLineageConnection(cursor)),
    )
    monkeypatch.setattr(
        "scala_backend.evaluation.exporter.importlib.import_module",
        fake_import_module(FakeRedisModule(FakeRedisFactory(redis_client))),
    )

    path = export_performance_results(
        BackendConfig(
            redis_url="redis://redis:6379/0",
            database_url="postgresql://postgres/scalas",
        ),
        tmp_path,
    )

    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual["field_mappings"] == [
        {
            "action": "map",
            "index": ES_NETWORK_INDEX,
            "ocsf_field": "src_endpoint.ip",
            "ocsf_type": "ip",
            "solution": "elasticsearch",
            "source_field": "src_ip",
            "source_type": "string",
        }
    ]
    assert actual["lineage"] == [
        {
            "opensearch_id": "os-1",
            "opensearch_index": OPENSEARCH_INDEX,
            "source_doc_id": "es-network-000001",
            "source_index": ES_NETWORK_INDEX,
            "source_solution": "elasticsearch",
        }
    ]


@dataclass
class FakeRedisScanClient:
    """exporter 테스트에서 Redis scan/get을 dict로 대신한다."""

    values: dict[str, str] = field(default_factory=dict)

    def scan_iter(self) -> list[str]:
        """fake Redis key 목록을 반환한다."""
        return list(self.values)

    def get(self, name: str) -> str | None:
        """fake Redis payload를 반환한다."""
        return self.values.get(name)


@dataclass
class FakeRedisFactory:
    """redis.Redis.from_url 대역이 반환할 client를 보관한다."""

    client: FakeRedisScanClient

    def from_url(self, _url: str) -> FakeRedisScanClient:
        """fake Redis client를 반환한다."""
        return self.client


@dataclass
class FakeRedisModule:
    """exporter가 동적 import할 redis module 대역이다."""

    Redis: FakeRedisFactory


@dataclass
class FakeLineageCursor:
    """PostgreSQL lineage query 결과를 보관하는 cursor 대역이다."""

    rows: list[tuple[str, str, str, str, str]]

    def __enter__(self) -> FakeLineageCursor:
        """context manager cursor 자신을 반환한다."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """context manager 종료 시 별도 처리를 하지 않는다."""

    def execute(self, _sql: str, _params: tuple[str]) -> None:
        """테스트에서는 SQL 실행 요청만 허용한다."""

    def fetchall(self) -> list[tuple[str, str, str, str, str]]:
        """준비된 lineage row 목록을 반환한다."""
        return self.rows


@dataclass
class FakeLineageConnection:
    """PostgreSQL connection context manager 대역이다."""

    cursor_result: FakeLineageCursor

    def __enter__(self) -> FakeLineageConnection:
        """context manager connection 자신을 반환한다."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """context manager 종료 시 별도 처리를 하지 않는다."""

    def cursor(self) -> FakeLineageCursor:
        """fake lineage cursor를 반환한다."""
        return self.cursor_result


def fake_import_module(module: FakeRedisModule) -> Callable[[str], FakeRedisModule]:
    """redis module import를 fake module로 바꾸는 callable을 만든다."""

    def import_module(name: str) -> FakeRedisModule:
        """redis 외 module import 요청은 테스트 실패로 처리한다."""
        if name != "redis":
            raise AssertionError(name)
        return module

    return import_module


def fake_lineage_connect(
    connection: FakeLineageConnection,
) -> Callable[[str], FakeLineageConnection]:
    """psycopg.connect를 fake connection에 묶는 callable을 만든다."""

    def connect(_url: str) -> FakeLineageConnection:
        """항상 같은 fake PostgreSQL connection을 반환한다."""
        return connection

    return connect
