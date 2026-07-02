from __future__ import annotations

from collections.abc import Iterable

from scala_backend.models import FieldSample, JsonValue, RawDocument
from scala_backend.normalization import expand_raw_json


class FixtureConnector:
    """메모리 RawDocument 목록으로 SIEM connector 계약을 구현한다."""

    def __init__(self, solution: str, documents: list[RawDocument]) -> None:
        """fixture solution 이름과 문서 목록을 저장한다."""
        self.solution = solution
        self._documents = documents

    def fetch_schema_samples(self, index: str, limit: int = 5) -> list[FieldSample]:
        """fixture 문서에서 field별 타입과 최대 limit개 sample을 수집한다."""
        rows = [doc for doc in self._documents if doc.source_index == index]
        fields: dict[str, list[JsonValue]] = {}
        types: dict[str, str] = {}
        for row in rows:
            for key, value in expand_raw_json(row.body).items():
                samples = fields.setdefault(key, [])
                if len(samples) < limit:
                    samples.append(value)
                current_type = types.get(key)
                next_type = _json_type(value)
                if current_type is None or (
                    current_type == "null" and next_type != "null"
                ):
                    types[key] = next_type
        return [
            FieldSample(name=name, type=types[name], samples=samples[:limit])
            for name, samples in sorted(fields.items())
        ]

    def iter_documents(self, index: str) -> Iterable[RawDocument]:
        """fixture 문서 중 요청 index에 속한 원본 문서만 반환한다."""
        return (doc for doc in self._documents if doc.source_index == index)

    def fetch_raw_document(self, index: str, doc_id: str) -> RawDocument | None:
        """fixture 저장 문서에서 doc_id와 일치하는 RawDocument를 찾는다."""
        return next(
            (
                doc
                for doc in self._documents
                if doc.source_index == index and doc.source_doc_id == doc_id
            ),
            None,
        )


def default_connectors() -> dict[str, FixtureConnector]:
    """메모리 ES/Splunk fixture connector 두 개를 반환한다."""
    return {
        "elasticsearch": FixtureConnector(
            "elasticsearch",
            [
                RawDocument(
                    "elasticsearch",
                    "logs-2026",
                    "es-1",
                    {
                        "src_ip": "10.0.0.5",
                        "dest_port": "443",
                        "action": "allow",
                        "empty": "",
                    },
                ),
                RawDocument(
                    "elasticsearch",
                    "scala-es-network",
                    "es-network-1",
                    {
                        "@timestamp": "2026-06-28T08:00:00Z",
                        "src_ip": "10.10.0.5",
                        "source_ip": "10.20.0.5",
                        "dst_ip": "172.16.0.10",
                        "dest_port": "443",
                        "dst_port": 80,
                        "action": "allow",
                        "severity": "informational",
                        "vendor_custom": "es-network-extra",
                    },
                ),
                RawDocument(
                    "elasticsearch",
                    "scala-es-endpoint",
                    "es-endpoint-1",
                    {
                        "time": "2026-06-28T09:00:00Z",
                        "client_ip": "192.168.1.5",
                        "remote_addr": "203.0.113.5",
                        "destination_port": "3389",
                        "status": "success",
                        "process_name": "ssh",
                        "parent_process": None,
                        "es_only_endpoint_flag": True,
                    },
                ),
            ],
        ),
        "splunk": FixtureConnector(
            "splunk",
            [
                RawDocument(
                    "splunk",
                    "main",
                    "_bkt-1:_cd-42",
                    {
                        "clientip": "192.168.1.20",
                        "port": "443",
                        "status": "allow",
                        "_time": "2026-06-28T08:00:00Z",
                        "nullable": None,
                    },
                ),
                RawDocument(
                    "splunk",
                    "security",
                    "security-1",
                    {
                        "_time": "2026-06-28T11:00:00Z",
                        "_raw": (
                            '{"source_ip": "10.40.0.5", '
                            '"dest_port": "445", "action": "allow"}'
                        ),
                        "source_ip": "10.40.0.5",
                        "sourceAddress": "10.41.0.5",
                        "DestinationPort": "1224",
                        "EventCode": 4624,
                        "splunk_only_security_flag": True,
                    },
                ),
            ],
        ),
    }


def _json_type(value: JsonValue) -> str:
    """fixture sample 값의 JSON 타입 이름을 계산한다."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"
