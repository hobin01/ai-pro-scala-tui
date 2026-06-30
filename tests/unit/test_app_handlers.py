import json
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
from scala_backend.errors import ConfigurationError, ProviderError, RunInProgressError
from scala_backend.models import (
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
    """BackendApp handler 테스트에서 RPC 메시지를 기록하는 peer다."""

    def __init__(self) -> None:
        """handler 테스트가 수집할 notification과 request 목록을 초기화한다."""
        self.messages: list[tuple[str, JsonObject]] = []

    async def notify(self, method: str, params: JsonObject) -> None:
        """handler notification payload를 테스트 목록에 저장한다."""
        self.messages.append((method, params))

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        """feedback request payload를 저장하고 approve 응답을 반환한다."""
        self.messages.append((method, params))
        return {"decision": "approve"}


class RecordingProvider:
    """mapping prompt와 validate 호출을 기록하는 LLM provider 대역이다."""

    def __init__(self) -> None:
        """prompt, validate 호출 기록과 응답 text를 초기화한다."""
        self.calls: list[dict[str, object]] = []
        self.validate_calls: list[str] = []

    def validate(self, model: str) -> None:
        """recording provider의 model preflight 성공을 반환한다."""
        self.validate_calls.append(model)

    def complete(
        self,
        prompt: str,
        model: str,
        price: dict[str, float] | None,
    ) -> LlmResponse:
        """prompt를 기록하고 준비된 LLM 응답을 반환한다."""
        self.calls.append({"prompt": prompt, "model": model, "price": price})
        payload: object = json.loads(prompt[prompt.find("{") : prompt.rfind("}") + 1])
        if not isinstance(payload, dict):
            raise AssertionError("agent prompt must contain JSON")
        text = self._response_text(payload)
        return LlmResponse(
            text=text,
            usage=ProviderUsage(
                prompt_tokens=11,
                completion_tokens=5,
                total_tokens=16,
                cost_usd=Decimal("0.000031"),
            ),
        )

    def _response_text(self, payload: JsonObject) -> str:
        task = str(payload.get("task") or "")
        if task == "Generate OCSF mapping decisions for cache-miss fields.":
            fields = payload.get("fields")
            if not isinstance(fields, list):
                raise AssertionError("normalization prompt must contain fields")
            return json.dumps(
                {
                    "decisions": [
                        self._mapping_decision(
                            _field_item_id(field),
                            str(field.get("source_field")),
                        )
                        for field in fields
                        if isinstance(field, dict)
                    ]
                }
            )
        if task == "Validate SCALA mapping decisions.":
            return json.dumps(
                {
                    "status": "feedback_required",
                    "feedback_request": {
                        "source_field": "clientip",
                        "question": "Confirm source IP mapping.",
                    },
                }
            )
        return json.dumps({"status": "ok"})

    def _mapping_decision(self, item_id: str, field: str) -> JsonObject:
        if field in {"src_ip", "clientip", "client_ip", "source_ip"}:
            return {
                "item_id": item_id,
                "action": "map",
                "ocsf_field": "src_endpoint.ip",
                "ocsf_type": "ip",
            }
        if field in {"port", "dest_port", "dst_port"}:
            return {
                "item_id": item_id,
                "action": "map",
                "ocsf_field": "dst_endpoint.port",
                "ocsf_type": "integer",
            }
        if field in {"action", "status"}:
            return {
                "item_id": item_id,
                "action": "map",
                "ocsf_field": "activity_name",
                "ocsf_type": "string",
            }
        return {"item_id": item_id, "action": "keep_raw"}


def _field_item_id(field: JsonObject) -> str:
    item_id = field.get("item_id")
    if not isinstance(item_id, str) or not item_id:
        raise AssertionError("normalization prompt field must contain item_id")
    return item_id


class FailingProvider(RecordingProvider):
    """provider preflight 실패가 mapping 호출을 막는지 확인하는 대역이다."""

    def __init__(self) -> None:
        """실패 provider가 발생시킬 exception과 호출 기록을 초기화한다."""
        super().__init__()
        self.complete_called = False

    def validate(self, model: str) -> None:
        """설정된 exception으로 model preflight 실패를 발생시킨다."""
        super().validate(model)
        raise ProviderError("OpenAI API key is invalid")

    def complete(
        self,
        prompt: str,
        model: str,
        price: dict[str, float] | None,
    ) -> LlmResponse:
        """pipeline이 preflight에서 멈췄는지 확인하기 위해 호출 시 실패시킨다."""
        del prompt, model, price
        self.complete_called = True
        raise AssertionError("pipeline should not request mappings with invalid key")


class BlockingFeedbackPeer:
    """feedback 요청 지점에서 pipeline을 멈춰 race를 관찰하는 peer다."""

    def __init__(self, task_group: TaskGroup) -> None:
        """feedback 요청을 블로킹하고 overlap 검증용 이벤트를 초기화한다."""
        self.task_group = task_group
        self.messages: list[tuple[str, JsonObject]] = []
        self.feedback_requested = anyio.Event()
        self.release_feedback = anyio.Event()
        self.completed = anyio.Event()

    async def notify(self, method: str, params: JsonObject) -> None:
        """pipeline notification payload를 저장하고 완료 이벤트를 표시한다."""
        self.messages.append((method, params))
        if method == "run.status" and params.get("status") in {"completed", "failed"}:
            self.completed.set()

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        """feedback request를 받은 뒤 테스트가 해제할 때까지 대기한다."""
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
        """BackendApp이 요청한 background coroutine을 test TaskGroup에 올린다."""
        self.task_group.start_soon(func, *args)


def test_settings_handlers_are_hot_reload() -> None:
    """settings.set 결과가 backend handler의 다음 호출에 즉시 반영되는지 확인한다."""
    app = create_app(BackendConfig(openai_api_key="sk-test-12345678"))

    result = app.settings_set(
        SettingsSetParams(key="source.splunk.indices", value=["security"]),
    )

    assert result["applied"] == "hot-reload"
    assert app.settings_get()["sources"]["splunk"]["indices"] == ["security"]
    assert app.settings_get()["openai_api_key_masked"] == "set"


def test_settings_get_redacts_source_url_credentials() -> None:
    """settings.get이 source URL password를 마스킹하는지 확인한다."""
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
    """monitoring 조회 시작 시간이 backend process 시작 시각인지 확인한다."""
    app = create_app(BackendConfig(openai_api_key="sk-test-12345678"))
    old_usage = make_usage(
        uuid4(),
        AgentName.ORCHESTRATOR,
        "old run",
        "gpt-5.4-mini",
        100,
    ).model_copy(update={"created_at": app.started_at - timedelta(seconds=1)})
    new_usage = make_usage(
        uuid4(),
        AgentName.ORCHESTRATOR,
        "new run",
        "gpt-5.4-mini",
        7,
    ).model_copy(update={"created_at": datetime.now(UTC)})
    app.store.add_usage(old_usage)
    app.store.add_usage(new_usage)

    result = app.monitoring_query(MonitoringQueryParams(scope="session"))

    assert result["total"]["tokens"] == 7


@pytest.mark.anyio
async def test_pipeline_run_rejects_missing_required_settings() -> None:
    """OpenSearch 설정이 없으면 pipeline.run이 시작되지 않는지 확인한다."""
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
    """선택 source가 하나면 pipeline.run이 거부되는지 확인한다."""
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
    """normalization model 설정이 없으면 pipeline.run이 거부되는지 확인한다."""
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
async def test_pipeline_run_requires_openai_provider() -> None:
    """OpenAI provider가 없으면 agent pipeline을 시작하지 않는지 확인한다."""
    app = create_app(BackendConfig())

    with pytest.raises(ProviderError, match="OpenAI API key is not configured"):
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
async def test_pipeline_run_rejects_invalid_openai_key_before_mapping() -> None:
    """OpenAI key 검증 실패 시 mapping 호출 전 pipeline이 중단되는지 확인한다."""
    provider = FailingProvider()
    app = BackendApp(
        BackendConfig(),
        store=_configured_store(),
        connectors=default_connectors(),
        cache=InMemoryMappingCache(),
        llm_provider=provider,
    )

    with pytest.raises(ProviderError, match="OpenAI API key is invalid"):
        await app.pipeline_run(
            PipelineRunParams(
                sources=[
                    SourceSelection(solution="elasticsearch", index="logs-2026"),
                    SourceSelection(solution="splunk", index="main"),
                ],
            ),
            RecordingPeer(),
        )

    assert provider.validate_calls == ["gpt-orchestrator"]
    assert provider.complete_called is False


@pytest.mark.anyio
async def test_pipeline_records_agent_usage_with_settings_prompts() -> None:
    """설정된 system prompt로 LLM을 호출하고 usage를 저장하는지 확인한다."""
    store = _configured_store()
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

    assert provider.validate_calls == [
        "gpt-orchestrator",
        "gpt-profiler",
        "gpt-normalizer",
        "gpt-validator",
    ]
    assert {call["model"] for call in provider.calls} == {
        "gpt-orchestrator",
        "gpt-profiler",
        "gpt-normalizer",
        "gpt-validator",
    }
    assert provider.calls
    normalization_calls = [
        call for call in provider.calls if call["model"] == "gpt-normalizer"
    ]
    assert normalization_calls
    assert all(
        "NORMALIZE SYSTEM" in str(call["prompt"]) for call in normalization_calls
    )
    usage = store.list_usage()
    for agent in (
        AgentName.ORCHESTRATOR,
        AgentName.SCHEMA_PROFILER,
        AgentName.NORMALIZATION,
        AgentName.VALIDATOR,
    ):
        agent_usage = [row for row in usage if row.agent == agent]
        assert agent_usage
        assert len(agent_usage) == 1
        assert sum(row.total_tokens for row in agent_usage) > 0
        assert sum(row.cost_usd for row in agent_usage) > 0


def _configured_store() -> InMemoryStore:
    """pipeline handler 테스트에 필요한 최소 settings store를 만든다."""
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
        "agent.normalization.system_prompt": "NORMALIZE SYSTEM",
    }.items():
        store.set_setting(key, value)
    return store


@pytest.mark.anyio
async def test_opensearch_loader_is_refreshed_from_current_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """현재 settings의 OpenSearch index가 loader 재생성에 반영되는지 확인한다."""
    app = create_app(BackendConfig())
    constructed_urls: list[str | None] = []

    class CapturingOpenSearchLoader:
        """설정 hot-reload가 만든 OpenSearch URL을 기록하는 loader 대역이다."""

        def __init__(
            self,
            url: str | None = None,
            *,
            username: str | None = None,
            password: str | None = None,
        ) -> None:
            """pipeline refresh 테스트가 관찰할 loader source 목록을 초기화한다."""
            del username, password
            constructed_urls.append(url)

        def index_normalized(
            self,
            index: str,
            doc_id: str,
            document: JsonObject,
        ) -> str:
            """적재 요청을 성공한 것처럼 doc_id로 응답한다."""
            del index, document
            return doc_id

        def fetch_by_id(self, index: str, doc_id: str) -> JsonObject | None:
            """hot-reload 테스트에서는 normalized 문서가 없다고 반환한다."""
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
    """feedback 대기 중인 run이 있으면 새 pipeline.run을 거부하는지 확인한다."""
    app = BackendApp(
        BackendConfig(),
        store=_configured_store(),
        connectors=default_connectors(),
        cache=InMemoryMappingCache(),
        llm_provider=RecordingProvider(),
    )
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
