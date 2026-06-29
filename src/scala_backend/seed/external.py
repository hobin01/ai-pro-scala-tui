from __future__ import annotations

import importlib
import json
from collections.abc import Iterable, Mapping
from contextlib import suppress
from typing import Protocol, cast

from scala_backend.models import JsonObject


class ElasticsearchSeedClient(Protocol):
    """외부 SIEM seed에서 외부 구현체가 제공할 메서드를 명시한다."""

    def index(self, *, index: str, id: str, document: JsonObject) -> JsonObject:
        """외부 SIEM seed의 index 변경을 저장 계층에 반영한다."""
        ...


class SplunkIndex(Protocol):
    """외부 SIEM seed에서 함께 이동해야 하는 상태를 묶는다."""

    def submit(self, event: str) -> None:
        """외부 SIEM seed의 submit 변경을 저장 계층에 반영한다."""
        ...


class SplunkSeedService(Protocol):
    """외부 SIEM seed에서 함께 이동해야 하는 상태를 묶는다."""

    @property
    def indexes(self) -> Mapping[str, SplunkIndex]:
        """Splunk SDK service에서 index collection을 노출한다."""
        ...


def seed_elasticsearch_documents(
    client: ElasticsearchSeedClient,
    index: str,
    documents: list[JsonObject],
) -> list[str]:
    """외부 SIEM seed의 seed elasticsearch documents 변경을 저장 계층에 반영한다."""
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
    """외부 SIEM seed의 seed splunk events 변경을 저장 계층에 반영한다."""
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
    """외부 SIEM seed의 seeded splunk ids 보조 경로를 분리한다."""
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
