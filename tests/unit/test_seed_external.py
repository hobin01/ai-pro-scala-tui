from scala_backend.seed.external import (
    seed_elasticsearch_documents,
    seed_splunk_events,
)


class FakeElasticsearchClient:
    """seed script가 Elasticsearch bulk payload를 보낼 client 대역이다."""

    def __init__(self) -> None:
        """Elasticsearch seed 테스트가 기록할 index 호출 목록을 초기화한다."""
        self.calls: list[dict[str, object]] = []

    def index(
        self, *, index: str, id: str, document: dict[str, object]
    ) -> dict[str, str]:
        """seeded Elasticsearch document index 호출을 저장한다."""
        self.calls.append({"index": index, "id": id, "document": document})
        return {"_id": id}


class FakeSplunkIndex:
    """Splunk seed가 submit할 event batch를 기록한다."""

    def __init__(self) -> None:
        """Splunk seed가 submit할 event batch를 초기화한다."""
        self.events: list[str] = []

    def submit(self, event: str) -> None:
        """Splunk event payload와 sourcetype을 batch에 저장한다."""
        self.events.append(event)


class FakeSplunkService:
    """seed script가 접근하는 Splunk index collection을 제공한다."""

    def __init__(self) -> None:
        """Splunk seed 테스트용 HEC client 대역을 연결한다."""
        self.indexes = {"main": FakeSplunkIndex()}


class CreatableSplunkIndexes(dict[str, FakeSplunkIndex]):
    """생성 호출을 기록하는 Splunk indexes 대역이다."""

    def create(self, index: str) -> FakeSplunkIndex:
        """생성할 Splunk index 이름을 기록한다."""
        self[index] = FakeSplunkIndex()
        return self[index]


class CreatableSplunkService:
    """indexes 속성을 제공하는 Splunk service 대역이다."""

    def __init__(self) -> None:
        """테스트가 관찰할 creatable indexes 대역을 연결한다."""
        self.indexes = CreatableSplunkIndexes()


def test_seed_elasticsearch_documents_indexes_with_stable_source_ids() -> None:
    """Elasticsearch seed가 안정적인 source id로 문서를 index하는지 확인한다."""
    client = FakeElasticsearchClient()
    docs = [{"message": "allowed"}, {"message": "blocked"}]

    ids = seed_elasticsearch_documents(client, "logs-2026", docs)

    assert ids == ["es-seed-1", "es-seed-2"]
    assert client.calls[0]["document"] == {"message": "allowed"}


def test_seed_splunk_events_submits_json_events() -> None:
    """Splunk seed가 JSON event를 HEC로 제출하는지 확인한다."""
    service = FakeSplunkService()

    ids = seed_splunk_events(service, "main", [{"clientip": "10.0.0.5"}])

    assert ids == ["splunk-seed-1"]
    assert '"source_doc_id": "splunk-seed-1"' in service.indexes["main"].events[0]


def test_seed_splunk_events_creates_missing_index() -> None:
    """Splunk index가 없으면 seed 전에 index를 생성하는지 확인한다."""
    service = CreatableSplunkService()

    ids = seed_splunk_events(service, "security", [{"source_ip": "10.0.0.5"}])

    assert ids == ["splunk-seed-1"]
    assert "security" in service.indexes
    assert '"source_ip": "10.0.0.5"' in service.indexes["security"].events[0]
