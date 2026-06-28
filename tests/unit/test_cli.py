from typer.testing import CliRunner

from scala_backend.cli import app


def test_cli_help_lists_backend_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "serve" in result.output
    assert "migrate" in result.output
    assert "seed-dev-settings" in result.output
    assert "ingest-ocsf" in result.output
