from __future__ import annotations

import json
from pathlib import Path
from typing import LiteralString, cast

import psycopg

from scala_backend.store import InMemoryStore, seed_dev_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def migrate_postgres(database_url: str) -> None:
    """PostgreSQL schema 파일을 순서대로 적용한다."""
    ddl = "\n".join(path.read_text() for path in sorted(MIGRATIONS_DIR.glob("*.sql")))
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(cast(LiteralString, ddl))
        connection.commit()


def seed_postgres(
    database_url: str,
    overrides: dict[str, object] | None = None,
) -> None:
    """PostgreSQL 초기화의 seed postgres 변경을 저장 계층에 반영한다."""
    store = InMemoryStore()
    seed_dev_settings(store, overrides)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for key, value in store.get_settings().items():
                cursor.execute(
                    """
                    INSERT INTO scala_settings (setting_key, setting_value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (setting_key)
                    DO UPDATE SET setting_value = EXCLUDED.setting_value,
                                  updated_at = EXCLUDED.updated_at
                    """,
                    (key, json.dumps(value)),
                )
        connection.commit()
