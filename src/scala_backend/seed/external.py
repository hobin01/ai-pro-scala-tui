from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from scala_backend.models import JsonObject


class ElasticsearchSeedClient(Protocol):
    def index(self, *, index: str, id: str, document: JsonObject) -> JsonObject: ...


class SplunkIndex(Protocol):
    def submit(self, event: str) -> None: ...


class SplunkSeedService(Protocol):
    @property
    def indexes(self) -> Mapping[str, SplunkIndex]: ...


def seed_elasticsearch_documents(
    client: ElasticsearchSeedClient,
    index: str,
    documents: list[JsonObject],
) -> list[str]:
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
    ids: list[str] = []
    target = service.indexes[index]
    for offset, event in enumerate(events, start=1):
        doc_id = str(event.get("source_doc_id", f"splunk-seed-{offset}"))
        target.submit(json.dumps(event | {"source_doc_id": doc_id}, sort_keys=True))
        ids.append(doc_id)
    return ids
