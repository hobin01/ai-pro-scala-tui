from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Final

from scala_backend.ids import stable_opensearch_id
from scala_backend.models import JsonObject, RawDocument

from .sources import (
    ES_ENDPOINT_INDEX,
    ES_NETWORK_INDEX,
    SPLUNK_AUTH_INDEX,
    SPLUNK_WEB_INDEX,
    elasticsearch_performance_batches,
    splunk_performance_batches,
)
from .types import DatasetPaths, LineageTruth, MappingTruth, PerformanceDatasetError

DATASET_NAME: Final = "scala-performance-v1"
OPENSEARCH_INDEX: Final = "scala-performance-normalized"
ES: Final = "elasticsearch"
SPLUNK: Final = "splunk"
STRING: Final = "string"
INTEGER: Final = "integer"
MAP: Final = "map"
KEEP_RAW: Final = "keep_raw"
type MappingTruthRow = tuple[str, str, str, str, str, str | None, str | None]
MAPPING_TRUTH_ROWS: Final[tuple[MappingTruthRow, ...]] = (
    (ES, ES_NETWORK_INDEX, "@timestamp", STRING, MAP, "time", STRING),
    (ES, ES_NETWORK_INDEX, "src_ip", STRING, MAP, "src_endpoint.ip", "ip"),
    (ES, ES_NETWORK_INDEX, "source_port", INTEGER, MAP, "src_endpoint.port", INTEGER),
    (ES, ES_NETWORK_INDEX, "dst_ip", STRING, MAP, "dst_endpoint.ip", "ip"),
    (ES, ES_NETWORK_INDEX, "dst_port", INTEGER, MAP, "dst_endpoint.port", INTEGER),
    (ES, ES_NETWORK_INDEX, "protocol", STRING, MAP, "network.protocol_name", STRING),
    (ES, ES_NETWORK_INDEX, "bytes_in", INTEGER, MAP, "traffic.bytes_in", INTEGER),
    (ES, ES_NETWORK_INDEX, "bytes_out", INTEGER, MAP, "traffic.bytes_out", INTEGER),
    (ES, ES_NETWORK_INDEX, "username", STRING, MAP, "actor.user.name", STRING),
    (ES, ES_NETWORK_INDEX, "vendor_weird_flag", STRING, KEEP_RAW, None, None),
    (ES, ES_ENDPOINT_INDEX, "time", STRING, MAP, "time", STRING),
    (ES, ES_ENDPOINT_INDEX, "client_ip", STRING, MAP, "src_endpoint.ip", "ip"),
    (ES, ES_ENDPOINT_INDEX, "remote_addr", STRING, MAP, "dst_endpoint.ip", "ip"),
    (
        ES,
        ES_ENDPOINT_INDEX,
        "destination_port",
        STRING,
        MAP,
        "dst_endpoint.port",
        INTEGER,
    ),
    (ES, ES_ENDPOINT_INDEX, "process_name", STRING, MAP, "process.name", STRING),
    (ES, ES_ENDPOINT_INDEX, "process_pid", INTEGER, MAP, "process.pid", INTEGER),
    (
        ES,
        ES_ENDPOINT_INDEX,
        "process_command_line",
        STRING,
        MAP,
        "process.cmd_line",
        STRING,
    ),
    (
        ES,
        ES_ENDPOINT_INDEX,
        "endpoint_hostname",
        STRING,
        MAP,
        "device.hostname",
        STRING,
    ),
    (ES, ES_ENDPOINT_INDEX, "typooedEDRField", STRING, KEEP_RAW, None, None),
    (SPLUNK, SPLUNK_WEB_INDEX, "_time", STRING, MAP, "time", STRING),
    (SPLUNK, SPLUNK_WEB_INDEX, "_raw", STRING, MAP, "raw_data", STRING),
    (SPLUNK, SPLUNK_WEB_INDEX, "time", STRING, MAP, "time", STRING),
    (SPLUNK, SPLUNK_WEB_INDEX, "clientip", STRING, MAP, "src_endpoint.ip", "ip"),
    (SPLUNK, SPLUNK_WEB_INDEX, "dest_ip", STRING, MAP, "dst_endpoint.ip", "ip"),
    (SPLUNK, SPLUNK_WEB_INDEX, "dest_port", STRING, MAP, "dst_endpoint.port", INTEGER),
    (
        SPLUNK,
        SPLUNK_WEB_INDEX,
        "method",
        STRING,
        MAP,
        "http_request.http_method",
        STRING,
    ),
    (
        SPLUNK,
        SPLUNK_WEB_INDEX,
        "http_status",
        STRING,
        MAP,
        "http_response.code",
        INTEGER,
    ),
    (
        SPLUNK,
        SPLUNK_WEB_INDEX,
        "user_agent",
        STRING,
        MAP,
        "http_request.user_agent",
        STRING,
    ),
    (SPLUNK, SPLUNK_WEB_INDEX, "wafMysteryColumn", STRING, KEEP_RAW, None, None),
    (SPLUNK, SPLUNK_AUTH_INDEX, "_time", STRING, MAP, "time", STRING),
    (SPLUNK, SPLUNK_AUTH_INDEX, "_raw", STRING, MAP, "raw_data", STRING),
    (SPLUNK, SPLUNK_AUTH_INDEX, "time", STRING, MAP, "time", STRING),
    (SPLUNK, SPLUNK_AUTH_INDEX, "source_ip", STRING, MAP, "src_endpoint.ip", "ip"),
    (SPLUNK, SPLUNK_AUTH_INDEX, "dest_port", STRING, MAP, "dst_endpoint.port", INTEGER),
    (SPLUNK, SPLUNK_AUTH_INDEX, "user", STRING, MAP, "actor.user.name", STRING),
    (SPLUNK, SPLUNK_AUTH_INDEX, "user_id", STRING, MAP, "actor.user.uid", STRING),
    (SPLUNK, SPLUNK_AUTH_INDEX, "auth_protocol", STRING, MAP, "auth_protocol", STRING),
    (SPLUNK, SPLUNK_AUTH_INDEX, "auth_method", STRING, MAP, "auth_type", STRING),
    (
        SPLUNK,
        SPLUNK_AUTH_INDEX,
        "DestinationPort",
        STRING,
        MAP,
        "dst_endpoint.port",
        INTEGER,
    ),
)


def generate_performance_dataset(root: Path, count: int = 1000) -> DatasetPaths:
    """성능 지표 측정용 원천 데이터와 정답지를 결정적으로 생성한다."""
    if count < 1:
        raise PerformanceDatasetError("count must be greater than zero")
    root.mkdir(parents=True, exist_ok=True)
    elasticsearch_batches = elasticsearch_performance_batches(count)
    splunk_batches = splunk_performance_batches(count)
    _write_source_batches(root / "elasticsearch", elasticsearch_batches)
    _write_source_batches(root / "splunk", splunk_batches)
    mappings = performance_mapping_truth()
    lineages = _lineage_truth(elasticsearch_batches, splunk_batches)
    truth_path = root / "answer_key.json"
    actual_results_path = root / "actual_results.json"
    manifest_path = root / "dataset_manifest.json"
    metrics_path = root / "metrics.json"
    _write_json(
        truth_path,
        {
            "dataset": DATASET_NAME,
            "field_mappings": [asdict(row) for row in mappings],
            "lineage": [asdict(row) for row in lineages],
            "thresholds": {
                "field_mapping_precision": 0.95,
                "field_mapping_recall": 0.95,
                "lineage_traceability": 1.0,
            },
        },
    )
    _write_json(
        manifest_path,
        {
            "dataset": DATASET_NAME,
            "elasticsearch_indices": list(elasticsearch_batches),
            "splunk_indices": list(splunk_batches),
            "elasticsearch_count": _batch_count(elasticsearch_batches),
            "splunk_count": _batch_count(splunk_batches),
            "answer_key": truth_path.name,
            "actual_results": actual_results_path.name,
            "metrics": metrics_path.name,
        },
    )
    return DatasetPaths(
        root=root,
        truth_path=truth_path,
        actual_results_path=actual_results_path,
        manifest_path=manifest_path,
        metrics_path=metrics_path,
        elasticsearch_count=_batch_count(elasticsearch_batches),
        splunk_count=_batch_count(splunk_batches),
    )


def performance_mapping_truth() -> list[MappingTruth]:
    """평가 dataset의 source field별 정답 mapping 목록을 반환한다."""
    return [MappingTruth(*row) for row in MAPPING_TRUTH_ROWS]


def _write_source_batches(root: Path, batches: dict[str, list[JsonObject]]) -> None:
    """source별 JSONL 파일을 index 이름 기준으로 쓴다."""
    root.mkdir(parents=True, exist_ok=True)
    for index, docs in batches.items():
        path = root / f"{index}.jsonl"
        lines = [json.dumps(doc, ensure_ascii=False, sort_keys=True) for doc in docs]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _lineage_truth(
    elasticsearch_batches: dict[str, list[JsonObject]],
    splunk_batches: dict[str, list[JsonObject]],
) -> list[LineageTruth]:
    """source batch 문서마다 기대 OpenSearch id를 계산한다."""
    rows: list[LineageTruth] = []
    for solution, batches in (
        ("elasticsearch", elasticsearch_batches),
        ("splunk", splunk_batches),
    ):
        for index, docs in batches.items():
            for doc in docs:
                source_doc_id = str(doc["source_doc_id"])
                raw = RawDocument(solution, index, source_doc_id, doc)
                rows.append(
                    LineageTruth(
                        solution,
                        index,
                        source_doc_id,
                        OPENSEARCH_INDEX,
                        stable_opensearch_id(raw),
                    )
                )
    return rows


def _batch_count(batches: dict[str, list[JsonObject]]) -> int:
    """source batch 전체 문서 수를 합산한다."""
    return sum(len(docs) for docs in batches.values())


def _write_json(path: Path, payload: JsonObject) -> None:
    """JSON 산출물을 사람이 읽기 쉬운 형태로 쓴다."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
