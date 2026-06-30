from pathlib import Path


def test_initial_migration_defines_required_tables() -> None:
    """초기 migration SQL에 필수 테이블이 들어 있는지 확인한다."""
    sql = Path("src/scala_backend/migrations/001_initial.sql").read_text()

    for table in (
        "scala_settings",
        "scala_runs",
        "scala_agent_usage",
        "scala_data_lineage_metadata",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "UNIQUE (run_id, agent)" in sql
