from scala_backend.seed.external import (
    seed_elasticsearch_documents,
    seed_splunk_events,
)


class FakeElasticsearchClient:
    """seed script가 Elasticsearch bulk payload를 보낼 client 대역이다."""

    def __init__(self) -> None:
        """테스트 목적: 개발 seed 데이터 중복 방지."""
        self.calls: list[dict[str, object]] = []

    def index(
        self, *, index: str, id: str, document: dict[str, object]
    ) -> dict[str, str]:
        """테스트 목적: 개발 seed 데이터 중복 방지."""
        self.calls.append({"index": index, "id": id, "document": document})
        return {"_id": id}


class FakeSplunkIndex:
    """Splunk seed가 submit할 event batch를 기록한다."""

    def __init__(self) -> None:
        """테스트 목적: 개발 seed 데이터 중복 방지."""
        self.events: list[str] = []

    def submit(self, event: str) -> None:
        """테스트 목적: 개발 seed 데이터 중복 방지."""
        self.events.append(event)


class FakeSplunkService:
    """seed script가 접근하는 Splunk index collection을 제공한다."""

    def __init__(self) -> None:
        """테스트 목적: 개발 seed 데이터 중복 방지."""
        self.indexes = {"main": FakeSplunkIndex()}


def test_seed_elasticsearch_documents_indexes_with_stable_source_ids() -> None:
    """테스트 목적: 개발 seed 데이터 중복 방지."""
    client = FakeElasticsearchClient()
    docs = [{"message": "allowed"}, {"message": "blocked"}]

    ids = seed_elasticsearch_documents(client, "logs-2026", docs)

    assert ids == ["es-seed-1", "es-seed-2"]
    assert client.calls[0]["document"] == {"message": "allowed"}


def test_seed_splunk_events_submits_json_events() -> None:
    """테스트 목적: 개발 seed 데이터 중복 방지."""
    service = FakeSplunkService()

    ids = seed_splunk_events(service, "main", [{"clientip": "10.0.0.5"}])

    assert ids == ["splunk-seed-1"]
    assert '"source_doc_id": "splunk-seed-1"' in service.indexes["main"].events[0]
