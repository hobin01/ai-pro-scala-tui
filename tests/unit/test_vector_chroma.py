from scala_backend.ocsf import OcsfField
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


class FakeEmbeddingProvider:
    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        return [[float(len(text)), float(len(model))] for text in texts]


class FakeCollection:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, str]] = {}
        self.query_embeddings: list[list[float]] = []

    def count(self) -> int:
        return len(self.records)

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str]],
        embeddings: list[list[float]],
    ) -> None:
        for index, field_id in enumerate(ids):
            self.records[field_id] = metadatas[index]

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, list[list[dict[str, str]]]]:
        self.query_embeddings = query_embeddings
        return {"metadatas": [[self.records["src_endpoint.ip"]]][:n_results]}


class FakeChromaClient:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def get_or_create_collection(self, name: str) -> FakeCollection:
        return self.collection


def test_chroma_ocsf_index_upserts_and_queries_fields() -> None:
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
