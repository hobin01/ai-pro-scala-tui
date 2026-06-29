from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from scala_backend.config import DEFAULT_OPENAI_MODEL
from scala_backend.models import (
    ALL_AGENTS,
    AgentName,
    JsonValue,
    LineageRecord,
    RunRecord,
    UsageRecord,
)
from scala_backend.store_postgres import PostgresStore as PostgresStore


class BackendStore(Protocol):
    """BackendStore 객체의 책임을 정의한다."""

    def get_settings(self) -> dict[str, JsonValue]:
        """get settings 값을 조회한다."""
        ...

    def set_setting(self, key: str, value: JsonValue) -> None:
        """set setting 값을 저장한다."""
        ...

    def create_run(self, run: RunRecord) -> None:
        """create run 동작을 처리한다."""
        ...

    def update_run(
        self,
        run_id: UUID,
        status: str,
        doc_count: int | None = None,
    ) -> None:
        """update run 상태를 갱신한다."""
        ...

    def add_usage(self, record: UsageRecord) -> None:
        """add usage 동작을 처리한다."""
        ...

    def list_usage(self) -> list[UsageRecord]:
        """list usage 동작을 처리한다."""
        ...

    def add_lineage(self, record: LineageRecord) -> None:
        """add lineage 동작을 처리한다."""
        ...

    def get_lineage(self, opensearch_id: str) -> LineageRecord | None:
        """get lineage 값을 조회한다."""
        ...


class InMemoryStore:
    """InMemoryStore 객체의 책임을 정의한다."""

    def __init__(self) -> None:
        """객체 초기 상태를 준비한다."""
        self._settings: dict[str, JsonValue] = {}
        self._runs: dict[UUID, RunRecord] = {}
        self._usage: list[UsageRecord] = []
        self._lineage: dict[str, LineageRecord] = {}

    def get_settings(self) -> dict[str, JsonValue]:
        """get settings 값을 조회한다."""
        return dict(self._settings)

    def set_setting(self, key: str, value: JsonValue) -> None:
        """set setting 값을 저장한다."""
        self._settings[key] = value

    def create_run(self, run: RunRecord) -> None:
        """create run 동작을 처리한다."""
        self._runs[run.run_id] = run

    def update_run(
        self,
        run_id: UUID,
        status: str,
        doc_count: int | None = None,
    ) -> None:
        """update run 상태를 갱신한다."""
        run = self._runs[run_id]
        now = datetime.now(UTC)
        self._runs[run_id] = run.model_copy(
            update={
                "status": status,
                "doc_count": doc_count,
                "finished_at": now if status != "running" else None,
            },
        )

    def add_usage(self, record: UsageRecord) -> None:
        """add usage 동작을 처리한다."""
        self._usage.append(record)

    def list_usage(self) -> list[UsageRecord]:
        """list usage 동작을 처리한다."""
        return list(self._usage)

    def add_lineage(self, record: LineageRecord) -> None:
        """add lineage 동작을 처리한다."""
        self._lineage[record.opensearch_id] = record

    def get_lineage(self, opensearch_id: str) -> LineageRecord | None:
        """get lineage 값을 조회한다."""
        return self._lineage.get(opensearch_id)


def seed_dev_settings(
    store: BackendStore,
    overrides: dict[str, JsonValue] | None = None,
) -> None:
    """seed dev settings 데이터를 시드한다."""
    entries: dict[str, JsonValue] = {
        **agent_model_settings(DEFAULT_OPENAI_MODEL),
        "agent.orchestrator.system_prompt": (
            "You are the SCALA Orchestrator Agent. Coordinate the workflow and "
            "summarize final Load, Caching, and Lineage results for the user."
        ),
        "agent.schema_profiler.system_prompt": (
            "You are the SCALA Schema Profiler Agent. Profile source fields, "
            "reuse confirmed cache mappings, and inspect OCSF candidates for "
            "cache misses."
        ),
        "agent.normalization.system_prompt": (
            "You are the SCALA Normalization Agent. Generate OCSF mapping rules "
            "and preserve unmapped source fields without data loss."
        ),
        "agent.validator.system_prompt": (
            "You are the SCALA Validator Agent. Verify normalized mappings and "
            "request human feedback only when a decision is ambiguous."
        ),
        "source.elasticsearch.url": "memory://elasticsearch",
        "source.elasticsearch.indices": ["logs-2026"],
        "source.splunk.url": "memory://splunk",
        "source.splunk.indices": ["main"],
        "output.opensearch.url": "memory://opensearch",
        "output.opensearch.index": "scala-normalized",
        "console.kibana.url": "http://localhost:5601",
        "console.splunk.url": "http://localhost:8000",
        "console.opensearch.url": "http://localhost:5602",
    }
    if overrides is not None:
        entries.update(overrides)
    for key, value in entries.items():
        store.set_setting(key, value)


def agent_model_settings(model: str) -> dict[str, JsonValue]:
    """agent model settings 동작을 처리한다."""
    return {
        "agent.orchestrator.model": model,
        "agent.schema_profiler.model": model,
        "agent.normalization.model": model,
        "agent.validator.model": model,
    }


def settings_to_display(
    settings: dict[str, JsonValue],
    openai_key_masked: str,
) -> dict[str, JsonValue]:
    """settings to display 동작을 처리한다."""
    agents: dict[str, JsonValue] = {}
    for agent in ("orchestrator", "schema_profiler", "normalization", "validator"):
        model = settings.get(f"agent.{agent}.model")
        if isinstance(model, str):
            agents[agent] = {"model": model}
    return {
        "agents": agents,
        "sources": _group_sources(settings),
        "output": {
            "opensearch": {
                "url": settings.get("output.opensearch.url"),
                "index": settings.get("output.opensearch.index"),
            },
        },
        "consoles": _group_consoles(settings),
        "openai_api_key_masked": openai_key_masked,
    }


def aggregate_usage(
    usage: Iterable[UsageRecord],
    scope: str,
) -> dict[str, JsonValue]:
    """aggregate usage 동작을 처리한다."""
    now = datetime.now(UTC)
    rows = [
        row for row in usage if scope != "today" or row.created_at.date() == now.date()
    ]
    agents = []
    total_tokens = 0
    last_run_id = ""
    for agent in ALL_AGENTS:
        selected = [row for row in rows if row.agent == agent]
        tokens = sum(row.total_tokens for row in selected)
        last = selected[-1] if selected else None
        total_tokens += tokens
        if last is not None:
            last_run_id = str(last.run_id)
        agents.append(
            {
                "agent": agent.value,
                "model": last.model if last else None,
                "last_activity": last.last_activity if last else "",
                "tokens": tokens,
                "cost": 0,
            },
        )
    return {
        "scope": scope,
        "as_of": now.strftime("%H:%M"),
        "total": {
            "tokens": total_tokens,
            "cost": None,
            "cost_source": "unavailable",
            "last_run_id": last_run_id,
            "runs": len({row.run_id for row in rows}),
        },
        "agents": agents,
    }


def make_usage(
    run_id: UUID,
    agent: AgentName,
    activity: str,
    model: str | None = None,
    tokens: int = 0,
    cost: Decimal = Decimal("0"),
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int = 0,
) -> UsageRecord:
    """make usage 값을 만든다."""
    prompt = tokens if prompt_tokens is None else prompt_tokens
    total = tokens if prompt_tokens is None else prompt + completion_tokens
    return UsageRecord(
        run_id=run_id,
        agent=agent,
        model=model,
        prompt_tokens=prompt,
        completion_tokens=completion_tokens,
        total_tokens=total,
        cost_usd=cost,
        last_activity=activity,
        created_at=datetime.now(UTC),
    )


def _group_sources(settings: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """group sources 내부 처리를 수행한다."""
    return {
        name: {
            "url": _redact_url(settings.get(f"source.{name}.url")),
            "indices": settings.get(f"source.{name}.indices") or [],
        }
        for name in ("elasticsearch", "splunk")
    }


def _group_consoles(settings: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """group consoles 내부 처리를 수행한다."""
    return {
        name: {"url": settings.get(f"console.{name}.url")}
        for name in ("kibana", "splunk", "opensearch")
    }


def _redact_url(value: JsonValue) -> JsonValue:
    """redact url 내부 처리를 수행한다."""
    if not isinstance(value, str) or "@" not in value:
        return value
    parsed = urlsplit(value)
    if not parsed.username:
        return value
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit(
        (
            parsed.scheme,
            f"{parsed.username}:<redacted>@{host}{port}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )
