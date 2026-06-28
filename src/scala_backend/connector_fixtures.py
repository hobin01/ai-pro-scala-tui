from __future__ import annotations

from collections.abc import Iterable

from scala_backend.models import FieldSample, JsonValue, RawDocument


class FixtureConnector:
    def __init__(self, solution: str, documents: list[RawDocument]) -> None:
        self.solution = solution
        self._documents = documents

    def fetch_schema_samples(self, index: str, limit: int = 5) -> list[FieldSample]:
        rows = [doc for doc in self._documents if doc.source_index == index]
        fields: dict[str, list[JsonValue]] = {}
        types: dict[str, str] = {}
        for row in rows:
            for key, value in row.body.items():
                samples = fields.setdefault(key, [])
                if len(samples) < limit:
                    samples.append(value)
                types[key] = _json_type(value)
        return [
            FieldSample(name=name, type=types[name], samples=samples[:limit])
            for name, samples in sorted(fields.items())
        ]

    def iter_documents(self, index: str) -> Iterable[RawDocument]:
        return (doc for doc in self._documents if doc.source_index == index)

    def fetch_raw_document(self, index: str, doc_id: str) -> RawDocument | None:
        return next(
            (
                doc
                for doc in self._documents
                if doc.source_index == index and doc.source_doc_id == doc_id
            ),
            None,
        )


def default_connectors() -> dict[str, FixtureConnector]:
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
