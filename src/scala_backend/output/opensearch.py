from __future__ import annotations

import importlib
from typing import Protocol, cast

from scala_backend.models import JsonObject


class OpenSearchClient(Protocol):
    def index(self, *, index: str, id: str, body: JsonObject) -> JsonObject: ...

    def get(self, *, index: str, id: str) -> JsonObject: ...


class OpenSearchLoader:
    def __init__(
        self,
        url: str | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        client: OpenSearchClient | None = None,
    ) -> None:
        self._client = client or self._make_client(url, username, password)

    def index_normalized(
        self,
        index: str,
        doc_id: str,
        document: JsonObject,
    ) -> str:
        response = self._client.index(index=index, id=doc_id, body=document)
        value = response.get("_id", doc_id)
        return str(value)

    def fetch_by_id(self, index: str, doc_id: str) -> JsonObject | None:
        response = self._client.get(index=index, id=doc_id)
        if response.get("found", True) is False:
            return None
        source = response.get("_source")
        return source if isinstance(source, dict) else None

    def _make_client(
        self,
        url: str | None,
        username: str | None,
        password: str | None,
    ) -> OpenSearchClient:
        module = importlib.import_module("opensearchpy")
        client_cls = module.OpenSearch
        auth = (username, password) if username and password else None
        return cast(
            OpenSearchClient,
            client_cls(hosts=[url or "http://localhost:9200"], http_auth=auth),
        )
