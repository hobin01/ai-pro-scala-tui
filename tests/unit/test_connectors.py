import sys
import types
from typing import ClassVar

from pytest import MonkeyPatch

from scala_backend.connectors import (
    ElasticsearchConnector,
    SplunkConnector,
    parse_service_url,
    splunk_source_doc_id,
)


def test_parse_service_url_extracts_scheme_host_and_port() -> None:
    """parse service url extracts scheme host and port 동작을 검증한다."""
    parsed = parse_service_url("https://splunk.local:8089")

    assert parsed.scheme == "https"
    assert parsed.host == "splunk.local"
    assert parsed.port == 8089


def test_splunk_source_doc_id_preserves_seeded_and_native_ids() -> None:
    """splunk source doc id preserves seeded and native ids 동작을 검증한다."""
    seeded = splunk_source_doc_id({"source_doc_id": "splunk-seed-1"})
    native = splunk_source_doc_id({"_bkt": "bucket", "_cd": "42"})
    native_with_seed_id = splunk_source_doc_id(
        {"source_doc_id": "splunk-seed-1", "_bkt": "bucket", "_cd": "43"}
    )

    assert seeded == "splunk-seed-1"
    assert native == "bucket:42"
    assert native_with_seed_id == "bucket:43"


class FakeElasticsearchClient:
    """FakeElasticsearchClient 호출 계약을 정의한다."""

    def __init__(self, url: str, basic_auth: object = None) -> None:
        """객체 초기 상태를 준비한다."""
        del url, basic_auth


class FakeElasticsearchHelpers:
    """FakeElasticsearchHelpers 테스트 대상을 표현한다."""

    calls: ClassVar[list[dict[str, object]]] = []

    @staticmethod
    def scan(
        client: FakeElasticsearchClient,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        """scan 동작을 처리한다."""
        del client
        FakeElasticsearchHelpers.calls.append(kwargs)
        return [
            {"_id": str(index), "_source": {"value": index}} for index in range(5001)
        ]


def test_elasticsearch_connector_scans_without_document_cap(
    monkeypatch: MonkeyPatch,
) -> None:
    """elasticsearch connector scans without document cap 동작을 검증한다."""
    FakeElasticsearchHelpers.calls = []
    module = types.SimpleNamespace(Elasticsearch=FakeElasticsearchClient)
    helpers = types.SimpleNamespace(scan=FakeElasticsearchHelpers.scan)
    monkeypatch.setitem(sys.modules, "elasticsearch", module)
    monkeypatch.setitem(sys.modules, "elasticsearch.helpers", helpers)
    connector = ElasticsearchConnector("http://localhost:9200", None, None)

    docs = list(connector.iter_documents("logs"))

    assert len(docs) == 5001
    assert FakeElasticsearchHelpers.calls == [
        {"index": "logs", "query": {"query": {"match_all": {}}}, "size": 1000}
    ]


class FakeSplunkJobs:
    """FakeSplunkJobs 테스트 대상을 표현한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self.search = ""

    def export(
        self,
        search: str,
        output_mode: str,
    ) -> list[dict[str, str]]:
        """export 동작을 처리한다."""
        del output_mode
        self.search = search
        return [{"source_doc_id": f"splunk-{index}"} for index in range(5001)]


class FakeSplunkService:
    """FakeSplunkService 테스트 대상을 표현한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self.jobs = FakeSplunkJobs()


def fake_splunk_connect(**kwargs: object) -> FakeSplunkService:
    """fake splunk connect 동작을 처리한다."""
    del kwargs
    return fake_splunk_service


def fake_json_results_reader(
    stream: list[dict[str, str]],
) -> list[dict[str, str]]:
    """fake json results reader 동작을 처리한다."""
    return stream


fake_splunk_service = FakeSplunkService()


def test_splunk_connector_exports_without_document_cap(
    monkeypatch: MonkeyPatch,
) -> None:
    """splunk connector exports without document cap 동작을 검증한다."""
    fake_splunk_service.jobs.search = ""
    client_module = types.SimpleNamespace(connect=fake_splunk_connect)
    results_module = types.SimpleNamespace(JSONResultsReader=fake_json_results_reader)
    monkeypatch.setitem(sys.modules, "splunklib.client", client_module)
    monkeypatch.setitem(sys.modules, "splunklib.results", results_module)
    connector = SplunkConnector("https://localhost:8089", "admin", "password")

    docs = list(connector.iter_documents("main"))

    assert len(docs) == 5001
    assert fake_splunk_service.jobs.search == "search index=main | spath"
