from scala_backend.seed.external import (
    seed_elasticsearch_documents,
    seed_splunk_events,
)


class FakeElasticsearchClient:
    """FakeElasticsearchClient 호출 계약을 정의한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self.calls: list[dict[str, object]] = []

    def index(
        self, *, index: str, id: str, document: dict[str, object]
    ) -> dict[str, str]:
        """index 동작을 처리한다."""
        self.calls.append({"index": index, "id": id, "document": document})
        return {"_id": id}


class FakeSplunkIndex:
    """FakeSplunkIndex 테스트 대상을 표현한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self.events: list[str] = []

    def submit(self, event: str) -> None:
        """submit 동작을 처리한다."""
        self.events.append(event)


class FakeSplunkService:
    """FakeSplunkService 테스트 대상을 표현한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self.indexes = {"main": FakeSplunkIndex()}


def test_seed_elasticsearch_documents_indexes_with_stable_source_ids() -> None:
    """seed elasticsearch documents indexes with stable source ids 동작을 검증한다."""
    client = FakeElasticsearchClient()
    docs = [{"message": "allowed"}, {"message": "blocked"}]

    ids = seed_elasticsearch_documents(client, "logs-2026", docs)

    assert ids == ["es-seed-1", "es-seed-2"]
    assert client.calls[0]["document"] == {"message": "allowed"}


def test_seed_splunk_events_submits_json_events() -> None:
    """seed splunk events submits json events 동작을 검증한다."""
    service = FakeSplunkService()

    ids = seed_splunk_events(service, "main", [{"clientip": "10.0.0.5"}])

    assert ids == ["splunk-seed-1"]
    assert '"source_doc_id": "splunk-seed-1"' in service.indexes["main"].events[0]
