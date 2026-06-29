from __future__ import annotations

import importlib
from pathlib import Path
from typing import Protocol, cast

from scala_backend.ocsf import OcsfField
from scala_backend.providers import EmbeddingProvider


class ChromaCollection(Protocol):
    """ChromaDB OCSF 검색에서 함께 이동해야 하는 상태를 묶는다."""

    def count(self) -> int:
        """ChromaDB OCSF 검색에서 필요한 count 결과를 읽어 온다."""
        ...

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str]],
        embeddings: list[list[float]],
    ) -> None:
        """ChromaDB OCSF 검색의 upsert 변경을 저장 계층에 반영한다."""
        ...

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, list[list[dict[str, str]]]]:
        """query embedding으로 Chroma collection에서 OCSF field metadata를 찾는다."""
        ...


class ChromaClient(Protocol):
    """ChromaDB OCSF 검색에서 외부 구현체가 제공할 메서드를 명시한다."""

    def get_or_create_collection(self, name: str) -> ChromaCollection:
        """ChromaDB OCSF 검색에서 필요한 get or create collection 결과를 읽어 온다."""
        ...


class ChromaOcsfIndex:
    """ChromaDB OCSF 검색에서 함께 이동해야 하는 상태를 묶는다."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        model: str,
        collection_name: str = "ocsf-fields",
        client: ChromaClient | None = None,
        path: Path | None = None,
        host: str | None = None,
        port: int = 8000,
    ) -> None:
        """Chroma OCSF index 인스턴스가 쓸 client, store, cache 참조를 연결한다."""
        self._provider = embedding_provider
        self._model = model
        self._collection = (
            client or self._make_client(path=path, host=host, port=port)
        ).get_or_create_collection(collection_name)

    def upsert(self, fields: list[OcsfField]) -> int:
        """ChromaDB OCSF 검색의 upsert 변경을 저장 계층에 반영한다."""
        documents = [_field_text(field) for field in fields]
        self._collection.upsert(
            ids=[field.name for field in fields],
            documents=documents,
            metadatas=[_metadata(field) for field in fields],
            embeddings=self._provider.embed(documents, self._model),
        )
        return len(fields)

    def query(self, text: str, top_k: int = 3) -> list[OcsfField]:
        """query embedding으로 Chroma collection에서 OCSF field metadata를 찾는다."""
        result = self._collection.query(
            query_embeddings=self._provider.embed([text], self._model),
            n_results=top_k,
            include=["metadatas"],
        )
        return [_field_from_metadata(item) for item in result.get("metadatas", [[]])[0]]

    def count(self) -> int:
        """ChromaDB OCSF 검색에서 필요한 count 결과를 읽어 온다."""
        return self._collection.count()

    def _make_client(
        self,
        *,
        path: Path | None,
        host: str | None,
        port: int,
    ) -> ChromaClient:
        """ChromaDB OCSF 검색의 make client 보조 경로를 분리한다."""
        chromadb = importlib.import_module("chromadb")
        if host is not None:
            return cast(ChromaClient, chromadb.HttpClient(host=host, port=port))
        return cast(
            ChromaClient,
            chromadb.PersistentClient(path=str(path or Path(".chroma"))),
        )


def _field_text(field: OcsfField) -> str:
    """ChromaDB OCSF 검색의 field text 보조 경로를 분리한다."""
    return f"{field.name} {field.type_name} {field.caption} {field.description}"


def _metadata(field: OcsfField) -> dict[str, str]:
    """ChromaDB OCSF 검색의 metadata 보조 경로를 분리한다."""
    return {
        "name": field.name,
        "type_name": field.type_name,
        "caption": field.caption,
        "description": field.description,
    }


def _field_from_metadata(data: dict[str, str]) -> OcsfField:
    """ChromaDB OCSF 검색의 field from metadata 보조 경로를 분리한다."""
    return OcsfField(
        name=data["name"],
        type_name=data["type_name"],
        caption=data["caption"],
        description=data["description"],
    )
