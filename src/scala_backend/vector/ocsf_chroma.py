from __future__ import annotations

import importlib
from pathlib import Path
from typing import Protocol

from scala_backend.ocsf import OcsfField
from scala_backend.providers import EmbeddingProvider


class ChromaCollection(Protocol):
    def count(self) -> int: ...

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str]],
        embeddings: list[list[float]],
    ) -> None: ...

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, list[list[dict[str, str]]]]: ...


class ChromaClient(Protocol):
    def get_or_create_collection(self, name: str) -> ChromaCollection: ...


class ChromaOcsfIndex:
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
        self._provider = embedding_provider
        self._model = model
        self._collection = (
            client or self._make_client(path=path, host=host, port=port)
        ).get_or_create_collection(collection_name)

    def upsert(self, fields: list[OcsfField]) -> int:
        documents = [_field_text(field) for field in fields]
        self._collection.upsert(
            ids=[field.name for field in fields],
            documents=documents,
            metadatas=[_metadata(field) for field in fields],
            embeddings=self._provider.embed(documents, self._model),
        )
        return len(fields)

    def query(self, text: str, top_k: int = 3) -> list[OcsfField]:
        result = self._collection.query(
            query_embeddings=self._provider.embed([text], self._model),
            n_results=top_k,
            include=["metadatas"],
        )
        return [_field_from_metadata(item) for item in result.get("metadatas", [[]])[0]]

    def count(self) -> int:
        return self._collection.count()

    def _make_client(
        self,
        *,
        path: Path | None,
        host: str | None,
        port: int,
    ) -> ChromaClient:
        chromadb = importlib.import_module("chromadb")
        if host is not None:
            return chromadb.HttpClient(host=host, port=port)
        return chromadb.PersistentClient(path=str(path or Path(".chroma")))


def _field_text(field: OcsfField) -> str:
    return f"{field.name} {field.type_name} {field.caption} {field.description}"


def _metadata(field: OcsfField) -> dict[str, str]:
    return {
        "name": field.name,
        "type_name": field.type_name,
        "caption": field.caption,
        "description": field.description,
    }


def _field_from_metadata(data: dict[str, str]) -> OcsfField:
    return OcsfField(
        name=data["name"],
        type_name=data["type_name"],
        caption=data["caption"],
        description=data["description"],
    )
