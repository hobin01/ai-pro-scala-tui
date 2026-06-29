from __future__ import annotations

import json
from uuid import UUID

import psycopg

from scala_backend.models import (
    AgentName,
    JsonValue,
    LineageRecord,
    RunRecord,
    UsageRecord,
)


class PostgresStore:
    """PostgresStore 객체의 책임을 정의한다."""

    def __init__(self, database_url: str) -> None:
        """객체 초기 상태를 준비한다."""
        self._database_url = database_url

    def get_settings(self) -> dict[str, JsonValue]:
        """get settings 값을 조회한다."""
        with (
            psycopg.connect(self._database_url) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT setting_key, setting_value FROM scala_settings "
                "ORDER BY setting_key",
            )
            return dict(cursor.fetchall())

    def set_setting(self, key: str, value: JsonValue) -> None:
        """set setting 값을 저장한다."""
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scala_settings (setting_key, setting_value, "
                    "updated_at) VALUES (%s, %s::jsonb, NOW()) ON CONFLICT "
                    "(setting_key) DO UPDATE SET "
                    "setting_value = EXCLUDED.setting_value, "
                    "updated_at = EXCLUDED.updated_at",
                    (key, json.dumps(value)),
                )
            connection.commit()

    def create_run(self, run: RunRecord) -> None:
        """create run 동작을 처리한다."""
        selected_sources = [
            source.model_dump(mode="json") for source in run.selected_sources
        ]
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scala_runs (run_id, status, selected_sources, "
                    "doc_count, started_at, finished_at) "
                    "VALUES (%s, %s, %s::jsonb, %s, %s, %s)",
                    (
                        run.run_id,
                        run.status,
                        json.dumps(selected_sources),
                        run.doc_count,
                        run.started_at,
                        run.finished_at,
                    ),
                )
            connection.commit()

    def update_run(
        self,
        run_id: UUID,
        status: str,
        doc_count: int | None = None,
    ) -> None:
        """update run 상태를 갱신한다."""
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE scala_runs SET status = %s, doc_count = %s, "
                    "finished_at = CASE WHEN %s = 'running' THEN NULL "
                    "ELSE NOW() END WHERE run_id = %s",
                    (status, doc_count, status, run_id),
                )
            connection.commit()

    def add_usage(self, record: UsageRecord) -> None:
        """add usage 동작을 처리한다."""
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scala_agent_usage (run_id, agent, model, "
                    "prompt_tokens, completion_tokens, total_tokens, cost_usd, "
                    "last_activity, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        record.run_id,
                        record.agent.value,
                        record.model,
                        record.prompt_tokens,
                        record.completion_tokens,
                        record.total_tokens,
                        record.cost_usd,
                        record.last_activity,
                        record.created_at,
                    ),
                )
            connection.commit()

    def list_usage(self) -> list[UsageRecord]:
        """list usage 동작을 처리한다."""
        with (
            psycopg.connect(self._database_url) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT run_id, agent, model, prompt_tokens, "
                "completion_tokens, total_tokens, cost_usd, last_activity, "
                "created_at FROM scala_agent_usage ORDER BY created_at, id",
            )
            return [
                UsageRecord(
                    run_id=run_id,
                    agent=AgentName(agent),
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    last_activity=last_activity or "",
                    created_at=created_at,
                )
                for (
                    run_id,
                    agent,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    last_activity,
                    created_at,
                ) in cursor.fetchall()
            ]

    def add_lineage(self, record: LineageRecord) -> None:
        """add lineage 동작을 처리한다."""
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scala_data_lineage_metadata (run_id, "
                    "source_solution, source_index, source_doc_id, "
                    "opensearch_index, opensearch_id, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        record.run_id,
                        record.source_solution,
                        record.source_index,
                        record.source_doc_id,
                        record.opensearch_index,
                        record.opensearch_id,
                        record.created_at,
                    ),
                )
            connection.commit()

    def get_lineage(self, opensearch_id: str) -> LineageRecord | None:
        """get lineage 값을 조회한다."""
        with (
            psycopg.connect(self._database_url) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT run_id, source_solution, source_index, source_doc_id, "
                "opensearch_index, opensearch_id, created_at "
                "FROM scala_data_lineage_metadata WHERE opensearch_id = %s "
                "ORDER BY created_at DESC LIMIT 1",
                (opensearch_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        (
            run_id,
            source_solution,
            source_index,
            source_doc_id,
            opensearch_index,
            found_opensearch_id,
            created_at,
        ) = row
        return LineageRecord(
            run_id=run_id,
            source_solution=source_solution,
            source_index=source_index,
            source_doc_id=source_doc_id,
            opensearch_index=opensearch_index,
            opensearch_id=found_opensearch_id,
            raw_document={},
            normalized_document={},
            created_at=created_at,
        )
