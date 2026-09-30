from typer.testing import CliRunner

from criciq_pipelines.cli import app


def test_paths_command_lists_locations() -> None:
    result = CliRunner().invoke(app, ["paths"])
    assert result.exit_code == 0
    assert "warehouse" in result.output
    assert "criciq.duckdb" in result.output
