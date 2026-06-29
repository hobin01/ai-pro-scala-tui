from pathlib import Path


def test_initial_migration_defines_required_tables() -> None:
    """initial migration defines required tables 동작을 검증한다."""
    sql = Path("src/scala_backend/migrations/001_initial.sql").read_text()

    for table in (
        "scala_settings",
        "scala_runs",
        "scala_agent_usage",
        "scala_data_lineage_metadata",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
