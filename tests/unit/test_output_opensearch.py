from scala_backend.output.opensearch import OpenSearchLoader


class FakeOpenSearchClient:
    def __init__(self) -> None:
        self.index_calls: list[dict[str, object]] = []
        self.docs: dict[str, dict[str, object]] = {}

    def index(self, *, index: str, id: str, body: dict[str, object]) -> dict[str, str]:
        self.index_calls.append({"index": index, "id": id, "body": body})
        self.docs[id] = body
        return {"_id": id}

    def get(self, *, index: str, id: str) -> dict[str, object]:
        return {"found": id in self.docs, "_source": self.docs.get(id, {})}


def test_opensearch_loader_indexes_normalized_document() -> None:
    client = FakeOpenSearchClient()
    loader = OpenSearchLoader(client=client)
    doc = {"activity_name": "allow", "src_endpoint": {"ip": "10.0.0.5"}}

    doc_id = loader.index_normalized("scala-normalized", "scala-1", doc)

    assert doc_id == "scala-1"
    assert client.index_calls == [
        {"index": "scala-normalized", "id": "scala-1", "body": doc}
    ]


def test_opensearch_loader_fetches_normalized_document_by_id() -> None:
    client = FakeOpenSearchClient()
    loader = OpenSearchLoader(client=client)
    doc = {"activity_name": "allow"}
    loader.index_normalized("scala-normalized", "scala-1", doc)

    found = loader.fetch_by_id("scala-normalized", "scala-1")
    missing = loader.fetch_by_id("scala-normalized", "missing")

    assert found == doc
    assert missing is None
