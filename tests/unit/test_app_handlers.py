from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import anyio
import pytest
from anyio.abc import TaskGroup

from scala_backend.app import BackendApp
from scala_backend.app_factory import create_app
from scala_backend.config import BackendConfig
from scala_backend.errors import ConfigurationError, RunInProgressError
from scala_backend.models import (
    AgentName,
    JsonObject,
    MonitoringQueryParams,
    PipelineRunParams,
    SettingsSetParams,
    SourceSelection,
)
from scala_backend.store import InMemoryStore, make_usage


class RecordingPeer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, JsonObject]] = []

    async def notify(self, method: str, params: JsonObject) -> None:
        self.messages.append((method, params))

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        self.messages.append((method, params))
        return {"decision": "approve"}


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
                sources=[SourceSelection(solution="splunk", index="main")],
            ),
            RecordingPeer(),
        )


@pytest.mark.anyio
async def test_pipeline_run_rejects_overlap_while_waiting_for_feedback() -> None:
    app = create_app(BackendConfig())
    params = PipelineRunParams(
        sources=[SourceSelection(solution="splunk", index="main")],
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
