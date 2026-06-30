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
from scala_backend.models import AgentName, JsonObject
from scala_backend.normalization import recommend_mapping
from scala_backend.pipeline import stable_opensearch_id
from scala_backend.providers import LlmResponse, ProviderUsage

PIPELINE_SOURCES = [
    {"solution": "elasticsearch", "index": "scala-es-network"},
    {"solution": "elasticsearch", "index": "scala-es-endpoint"},
    {"solution": "splunk", "index": "main"},
    {"solution": "splunk", "index": "security"},
]


class InlinePeer:
    """BackendApp surface 테스트에서 notification/request를 즉시 기록하는 peer다."""

    def __init__(self, task_group: TaskGroup) -> None:
        """integration peer가 수집할 notification, request 목록과 이벤트를 준비한다."""
        self.task_group = task_group
        self.messages: list[tuple[str, JsonObject]] = []
        self.running = anyio.Event()
        self.completed = anyio.Event()

    async def notify(self, method: str, params: JsonObject) -> None:
        """notification payload를 저장하고 완료 이벤트를 표시한다."""
        self.messages.append((method, params))
        if method == "run.status" and params.get("status") == "running":
            self.running.set()
        if method == "run.status" and params.get("status") == "completed":
            self.completed.set()

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        """feedback request payload를 저장하고 approve 응답을 반환한다."""
        self.messages.append((method, params))
        return {"decision": "approve"}

    def start_soon(
        self,
        func: Callable[..., Coroutine[Any, Any, None]],
        *args: object,
    ) -> None:
        """BackendApp이 요청한 background coroutine을 test TaskGroup에 올린다."""
        self.task_group.start_soon(func, *args)


class AgentJsonProvider:
    def __init__(self, *, feedback_required: bool = False) -> None:
        self.feedback_required = feedback_required
        self.calls: list[dict[str, object]] = []
        self.validate_calls: list[str] = []

    def validate(self, model: str) -> None:
        self.validate_calls.append(model)

    def complete(
        self,
        prompt: str,
        model: str,
        price: dict[str, float] | None,
    ) -> LlmResponse:
        self.calls.append({"prompt": prompt, "model": model, "price": price})
        payload: object = json.loads(prompt[prompt.find("{") : prompt.rfind("}") + 1])
        if not isinstance(payload, dict):
            raise AssertionError("agent prompt must contain JSON")
        return LlmResponse(
            text=self._response_text(payload),
            usage=ProviderUsage(3, 2, 5, Decimal("0.00001")),
        )

    def _response_text(self, payload: JsonObject) -> str:
        task = str(payload.get("task") or "")
        if task == "Generate one OCSF mapping decision.":
            source = payload.get("source")
            if not isinstance(source, dict):
                raise AssertionError("normalization prompt must contain source")
            field = str(source.get("field") or "")
            if field in {"src_ip", "source_ip", "clientip", "client_ip"}:
                return json.dumps(
                    {
                        "action": "map",
                        "ocsf_field": "src_endpoint.ip",
                        "ocsf_type": "ip",
                    }
                )
            if field in {"port", "dest_port", "dst_port"}:
                return json.dumps(
                    {
                        "action": "map",
                        "ocsf_field": "dst_endpoint.port",
                        "ocsf_type": "integer",
                    }
                )
            if field in {"@timestamp", "_time", "time"}:
                return json.dumps(
                    {"action": "map", "ocsf_field": "time", "ocsf_type": "string"}
                )
            if field in {"action", "status"}:
                return json.dumps(
                    {
                        "action": "map",
                        "ocsf_field": "activity_name",
                        "ocsf_type": "string",
                    }
                )
            return json.dumps({"action": "keep_raw"})
        if task == "Validate SCALA mapping decisions.":
            if self.feedback_required:
                return json.dumps(
                    {
                        "status": "feedback_required",
                        "feedback_request": {
                            "source_field": "clientip",
                            "question": "Confirm source IP mapping.",
                        },
                    }
                )
            return json.dumps({"status": "valid"})
        return json.dumps({"status": "ok"})


def app_with_agent_provider(*, feedback_required: bool = False) -> BackendApp:
    """fallback LLM provider를 붙인 BackendApp fixture를 만든다."""
    app = create_app(BackendConfig())
    app.llm_provider = AgentJsonProvider(feedback_required=feedback_required)
    app.set_pipeline()
    return app


@pytest.mark.anyio
async def test_pipeline_surface_returns_run_id() -> None:
    """pipeline.run JSON-RPC handler가 run_id를 즉시 반환하는지 확인한다."""
    app = app_with_agent_provider()
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        result = await app.handle(
            "pipeline.run",
            {"sources": PIPELINE_SOURCES},
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
async def test_pipeline_surface_reports_prd_agent_count_and_completes() -> None:
    """pipeline 실행이 PRD agent trace와 완료 notification을 내보내는지 확인한다."""
    app = app_with_agent_provider()
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        result = await app.handle(
            "pipeline.run",
            {"sources": PIPELINE_SOURCES},
            peer,
        )
        with anyio.fail_after(2):
            await peer.completed.wait()

        progress_messages = [
            params["message"]
            for method, params in peer.messages
            if method == "progress" and params.get("agent") == "schema_profiler"
        ]
        assert any(message.startswith("profiled ") for message in progress_messages)

        completed = next(
            params
            for method, params in peer.messages
            if method == "run.status" and params.get("status") == "completed"
        )
        assert completed["run_id"] == result["run_id"]
        assert completed["summary"]["loaded"] == 4
        assert completed["summary"]["lineage"] == 4
        assert completed["summary"]["cached"] > 0
        fixture_connectors = default_connectors()
        es_doc = next(
            iter(fixture_connectors["elasticsearch"].iter_documents("scala-es-network"))
        )
        assert completed["lineage_refs"][0] == {
            "source_solution": "elasticsearch",
            "source_index": "scala-es-network",
            "source_doc_id": "es-network-1",
            "opensearch_id": stable_opensearch_id(es_doc),
        }
        usage = app.store.list_usage()
        for agent in (
            AgentName.ORCHESTRATOR,
            AgentName.SCHEMA_PROFILER,
            AgentName.NORMALIZATION,
            AgentName.VALIDATOR,
        ):
            assert any(row.agent == agent and row.total_tokens > 0 for row in usage)
        task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_pipeline_surface_routes_cache_hit_without_validator_or_feedback() -> (
    None
):
    app = app_with_agent_provider()
    settings = app.store.get_settings()
    source_urls = {
        "elasticsearch": settings["source.elasticsearch.url"],
        "splunk": settings["source.splunk.url"],
    }
    for source in PIPELINE_SOURCES:
        solution = str(source["solution"])
        index = str(source["index"])
        assert isinstance(source_urls[solution], str)
        for field in app.connectors[solution].fetch_schema_samples(index):
            app.cache.set(
                cache_key(source_urls[solution], index, field.name, field.type),
                recommend_mapping(field),
            )
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        await app.handle("pipeline.run", {"sources": PIPELINE_SOURCES}, peer)
        with anyio.fail_after(2):
            await peer.completed.wait()

        usage = app.store.list_usage()
        assert not any(row.agent == AgentName.VALIDATOR for row in usage)
        assert not any(row.agent == AgentName.NORMALIZATION for row in usage)
        assert not any(method == "feedback.request" for method, _ in peer.messages)
        completed = next(
            params
            for method, params in peer.messages
            if method == "run.status" and params.get("status") == "completed"
        )
        assert completed["summary"]["cached"] == 0
        task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_pipeline_surface_routes_mixed_cache_and_feedback() -> None:
    app = app_with_agent_provider(feedback_required=True)
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
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        await app.handle("pipeline.run", {"sources": PIPELINE_SOURCES}, peer)
        with anyio.fail_after(2):
            await peer.completed.wait()

        completed = next(
            params
            for method, params in peer.messages
            if method == "run.status" and params.get("status") == "completed"
        )
        assert completed["summary"]["cached"] > 0
        assert any(method == "feedback.request" for method, _ in peer.messages)
        task_group.cancel_scope.cancel()
