from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import anyio
import pytest
from anyio.abc import TaskGroup

from scala_backend.app import BackendApp
from scala_backend.app_factory import create_app
from scala_backend.cache import InMemoryMappingCache
from scala_backend.config import BackendConfig
from scala_backend.connectors import default_connectors
from scala_backend.errors import ConfigurationError, RunInProgressError
from scala_backend.models import (
    LLM_AGENTS,
    AgentName,
    JsonObject,
    MonitoringQueryParams,
    PipelineRunParams,
    SettingsSetParams,
    SourceSelection,
)
from scala_backend.providers import LlmResponse, ProviderUsage
from scala_backend.store import InMemoryStore, make_usage


class RecordingPeer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, JsonObject]] = []

    async def notify(self, method: str, params: JsonObject) -> None:
        self.messages.append((method, params))

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        self.messages.append((method, params))
        return {"decision": "approve"}


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        prompt: str,
        model: str,
        price: dict[str, float] | None,
    ) -> LlmResponse:
        self.calls.append({"prompt": prompt, "model": model, "price": price})
        return LlmResponse(
            text="ok",
            usage=ProviderUsage(
                prompt_tokens=11,
                completion_tokens=5,
                total_tokens=16,
                cost_usd=Decimal("0.0195"),
            ),
        )


class BlockingFeedbackPeer:
    def __init__(self, task_group: TaskGroup) -> None:
        self.task_group = task_group
        self.messages: list[tuple[str, JsonObject]] = []
        self.feedback_requested = anyio.Event()
        self.release_feedback = anyio.Event()
        self.completed = anyio.Event()

    async def notify(self, method: str, params: JsonObject) -> None:
        self.messages.append((method, params))
        if method == "run.status" and params.get("status") in {"completed", "failed"}:
            self.completed.set()

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        self.messages.append((method, params))
        if method == "feedback.request":
            self.feedback_requested.set()
            await self.release_feedback.wait()
        return {"decision": "approve"}

    def start_soon(
        self,
        func: Callable[..., Coroutine[Any, Any, None]],
        *args: object,
    ) -> None:
        self.task_group.start_soon(func, *args)


def test_settings_handlers_are_hot_reload() -> None:
    app = create_app(BackendConfig(openai_api_key="sk-test-12345678"))

    result = app.settings_set(
        SettingsSetParams(key="source.splunk.indices", value=["security"]),
    )

    assert result["applied"] == "hot-reload"
    assert app.settings_get()["sources"]["splunk"]["indices"] == ["security"]
    assert app.settings_get()["openai_api_key_masked"] == "set...5678"


def test_settings_get_redacts_source_url_credentials() -> None:
    app = create_app(BackendConfig(openai_api_key="sk-test-12345678"))

    app.settings_set(
        SettingsSetParams(
            key="source.splunk.url",
            value="https://admin:secret@127.0.0.1:8089",
        ),
    )

    assert (
        app.settings_get()["sources"]["splunk"]["url"]
        == "https://admin:<redacted>@127.0.0.1:8089"
    )


def test_monitoring_session_starts_at_backend_process_start() -> None:
    app = create_app(BackendConfig(openai_api_key="sk-test-12345678"))
    old_usage = make_usage(
        uuid4(),
        AgentName.ORCHESTRATOR,
        "old run",
        "gpt-5-mini",
        100,
    ).model_copy(update={"created_at": app.started_at - timedelta(seconds=1)})
    new_usage = make_usage(
        uuid4(),
        AgentName.ORCHESTRATOR,
        "new run",
        "gpt-5-mini",
        7,
    ).model_copy(update={"created_at": datetime.now(UTC)})
    app.store.add_usage(old_usage)
    app.store.add_usage(new_usage)

    result = app.monitoring_query(MonitoringQueryParams(scope="session"))

    assert result["total"]["tokens"] == 7


@pytest.mark.anyio
async def test_pipeline_run_rejects_missing_required_settings() -> None:
    app = BackendApp(BackendConfig(), store=InMemoryStore())

    with pytest.raises(ConfigurationError, match="OpenSearch URL"):
        await app.pipeline_run(
            PipelineRunParams(
                sources=[
                    SourceSelection(solution="elasticsearch", index="logs-2026"),
                    SourceSelection(solution="splunk", index="main"),
                ],
            ),
            RecordingPeer(),
        )


@pytest.mark.anyio
async def test_pipeline_run_requires_two_or_more_sources() -> None:
    app = create_app(BackendConfig())

    with pytest.raises(ConfigurationError, match="at least two sources"):
        await app.pipeline_run(
            PipelineRunParams(
                sources=[SourceSelection(solution="splunk", index="main")],
            ),
            RecordingPeer(),
        )


@pytest.mark.anyio
async def test_pipeline_run_requires_agent_models() -> None:
    store = InMemoryStore()
    store.set_setting("source.elasticsearch.url", "memory://elasticsearch")
    store.set_setting("source.elasticsearch.indices", ["logs-2026"])
    store.set_setting("source.splunk.url", "memory://splunk")
    store.set_setting("source.splunk.indices", ["main"])
    store.set_setting("output.opensearch.url", "memory://opensearch")
    store.set_setting("output.opensearch.index", "scala-normalized")
    app = BackendApp(BackendConfig(), store=store)

    with pytest.raises(ConfigurationError, match="model is not configured"):
        await app.pipeline_run(
            PipelineRunParams(
                sources=[
                    SourceSelection(solution="elasticsearch", index="logs-2026"),
                    SourceSelection(solution="splunk", index="main"),
                ],
            ),
            RecordingPeer(),
        )


@pytest.mark.anyio
async def test_pipeline_records_agent_usage_with_settings_prompts() -> None:
    store = InMemoryStore()
    for key, value in {
        "source.elasticsearch.url": "memory://elasticsearch",
        "source.elasticsearch.indices": ["logs-2026"],
        "source.splunk.url": "memory://splunk",
        "source.splunk.indices": ["main"],
        "output.opensearch.url": "memory://opensearch",
        "output.opensearch.index": "scala-normalized",
        "agent.orchestrator.model": "gpt-orchestrator",
        "agent.schema_profiler.model": "gpt-profiler",
        "agent.normalization.model": "gpt-normalizer",
        "agent.validator.model": "gpt-validator",
        "agent.orchestrator.system_prompt": "ORCH SYSTEM",
        "agent.schema_profiler.system_prompt": "PROFILE SYSTEM",
        "agent.normalization.system_prompt": "NORMALIZE SYSTEM",
        "agent.validator.system_prompt": "VALIDATE SYSTEM",
        "model.gpt-orchestrator.price": {
            "prompt_per_1k": 0.5,
            "completion_per_1k": 1.0,
        },
        "model.gpt-profiler.price": {
            "prompt_per_1k": 0.25,
            "completion_per_1k": 0.75,
        },
        "model.gpt-normalizer.price": {
            "prompt_per_1k": 0.3,
            "completion_per_1k": 0.9,
        },
        "model.gpt-validator.price": {
            "prompt_per_1k": 0.4,
            "completion_per_1k": 1.1,
        },
    }.items():
        store.set_setting(key, value)
    provider = RecordingProvider()
    app = BackendApp(
        BackendConfig(),
        store=store,
        connectors=default_connectors(),
        cache=InMemoryMappingCache(),
        llm_provider=provider,
    )
    params = PipelineRunParams(
        sources=[
            SourceSelection(solution="elasticsearch", index="logs-2026"),
            SourceSelection(solution="splunk", index="main"),
        ],
    )

    async with anyio.create_task_group() as task_group:
        peer = BlockingFeedbackPeer(task_group)
        peer.release_feedback.set()
        await app.pipeline_run(params, peer)
        with anyio.fail_after(1):
            await peer.completed.wait()

    assert [call["model"] for call in provider.calls] == [
        "gpt-orchestrator",
        "gpt-profiler",
        "gpt-normalizer",
        "gpt-validator",
    ]
    assert [prompt in str(call["prompt"]) for prompt, call in zip(
        ["ORCH SYSTEM", "PROFILE SYSTEM", "NORMALIZE SYSTEM", "VALIDATE SYSTEM"],
        provider.calls,
        strict=True,
    )] == [True, True, True, True]
    usage = store.list_usage()
    assert len(usage) == 7
    assert [row.agent for row in usage if row.agent in LLM_AGENTS] == list(LLM_AGENTS)
    assert all(row.prompt_tokens == 11 for row in usage if row.agent in LLM_AGENTS)
    assert all(row.completion_tokens == 5 for row in usage if row.agent in LLM_AGENTS)


@pytest.mark.anyio
async def test_opensearch_loader_is_refreshed_from_current_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(BackendConfig())
    constructed_urls: list[str | None] = []

    class CapturingOpenSearchLoader:
        def __init__(
            self,
            url: str | None = None,
            *,
            username: str | None = None,
            password: str | None = None,
        ) -> None:
            del username, password
            constructed_urls.append(url)

        def index_normalized(
            self,
            index: str,
            doc_id: str,
            document: JsonObject,
        ) -> str:
            del index, document
            return doc_id

        def fetch_by_id(self, index: str, doc_id: str) -> JsonObject | None:
            del index, doc_id
            return None

    monkeypatch.setattr("scala_backend.app.OpenSearchLoader", CapturingOpenSearchLoader)
    app.settings_set(
        SettingsSetParams(
            key="output.opensearch.url",
            value="http://hot-opensearch:9200",
        )
    )

    app.refresh_opensearch()

    assert constructed_urls == ["http://hot-opensearch:9200"]
    assert app.opensearch is not None


@pytest.mark.anyio
async def test_pipeline_run_rejects_overlap_while_waiting_for_feedback() -> None:
    app = create_app(BackendConfig())
    params = PipelineRunParams(
        sources=[
            SourceSelection(solution="elasticsearch", index="logs-2026"),
            SourceSelection(solution="splunk", index="main"),
        ],
    )

    async with anyio.create_task_group() as task_group:
        peer = BlockingFeedbackPeer(task_group)
        first = await app.pipeline_run(params, peer)
        with anyio.fail_after(1):
            await peer.feedback_requested.wait()

        with pytest.raises(RunInProgressError):
            await app.pipeline_run(params, RecordingPeer())

        peer.release_feedback.set()
        with anyio.fail_after(1):
            await peer.completed.wait()
        assert first
