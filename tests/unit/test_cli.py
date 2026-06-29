from typer.testing import CliRunner

from scala_backend.cli import app


def test_cli_help_lists_backend_commands() -> None:
    """CLI help가 backend 실행 옵션을 노출하는지 확인한다."""
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "serve" in result.output
    assert "migrate" in result.output
    assert "seed-dev-settings" in result.output
    assert "ingest-ocsf" in result.output
