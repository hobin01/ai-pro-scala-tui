import json
from collections.abc import Callable, Coroutine
from decimal import Decimal
from typing import Any

import anyio
import pytest
from anyio.abc import TaskGroup

from scala_backend.app import BackendApp
from scala_backend.app_factory import create_app
from scala_backend.cache import cache_key
from scala_backend.config import BackendConfig
from scala_backend.connector_fixtures import default_connectors
from scala_backend.models import JsonObject
from scala_backend.normalization import recommend_mapping
from scala_backend.pipeline import stable_opensearch_id
from scala_backend.providers import LlmResponse, ProviderUsage


class InlinePeer:
    """InlinePeer 테스트 대상을 표현한다."""

    def __init__(self, task_group: TaskGroup) -> None:
        """객체 초기 상태를 준비한다."""
        self.task_group = task_group
        self.messages: list[tuple[str, JsonObject]] = []
        self.running = anyio.Event()
        self.completed = anyio.Event()

    async def notify(self, method: str, params: JsonObject) -> None:
        """notify 동작을 처리한다."""
        self.messages.append((method, params))
        if method == "run.status" and params.get("status") == "running":
            self.running.set()
        if method == "run.status" and params.get("status") == "completed":
            self.completed.set()

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        """request 동작을 처리한다."""
        self.messages.append((method, params))
        return {"decision": "approve"}

    def start_soon(
        self,
        func: Callable[..., Coroutine[Any, Any, None]],
        *args: object,
    ) -> None:
        """start soon 동작을 처리한다."""
        self.task_group.start_soon(func, *args)


class AgentJsonProvider:
    """AgentJsonProvider 테스트 대상을 표현한다."""

    def validate(self, model: str) -> None:
        """validate 동작을 처리한다."""
        del model

    def complete(
        self,
        prompt: str,
        model: str,
        price: dict[str, float] | None,
    ) -> LlmResponse:
        """complete 동작을 처리한다."""
        del model, price
        payload: object = json.loads(prompt[prompt.find("{") : prompt.rfind("}") + 1])
        if not isinstance(payload, dict):
            raise AssertionError("mapping prompt must contain JSON")
        fallback = payload.get("fallback")
        if not isinstance(fallback, dict):
            raise AssertionError("mapping prompt must contain fallback")
        return LlmResponse(
            text=json.dumps(fallback),
            usage=ProviderUsage(1, 1, 2, Decimal("0")),
        )


def app_with_agent_provider() -> BackendApp:
    """app with agent provider 동작을 처리한다."""
    app = create_app(BackendConfig())
    app.llm_provider = AgentJsonProvider()
    app.set_pipeline()
    return app


@pytest.mark.anyio
async def test_pipeline_surface_returns_run_id() -> None:
    """pipeline surface returns run id 동작을 검증한다."""
    app = app_with_agent_provider()
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
    """pipeline surface reports prd agent count and completes 동작을 검증한다."""
    app = app_with_agent_provider()
    graph_calls: list[tuple[bool, bool, bool]] = []

    def capture_graph(
        run_id: str,
        *,
        cache_hit: bool = False,
        cache_miss: bool = True,
        needs_feedback: bool = False,
    ) -> JsonObject:
        """capture graph 동작을 처리한다."""
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
                "opensearch_id": stable_opensearch_id(es_doc),
            },
            {
                "source_solution": "splunk",
                "source_index": "main",
                "source_doc_id": "_bkt-1:_cd-42",
                "opensearch_id": stable_opensearch_id(splunk_doc),
            },
        ]
        task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_pipeline_surface_routes_cache_hit_into_agent_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pipeline surface routes cache hit into agent graph 동작을 검증한다."""
    app = app_with_agent_provider()
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
        """capture graph 동작을 처리한다."""
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
    """캐시와 feedback이 agent graph로 전달되는지 검증한다."""
    app = app_with_agent_provider()
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
        """capture graph 동작을 처리한다."""
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
