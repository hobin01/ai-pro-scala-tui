from scala_backend.seed.external import (
    seed_elasticsearch_documents,
    seed_splunk_events,
)


class FakeElasticsearchClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def index(
        self, *, index: str, id: str, document: dict[str, object]
    ) -> dict[str, str]:
        self.calls.append({"index": index, "id": id, "document": document})
        return {"_id": id}


class FakeSplunkIndex:
    def __init__(self) -> None:
        self.events: list[str] = []

    def submit(self, event: str) -> None:
        self.events.append(event)


class FakeSplunkService:
    def __init__(self) -> None:
        self.indexes = {"main": FakeSplunkIndex()}


def test_seed_elasticsearch_documents_indexes_with_stable_source_ids() -> None:
    client = FakeElasticsearchClient()
    docs = [{"message": "allowed"}, {"message": "blocked"}]

    ids = seed_elasticsearch_documents(client, "logs-2026", docs)

    assert ids == ["es-seed-1", "es-seed-2"]
    assert client.calls[0]["document"] == {"message": "allowed"}


def test_seed_splunk_events_submits_json_events() -> None:
    service = FakeSplunkService()

    ids = seed_splunk_events(service, "main", [{"clientip": "10.0.0.5"}])

    assert ids == ["splunk-seed-1"]
    assert '"source_doc_id": "splunk-seed-1"' in service.indexes["main"].events[0]
