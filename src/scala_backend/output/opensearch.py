from __future__ import annotations

import importlib
from typing import Protocol, cast

from scala_backend.models import JsonObject


class OpenSearchClient(Protocol):
    """OpenSearch 적재에서 외부 구현체가 제공할 메서드를 명시한다."""

    def index(self, *, index: str, id: str, body: JsonObject) -> JsonObject:
        """OpenSearch 적재의 index 변경을 저장 계층에 반영한다."""
        ...

    def get(self, *, index: str, id: str) -> JsonObject:
        """OpenSearch 적재에서 필요한 get 결과를 읽어 온다."""
        ...


class OpenSearchLoader:
    """정규화 문서를 OpenSearch에 쓰고 lineage 조회용 문서를 읽는다."""

    def __init__(
        self,
        url: str | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        client: OpenSearchClient | None = None,
    ) -> None:
        """주입된 client가 없으면 URL/auth로 OpenSearch client를 만든다."""
        self._client = client or self._make_client(url, username, password)

    def index_normalized(
        self,
        index: str,
        doc_id: str,
        document: JsonObject,
    ) -> str:
        """정규화 문서를 OpenSearch index에 idempotent id로 적재한다."""
        response = self._client.index(index=index, id=doc_id, body=document)
        value = response.get("_id", doc_id)
        return str(value)

    def fetch_by_id(self, index: str, doc_id: str) -> JsonObject | None:
        """OpenSearch _id로 _source 문서를 조회한다."""
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
        """opensearchpy client를 loader protocol 형태로 생성한다."""
        module = importlib.import_module("opensearchpy")
        client_cls = module.OpenSearch
        auth = (username, password) if username and password else None
        return cast(
            OpenSearchClient,
            client_cls(hosts=[url or "http://localhost:9200"], http_auth=auth),
        )
