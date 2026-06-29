from __future__ import annotations

import importlib
import json
from collections.abc import Iterable, Mapping
from contextlib import suppress
from typing import Protocol, cast

from scala_backend.models import JsonObject


class ElasticsearchSeedClient(Protocol):
    """ElasticsearchSeedClient 호출 계약을 정의한다."""

    def index(self, *, index: str, id: str, document: JsonObject) -> JsonObject:
        """index 동작을 처리한다."""
        ...


class SplunkIndex(Protocol):
    """SplunkIndex 객체의 책임을 정의한다."""

    def submit(self, event: str) -> None:
        """submit 동작을 처리한다."""
        ...


class SplunkSeedService(Protocol):
    """SplunkSeedService 객체의 책임을 정의한다."""

    @property
    def indexes(self) -> Mapping[str, SplunkIndex]:
        """indexes 동작을 처리한다."""
        ...


def seed_elasticsearch_documents(
    client: ElasticsearchSeedClient,
    index: str,
    documents: list[JsonObject],
) -> list[str]:
    """seed elasticsearch documents 데이터를 시드한다."""
    ids: list[str] = []
    for offset, document in enumerate(documents, start=1):
        doc_id = str(document.get("source_doc_id", f"es-seed-{offset}"))
        client.index(index=index, id=doc_id, document=document)
        ids.append(doc_id)
    return ids


def seed_splunk_events(
    service: SplunkSeedService,
    index: str,
    events: list[JsonObject],
) -> list[str]:
    """seed splunk events 데이터를 시드한다."""
    ids = [
        str(event.get("source_doc_id", f"splunk-seed-{offset}"))
        for offset, event in enumerate(events, start=1)
    ]
    if _seeded_splunk_ids(service, index, ids) >= len(ids):
        return ids
    target = service.indexes[index]
    for doc_id, event in zip(ids, events, strict=True):
        target.submit(json.dumps(event | {"source_doc_id": doc_id}, sort_keys=True))
    return ids


def _seeded_splunk_ids(
    service: SplunkSeedService,
    index: str,
    expected_ids: list[str],
) -> int:
    """seeded splunk ids 내부 처리를 수행한다."""
    jobs = getattr(service, "jobs", None)
    export = getattr(jobs, "export", None)
    if export is None:
        return 0
    query = (
        f"search index={index} source_doc_id=splunk-seed-* "
        "| fields source_doc_id | dedup source_doc_id"
    )
    with suppress(Exception):
        stream = export(query, output_mode="json")
        results_module = importlib.import_module("splunklib.results")
        reader = cast(
            "Iterable[object]",
            results_module.JSONResultsReader(stream),
        )

        seen = {
            str(row.get("source_doc_id")) for row in reader if isinstance(row, dict)
        }
        return len(set(expected_ids) & seen)
    return 0
