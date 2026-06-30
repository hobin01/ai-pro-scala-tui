from typer.testing import CliRunner

from scala_backend.cli import (
    app,
    es_seed_batches,
    settings_overrides,
    splunk_seed_batches,
)
from scala_backend.config import BackendConfig


def test_cli_help_lists_backend_commands() -> None:
    """CLI help가 backend 실행 옵션을 노출하는지 확인한다."""
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "serve" in result.output
    assert "migrate" in result.output
    assert "seed-dev-settings" in result.output
    assert "ingest-ocsf" in result.output


def test_dev_settings_expose_four_complex_source_indices() -> None:
    """개발 settings가 복잡한 4개 source index를 노출하는지 확인한다."""
    settings = settings_overrides(BackendConfig())

    assert settings["source.elasticsearch.indices"] == [
        "scala-es-network",
        "scala-es-endpoint",
    ]
    assert settings["source.splunk.indices"] == ["main", "security"]
    assert settings["model.gpt-5.4-mini.input_cost_per_1m"] == 0.75
    assert settings["model.gpt-5.4-mini.output_cost_per_1m"] == 4.5


def test_seed_batches_split_count_across_four_indices() -> None:
    """seed batch가 Elasticsearch/Splunk index별 개수를 균등 분배하는지 확인한다."""
    es = es_seed_batches(8)
    splunk = splunk_seed_batches(8)

    assert {key: len(value) for key, value in es.items()} == {
        "scala-es-network": 4,
        "scala-es-endpoint": 4,
    }
    assert {key: len(value) for key, value in splunk.items()} == {
        "main": 4,
        "security": 4,
    }
    assert "vendor_custom" in es["scala-es-network"][0]
    assert es["scala-es-endpoint"][0]["parent_process"] is None
    assert "splunk_custom" in splunk["main"][0]
    assert isinstance(splunk["security"][0]["_raw"], str)
