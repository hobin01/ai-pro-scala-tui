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
                types[key] = _json_type(value)
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
