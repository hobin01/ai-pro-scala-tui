import sys
import types
from typing import ClassVar

from pytest import MonkeyPatch

from scala_backend.connector_fixtures import FixtureConnector
from scala_backend.connectors import (
    ElasticsearchConnector,
    SplunkConnector,
    parse_service_url,
    splunk_source_doc_id,
)
from scala_backend.models import RawDocument


def test_parse_service_url_extracts_scheme_host_and_port() -> None:
    """Splunk service URL에서 scheme, host, port를 분리하는지 확인한다."""
    parsed = parse_service_url("https://splunk.local:8089")

    assert parsed.scheme == "https"
    assert parsed.host == "splunk.local"
    assert parsed.port == 8089


def test_splunk_source_doc_id_preserves_seeded_and_native_ids() -> None:
    """Splunk source id가 seed id를 우선하고 없으면 native id를 쓰는지 확인한다."""
    seeded = splunk_source_doc_id({"source_doc_id": "splunk-seed-1"})
    native = splunk_source_doc_id({"_bkt": "bucket", "_cd": "42"})
    native_with_seed_id = splunk_source_doc_id(
        {"source_doc_id": "splunk-seed-1", "_bkt": "bucket", "_cd": "43"}
    )

    assert seeded == "splunk-seed-1"
    assert native == "bucket:42"
    assert native_with_seed_id == "splunk-seed-1"


def test_fixture_schema_samples_keep_first_non_null_type() -> None:
    """Fixture schema sample이 null보다 실제 sample 타입을 우선하는지 확인한다."""
    connector = FixtureConnector(
        "splunk",
        [
            RawDocument("splunk", "security", "one", {"user": "alice"}),
            RawDocument("splunk", "security", "two", {"user": None}),
        ],
    )

    samples = connector.fetch_schema_samples("security")

    assert len(samples) == 1
    assert samples[0].name == "user"
    assert samples[0].samples == ["alice", None]
    assert samples[0].type == "string"


class FakeElasticsearchClient:
    """ElasticsearchConnector가 import한 client 생성자를 대신한다."""

    def __init__(self, url: str, basic_auth: object = None) -> None:
        """테스트용 Elasticsearch client 생성 인자를 보관한다."""
        del url, basic_auth


class FakeElasticsearchHelpers:
    """helpers.scan 호출 옵션과 반환 문서를 제어한다."""

    calls: ClassVar[list[dict[str, object]]] = []

    @staticmethod
    def scan(
        client: FakeElasticsearchClient,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        """scan 호출 인자를 기록하고 준비된 hit 목록을 반환한다."""
        del client
        FakeElasticsearchHelpers.calls.append(kwargs)
        return [
            {"_id": str(index), "_source": {"value": index}} for index in range(5001)
        ]


def test_elasticsearch_connector_scans_without_document_cap(
    monkeypatch: MonkeyPatch,
) -> None:
    """Elasticsearch connector가 scan 결과를 수 제한 없이 반환하는지 확인한다."""
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
    """Splunk export 검색문과 결과 row를 기록한다."""

    def __init__(self) -> None:
        """마지막 export 검색문을 저장할 테스트 상태를 초기화한다."""
        self.search = ""

    def export(
        self,
        search: str,
        output_mode: str,
    ) -> list[dict[str, str]]:
        """export 검색문을 기록하고 준비된 Splunk event를 반환한다."""
        del output_mode
        self.search = search
        return [{"source_doc_id": f"splunk-{index}"} for index in range(5001)]


class FakeSplunkService:
    """Splunk SDK service의 jobs 속성을 제공한다."""

    def __init__(self) -> None:
        """테스트용 Splunk service에 jobs API 대역을 붙인다."""
        self.jobs = FakeSplunkJobs()


def fake_splunk_connect(**kwargs: object) -> FakeSplunkService:
    """Splunk SDK connect 호출을 fake service로 대체한다."""
    del kwargs
    return fake_splunk_service


def fake_json_results_reader(
    stream: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Splunk JSONResultsReader 대역으로 stream을 그대로 반환한다."""
    return stream


fake_splunk_service = FakeSplunkService()


def test_splunk_connector_exports_without_document_cap(
    monkeypatch: MonkeyPatch,
) -> None:
    """Splunk connector가 export 결과를 수 제한 없이 반환하는지 확인한다."""
    fake_splunk_service.jobs.search = ""
    client_module = types.SimpleNamespace(connect=fake_splunk_connect)
    results_module = types.SimpleNamespace(JSONResultsReader=fake_json_results_reader)
    monkeypatch.setitem(sys.modules, "splunklib.client", client_module)
    monkeypatch.setitem(sys.modules, "splunklib.results", results_module)
    connector = SplunkConnector("https://localhost:8089", "admin", "password")

    docs = list(connector.iter_documents("main"))

    assert len(docs) == 5001
    assert fake_splunk_service.jobs.search == "search index=main | spath"
