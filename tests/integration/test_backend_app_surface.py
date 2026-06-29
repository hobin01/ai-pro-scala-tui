from collections.abc import Callable, Coroutine
from typing import Any

import anyio
import pytest
from anyio.abc import TaskGroup

from scala_backend.app_factory import create_app
from scala_backend.cache import cache_key
from scala_backend.config import BackendConfig
from scala_backend.connector_fixtures import default_connectors
from scala_backend.models import JsonObject
from scala_backend.normalization import recommend_mapping
from scala_backend.pipeline import _stable_opensearch_id


class InlinePeer:
    def __init__(self, task_group: TaskGroup) -> None:
        self.task_group = task_group
        self.messages: list[tuple[str, JsonObject]] = []
        self.running = anyio.Event()
        self.completed = anyio.Event()

    async def notify(self, method: str, params: JsonObject) -> None:
        self.messages.append((method, params))
        if method == "run.status" and params.get("status") == "running":
            self.running.set()
        if method == "run.status" and params.get("status") == "completed":
            self.completed.set()

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        self.messages.append((method, params))
        return {"decision": "approve"}

    def start_soon(
        self,
        func: Callable[..., Coroutine[Any, Any, None]],
        *args: object,
    ) -> None:
        self.task_group.start_soon(func, *args)


@pytest.mark.anyio
async def test_pipeline_surface_returns_run_id() -> None:
    app = create_app(BackendConfig())
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        result = await app.handle(
            "pipeline.run",
            {
                "sources": [
                    {"solution": "elasticsearch", "index": "logs-2026"},
                    {"solution": "splunk", "index": "main"},
                ]
            },
            peer,
        )
        with anyio.fail_after(1):
            await peer.running.wait()
        assert "run_id" in result
        assert (
            "run.status",
            {"run_id": result["run_id"], "status": "running"},
        ) in peer.messages
        task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_pipeline_surface_reports_prd_agent_count_and_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(BackendConfig())
    graph_calls: list[tuple[bool, bool, bool]] = []

    def capture_graph(
        run_id: str,
        *,
        cache_hit: bool = False,
        cache_miss: bool = True,
        needs_feedback: bool = False,
    ) -> JsonObject:
        graph_calls.append((cache_hit, cache_miss, needs_feedback))
        return {"run_id": run_id, "stages": [], "nodes": []}

    monkeypatch.setattr("scala_backend.pipeline.run_agent_graph", capture_graph)
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        result = await app.handle(
            "pipeline.run",
            {
                "sources": [
                    {"solution": "elasticsearch", "index": "logs-2026"},
                    {"solution": "splunk", "index": "main"},
                ]
            },
            peer,
        )
        with anyio.fail_after(2):
            await peer.completed.wait()

        progress_messages = [
            params["message"]
            for method, params in peer.messages
            if method == "progress" and params.get("agent") == "schema_profiler"
        ]
        assert "profiled 9 fields (cache 0 hit · 9 miss)" in progress_messages
        assert graph_calls == [(False, True, True)]

        completed = next(
            params
            for method, params in peer.messages
            if method == "run.status" and params.get("status") == "completed"
        )
        assert completed["run_id"] == result["run_id"]
        assert completed["summary"] == {
            "mapped": 7,
            "kept_raw": 2,
            "loaded": 2,
            "lineage": 2,
            "cached": 9,
        }
        fixture_connectors = default_connectors()
        es_doc = next(
            iter(fixture_connectors["elasticsearch"].iter_documents("logs-2026"))
        )
        splunk_doc = next(iter(fixture_connectors["splunk"].iter_documents("main")))
        assert completed["lineage_refs"] == [
            {
                "source_solution": "elasticsearch",
                "source_index": "logs-2026",
                "source_doc_id": "es-1",
                "opensearch_id": _stable_opensearch_id(es_doc),
            },
            {
                "source_solution": "splunk",
                "source_index": "main",
                "source_doc_id": "_bkt-1:_cd-42",
                "opensearch_id": _stable_opensearch_id(splunk_doc),
            },
        ]
        task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_pipeline_surface_routes_cache_hit_into_agent_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(BackendConfig())
    settings = app.store.get_settings()
    source_url = settings["source.splunk.url"]
    assert isinstance(source_url, str)
    source_urls = {
        "elasticsearch": settings["source.elasticsearch.url"],
        "splunk": source_url,
    }
    for solution, index in (("elasticsearch", "logs-2026"), ("splunk", "main")):
        assert isinstance(source_urls[solution], str)
        for field in app.connectors[solution].fetch_schema_samples(index):
            app.cache.set(
                cache_key(source_urls[solution], index, field.name, field.type),
                recommend_mapping(field),
            )
    graph_calls: list[tuple[bool, bool, bool]] = []

    def capture_graph(
        run_id: str,
        *,
        cache_hit: bool = False,
        cache_miss: bool = True,
        needs_feedback: bool = False,
    ) -> JsonObject:
        graph_calls.append((cache_hit, cache_miss, needs_feedback))
        return {"run_id": run_id, "stages": [], "nodes": []}

    monkeypatch.setattr("scala_backend.pipeline.run_agent_graph", capture_graph)
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        await app.handle(
            "pipeline.run",
            {
                "sources": [
                    {"solution": "elasticsearch", "index": "logs-2026"},
                    {"solution": "splunk", "index": "main"},
                ]
            },
            peer,
        )
        with anyio.fail_after(2):
            await peer.completed.wait()

        assert graph_calls == [(True, False, False)]
        assert not any(method == "feedback.request" for method, _ in peer.messages)
        task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_pipeline_surface_routes_mixed_cache_and_feedback_into_agent_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(BackendConfig())
    settings = app.store.get_settings()
    source_url = settings["source.splunk.url"]
    assert isinstance(source_url, str)
    time_field = next(
        field
        for field in app.connectors["splunk"].fetch_schema_samples("main")
        if field.name == "_time"
    )
    app.cache.set(
        cache_key(source_url, "main", time_field.name, time_field.type),
        recommend_mapping(time_field),
    )
    graph_calls: list[tuple[bool, bool, bool]] = []

    def capture_graph(
        run_id: str,
        *,
        cache_hit: bool = False,
        cache_miss: bool = True,
        needs_feedback: bool = False,
    ) -> JsonObject:
        graph_calls.append((cache_hit, cache_miss, needs_feedback))
        return {"run_id": run_id, "stages": [], "nodes": []}

    monkeypatch.setattr("scala_backend.pipeline.run_agent_graph", capture_graph)
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        await app.handle(
            "pipeline.run",
            {
                "sources": [
                    {"solution": "elasticsearch", "index": "logs-2026"},
                    {"solution": "splunk", "index": "main"},
                ]
            },
            peer,
        )
        with anyio.fail_after(2):
            await peer.completed.wait()

        assert graph_calls == [(True, True, True)]
        assert any(method == "feedback.request" for method, _ in peer.messages)
        task_group.cancel_scope.cancel()
