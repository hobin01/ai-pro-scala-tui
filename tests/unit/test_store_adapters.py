from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from scala_backend.cache import MappingDecision, RedisMappingCache
from scala_backend.models import (
    AgentName,
    LineageRecord,
    RunRecord,
    SourceSelection,
    UsageRecord,
)
from scala_backend.store import PostgresStore


@dataclass
class SqlCall:
    sql: str
    params: tuple[object, ...] | None


@dataclass
class FakeCursor:
    calls: list[SqlCall] = field(default_factory=list)
    row: tuple[object, ...] | None = None
    rows: list[tuple[object, ...]] = field(default_factory=list)

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        self.calls.append(SqlCall(sql, params))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


@dataclass
class FakeConnection:
    cursor_obj: FakeCursor
    commits: int = 0

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1


@dataclass
class FakeRedis:
    values: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value


def fake_connect(connection: FakeConnection) -> Callable[[str], FakeConnection]:
    def connect(_url: str) -> FakeConnection:
        return connection

    return connect


def test_postgres_store_writes_expected_tables_when_records_are_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        "scala_backend.store_postgres.psycopg.connect",
        fake_connect(connection),
    )
    run_id = uuid4()
    started_at = datetime(2026, 1, 2, tzinfo=UTC)
    store = PostgresStore("postgresql://example/scalas")

    store.set_setting("source.elasticsearch.indices", ["logs-2026"])
    store.create_run(
        RunRecord(
            run_id=run_id,
            status="running",
            selected_sources=[
                SourceSelection(solution="elasticsearch", index="logs-2026")
            ],
            started_at=started_at,
        )
    )
    store.add_usage(
        record=_usage_record(run_id, started_at),
    )
    store.add_lineage(
        LineageRecord(
            run_id=run_id,
            source_solution="elasticsearch",
            source_index="logs-2026",
            source_doc_id="raw-1",
            opensearch_index="scala-normalized",
            opensearch_id="os-1",
            raw_document={"src_ip": "10.0.0.1"},
            normalized_document={"src_endpoint": {"ip": "10.0.0.1"}},
            created_at=started_at,
        )
    )
    store.update_run(run_id, "completed", 1)

    sql = "\n".join(call.sql for call in cursor.calls)
    assert "INSERT INTO scala_settings" in sql
    assert "INSERT INTO scala_runs" in sql
    assert "INSERT INTO scala_agent_usage" in sql
    assert "INSERT INTO scala_data_lineage_metadata" in sql
    assert "UPDATE scala_runs" in sql
    setting_params = cursor.calls[0].params
    assert setting_params == (
        "source.elasticsearch.indices",
        json.dumps(["logs-2026"]),
    )
    assert connection.commits == 5


def test_postgres_store_reads_lineage_metadata_when_opensearch_id_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    created_at = datetime(2026, 1, 2, tzinfo=UTC)
    cursor = FakeCursor(
        row=(
            run_id,
            "splunk",
            "main",
            "bkt:cd",
            "scala-normalized",
            "os-2",
            created_at,
        ),
    )
    monkeypatch.setattr(
        "scala_backend.store_postgres.psycopg.connect",
        fake_connect(FakeConnection(cursor)),
    )

    record = PostgresStore("postgresql://example/scalas").get_lineage("os-2")

    assert record == LineageRecord(
        run_id=run_id,
        source_solution="splunk",
        source_index="main",
        source_doc_id="bkt:cd",
        opensearch_index="scala-normalized",
        opensearch_id="os-2",
        raw_document={},
        normalized_document={},
        created_at=created_at,
    )


def test_redis_mapping_cache_round_trips_mapping_decision_as_json() -> None:
    client = FakeRedis()
    cache = RedisMappingCache(client)
    decision = MappingDecision(
        source_field="src_ip",
        source_type="keyword",
        action="map",
        ocsf_field="src_endpoint.ip",
        ocsf_type="ip_t",
    )

    cache.set("source|idx|src_ip|keyword", decision)
    loaded = cache.get("source|idx|src_ip|keyword")

    assert loaded == decision
    assert json.loads(client.values["source|idx|src_ip|keyword"]) == {
        "source_field": "src_ip",
        "source_type": "keyword",
        "action": "map",
        "ocsf_field": "src_endpoint.ip",
        "ocsf_type": "ip_t",
    }


def _usage_record(run_id: UUID, created_at: datetime) -> UsageRecord:
    return UsageRecord(
        run_id=run_id,
        agent=AgentName.NORMALIZATION,
        model="gpt-5-mini",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost_usd=Decimal("0.01"),
        last_activity="mapped fields",
        created_at=created_at,
    )
