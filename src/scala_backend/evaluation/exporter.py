from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, TypeGuard

import psycopg

from scala_backend.config import BackendConfig
from scala_backend.models import JsonObject

from .dataset import OPENSEARCH_INDEX
from .sources import (
    ES_ENDPOINT_INDEX,
    ES_NETWORK_INDEX,
    SPLUNK_AUTH_INDEX,
    SPLUNK_WEB_INDEX,
)
from .types import LineageTruth, MappingTruth, PerformanceDatasetError

DATASET_NAME = "scala-performance-v1"
PERFORMANCE_SOURCE_INDEX_TO_SOLUTION = {
    ES_NETWORK_INDEX: "elasticsearch",
    ES_ENDPOINT_INDEX: "elasticsearch",
    SPLUNK_WEB_INDEX: "splunk",
    SPLUNK_AUTH_INDEX: "splunk",
}


class RedisScanClient(Protocol):
    """성능 결과 export에 필요한 Redis scan/get 최소 계약이다."""

    def scan_iter(self) -> Iterable[bytes | str]:
        """Redis key 전체를 순회한다."""
        ...

    def get(self, name: str) -> bytes | str | None:
        """Redis key의 raw payload를 읽는다."""
        ...


def export_performance_results(config: BackendConfig, output_dir: Path) -> Path:
    """실행된 performance pipeline의 actual mapping/lineage 결과를 파일로 쓴다."""
    if config.redis_url == "memory://":
        raise PerformanceDatasetError("performance export requires Redis runtime")
    if config.database_url == "memory://":
        raise PerformanceDatasetError("performance export requires PostgreSQL runtime")
    mappings = _redis_mapping_rows(config.redis_url)
    lineages = _postgres_lineage_rows(config.database_url)
    path = output_dir / "actual_results.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        path,
        {
            "dataset": DATASET_NAME,
            "field_mappings": [asdict(row) for row in mappings],
            "lineage": [asdict(row) for row in lineages],
        },
    )
    return path


def _redis_mapping_rows(redis_url: str) -> list[MappingTruth]:
    """Redis mapping cache에서 performance index의 actual mapping을 추출한다."""
    client = _redis_scan_client(redis_url)
    rows: list[MappingTruth] = []
    for raw_key in client.scan_iter():
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        _, index, source_field, source_type = _parse_cache_key(key)
        solution = PERFORMANCE_SOURCE_INDEX_TO_SOLUTION.get(index)
        if solution is None:
            continue
        payload = client.get(key)
        if payload is None:
            continue
        decision = _mapping_decision_payload(payload, key)
        rows.append(
            MappingTruth(
                solution=solution,
                index=index,
                source_field=str(decision.get("source_field", source_field)),
                source_type=str(decision.get("source_type", source_type)),
                action=str(decision.get("action", "")),
                ocsf_field=_optional_str(decision.get("ocsf_field")),
                ocsf_type=_optional_str(decision.get("ocsf_type")),
            )
        )
    return sorted(rows, key=_mapping_sort_key)


def _redis_scan_client(redis_url: str) -> RedisScanClient:
    """동적 import한 redis module에서 scan/get client를 만든다."""
    redis_module = importlib.import_module("redis")
    redis_class = getattr(redis_module, "Redis", None)
    from_url = getattr(redis_class, "from_url", None)
    if not callable(from_url):
        raise PerformanceDatasetError("redis module missing Redis.from_url")
    from_url_fn: Callable[[str], object] = from_url
    client = from_url_fn(redis_url)
    if not _is_redis_scan_client(client):
        raise PerformanceDatasetError("redis client missing scan_iter/get")
    return client


def _is_redis_scan_client(value: object) -> TypeGuard[RedisScanClient]:
    """동적 Redis client가 exporter에 필요한 메서드를 갖췄는지 확인한다."""
    return callable(getattr(value, "scan_iter", None)) and callable(
        getattr(value, "get", None)
    )


def _postgres_lineage_rows(database_url: str) -> list[LineageTruth]:
    """PostgreSQL lineage metadata에서 performance index의 actual lineage를 읽는다."""
    rows: list[LineageTruth] = []
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT source_solution, source_index, source_doc_id, "
            "opensearch_index, opensearch_id "
            "FROM scala_data_lineage_metadata "
            "WHERE opensearch_index = %s "
            "ORDER BY source_solution, source_index, source_doc_id, opensearch_id",
            (OPENSEARCH_INDEX,),
        )
        for row in cursor.fetchall():
            source_solution, source_index, source_doc_id, os_index, os_id = row
            if source_index not in PERFORMANCE_SOURCE_INDEX_TO_SOLUTION:
                continue
            rows.append(
                LineageTruth(
                    source_solution=str(source_solution),
                    source_index=str(source_index),
                    source_doc_id=str(source_doc_id),
                    opensearch_index=str(os_index),
                    opensearch_id=str(os_id),
                )
            )
    return rows


def _parse_cache_key(key: str) -> tuple[str, str, str, str]:
    """Redis mapping cache key를 source URL, index, field, type으로 분해한다."""
    parts = key.split("|", 3)
    if len(parts) != 4:
        return "", "", "", ""
    return parts[0], parts[1], parts[2], parts[3]


def _mapping_decision_payload(payload: bytes | str, key: str) -> JsonObject:
    """Redis payload를 mapping decision JSON 객체로 변환한다."""
    text = payload.decode() if isinstance(payload, bytes) else payload
    value = json.loads(text)
    if not isinstance(value, dict):
        raise PerformanceDatasetError(f"invalid mapping payload for {key}")
    return value


def _optional_str(value: object) -> str | None:
    """JSON null과 문자열 값을 optional string으로 정리한다."""
    return value if isinstance(value, str) else None


def _mapping_sort_key(row: MappingTruth) -> tuple[str, str, str, str]:
    """actual mapping 산출물의 정렬 key를 만든다."""
    return (row.solution, row.index, row.source_field, row.source_type)


def _write_json(path: Path, payload: JsonObject) -> None:
    """JSON 산출물을 사람이 읽기 쉬운 형태로 쓴다."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
