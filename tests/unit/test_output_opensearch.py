from scala_backend.output.opensearch import OpenSearchLoader


class FakeOpenSearchClient:
    """OpenSearchLoader가 보내는 index/get 호출을 메모리에 기록한다."""

    def __init__(self) -> None:
        """OpenSearch 대역의 in-memory index 저장소를 초기화한다."""
        self.index_calls: list[dict[str, object]] = []
        self.docs: dict[str, dict[str, object]] = {}

    def index(self, *, index: str, id: str, body: dict[str, object]) -> dict[str, str]:
        """index API 호출 문서를 in-memory 저장소에 기록한다."""
        self.index_calls.append({"index": index, "id": id, "body": body})
        self.docs[id] = body
        return {"_id": id}

    def get(self, *, index: str, id: str) -> dict[str, object]:
        """get API 호출 id로 in-memory 문서를 반환한다."""
        return {"found": id in self.docs, "_source": self.docs.get(id, {})}


def test_opensearch_loader_indexes_normalized_document() -> None:
    """OpenSearch loader가 정규화 문서를 대상 index에 적재하는지 확인한다."""
    client = FakeOpenSearchClient()
    loader = OpenSearchLoader(client=client)
    doc = {"activity_name": "allow", "src_endpoint": {"ip": "10.0.0.5"}}

    doc_id = loader.index_normalized("scala-normalized", "scala-1", doc)

    assert doc_id == "scala-1"
    assert client.index_calls == [
        {"index": "scala-normalized", "id": "scala-1", "body": doc}
    ]


def test_opensearch_loader_fetches_normalized_document_by_id() -> None:
    """OpenSearch loader가 normalized document id로 단건 조회하는지 확인한다."""
    client = FakeOpenSearchClient()
    loader = OpenSearchLoader(client=client)
    doc = {"activity_name": "allow"}
    loader.index_normalized("scala-normalized", "scala-1", doc)

    found = loader.fetch_by_id("scala-normalized", "scala-1")
    missing = loader.fetch_by_id("scala-normalized", "missing")

    assert found == doc
    assert missing is None
