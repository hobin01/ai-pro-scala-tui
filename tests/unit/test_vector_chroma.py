from typing import Any, cast

import pytest

from scala_backend.app_factory import create_ocsf_index
from scala_backend.config import BackendConfig
from scala_backend.ocsf import OcsfField
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


class FakeEmbeddingProvider:
    """Chroma 테스트에서 deterministic embedding을 만드는 provider다."""

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """입력 텍스트와 model 길이로 deterministic embedding을 만든다."""
        return [[float(len(text)), float(len(model))] for text in texts]


class FakeCollection:
    """Chroma collection upsert/query 계약을 메모리 record로 대신한다."""

    def __init__(self) -> None:
        """테스트가 관찰할 내부 상태를 초기화한다."""
        self.records: dict[str, dict[str, str]] = {}
        self.query_embeddings: list[list[float]] = []

    def count(self) -> int:
        """fake collection 또는 bootstrap index의 현재 row 수를 반환한다."""
        return len(self.records)

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str]],
        embeddings: list[list[float]],
    ) -> None:
        """upsert된 metadata 또는 OCSF field 목록을 기록한다."""
        for index, field_id in enumerate(ids):
            self.records[field_id] = metadatas[index]

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, list[list[dict[str, str]]]]:
        """저장된 metadata를 Chroma query 응답 형태로 반환한다."""
        self.query_embeddings = query_embeddings
        return {"metadatas": [[self.records["src_endpoint.ip"]]][:n_results]}


class FakeChromaClient:
    """테스트 collection을 반환하는 Chroma client 대역이다."""

    def __init__(self) -> None:
        """테스트가 관찰할 내부 상태를 초기화한다."""
        self.collection = FakeCollection()

    def get_or_create_collection(self, name: str) -> FakeCollection:
        """항상 같은 fake collection을 반환한다."""
        return self.collection


def test_chroma_ocsf_index_upserts_and_queries_fields() -> None:
    """테스트 목적: OCSF schema token 검색."""
    client = FakeChromaClient()
    index = ChromaOcsfIndex(
        client=client,
        embedding_provider=FakeEmbeddingProvider(),
        model="text-embedding-3-small",
    )
    fields = [
        OcsfField(
            "src_endpoint.ip",
            "ip",
            "Source IP",
            "Source endpoint IP address",
        )
    ]

    count = index.upsert(fields)
    candidates = index.query("client source ip", top_k=1)

    assert count == 1
    assert candidates == fields
    assert client.collection.query_embeddings == [[16.0, 22.0]]


def test_app_factory_bootstraps_empty_ocsf_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """테스트 목적: OCSF schema token 검색."""
    fields = [
        OcsfField("src_endpoint.ip", "ip", "Source IP", "Source endpoint IP address")
    ]
    fake_index = FakeBootstrapIndex(count_value=0)

    def fields_for_version(version: str) -> list[OcsfField]:
        """요청 version이 fixture version일 때만 OCSF field를 반환한다."""
        return fields if version == "1.8.0" else []

    monkeypatch.setattr("scala_backend.app_factory.ChromaOcsfIndex", fake_index.factory)
    monkeypatch.setattr(
        "scala_backend.app_factory.load_official_ocsf_fields",
        fields_for_version,
        raising=False,
    )

    index = create_ocsf_index(
        BackendConfig(openai_api_key="sk-test"),
        FakeEmbeddingProvider(),
    )

    assert cast(object, index) is fake_index
    assert fake_index.upserted == fields


def test_app_factory_skips_ocsf_bootstrap_when_collection_has_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """테스트 목적: OCSF schema token 검색."""
    fake_index = FakeBootstrapIndex(count_value=3)

    def fields_for_version(version: str) -> list[OcsfField]:
        """요청 version이 fixture version일 때만 OCSF field를 반환한다."""
        del version
        return [OcsfField("src_endpoint.ip", "ip", "Source IP", "Source endpoint IP")]

    monkeypatch.setattr("scala_backend.app_factory.ChromaOcsfIndex", fake_index.factory)
    monkeypatch.setattr(
        "scala_backend.app_factory.load_official_ocsf_fields",
        fields_for_version,
        raising=False,
    )

    index = create_ocsf_index(
        BackendConfig(openai_api_key="sk-test"),
        FakeEmbeddingProvider(),
    )

    assert cast(object, index) is fake_index
    assert fake_index.upserted == []


class FakeBootstrapIndex:
    """app_factory가 bootstrap하는 OCSF field 목록을 기록하는 index다."""

    def __init__(self, count_value: int) -> None:
        """테스트가 관찰할 내부 상태를 초기화한다."""
        self.count_value = count_value
        self.upserted: list[OcsfField] = []

    def factory(self, **kwargs: Any) -> "FakeBootstrapIndex":
        """app_factory monkeypatch가 사용할 fake index instance를 반환한다."""
        del kwargs
        return self

    def count(self) -> int:
        """fake collection 또는 bootstrap index의 현재 row 수를 반환한다."""
        return self.count_value

    def upsert(self, fields: list[OcsfField]) -> int:
        """upsert된 metadata 또는 OCSF field 목록을 기록한다."""
        self.upserted = fields
        return len(fields)
