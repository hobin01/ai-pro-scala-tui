from datetime import UTC, datetime
from uuid import uuid4

import pytest

from scala_backend.app import BackendApp
from scala_backend.config import BackendConfig
from scala_backend.models import JsonObject, LineageLookupParams, LineageRecord
from scala_backend.store import InMemoryStore


class RecordingPeer:
    """RecordingPeer 테스트 대상을 표현한다."""

    async def notify(self, method: str, params: JsonObject) -> None:
        """notify 동작을 처리한다."""
        del method, params


@pytest.mark.anyio
async def test_lineage_lookup_returns_not_found_for_missing_opensearch_id() -> None:
    """lineage lookup returns not found for missing opensearch id 동작을 검증한다."""
    app = BackendApp(BackendConfig(), store=InMemoryStore())

    result = await app.lineage_lookup(
        LineageLookupParams(opensearch_id="missing-os-id"),
        RecordingPeer(),
    )

    assert result == {"found": False}


@pytest.mark.anyio
async def test_lineage_lookup_prefers_fetched_raw_and_normalized_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lineage lookup prefers fetched raw and normalized documents 동작을 검증한다."""
    store = InMemoryStore()
    store.set_setting("source.elasticsearch.url", "memory://elasticsearch")
    store.set_setting("source.splunk.url", "memory://splunk")
    store.set_setting("output.opensearch.url", "http://hot-opensearch:9200")
    run_id = uuid4()
    store.add_lineage(
        LineageRecord(
            run_id=run_id,
            source_solution="splunk",
            source_index="main",
            source_doc_id="_bkt-1:_cd-42",
            opensearch_index="scala-normalized",
            opensearch_id="os-1",
            raw_document={"clientip": "stale"},
            normalized_document={"activity_name": "stale"},
            created_at=datetime.now(UTC),
        )
    )

    class CapturingOpenSearchLoader:
        """CapturingOpenSearchLoader 테스트 대상을 표현한다."""

        def __init__(
            self,
            url: str | None = None,
            *,
            username: str | None = None,
            password: str | None = None,
        ) -> None:
            """객체 초기 상태를 준비한다."""
            del url, username, password

        def fetch_by_id(self, index: str, doc_id: str) -> JsonObject | None:
            """fetch by id 데이터를 조회한다."""
            assert index == "scala-normalized"
            assert doc_id == "os-1"
            return {"activity_name": "Allowed", "class_name": "Network Activity"}

    monkeypatch.setattr("scala_backend.app.OpenSearchLoader", CapturingOpenSearchLoader)
    app = BackendApp(BackendConfig(), store=store)

    result = await app.lineage_lookup(
        LineageLookupParams(opensearch_id="os-1"),
        RecordingPeer(),
    )

    assert result["metadata"] == {
        "run_id": str(run_id),
        "source_solution": "splunk",
        "source_index": "main",
        "source_doc_id": "_bkt-1:_cd-42",
        "opensearch_index": "scala-normalized",
        "opensearch_id": "os-1",
    }
    assert result["raw_document"]["clientip"] == "192.168.1.20"
    assert result["raw_document"]["port"] == "443"
    assert result["normalized_document"] == {
        "activity_name": "Allowed",
        "class_name": "Network Activity",
    }
