from pathlib import Path

import pytest
from typer.testing import CliRunner

from criciq_pipelines.cli import app
from tests.pipelines.conftest import PEOPLE_CSV

runner = CliRunner()


def test_paths_command_lists_locations() -> None:
    result = runner.invoke(app, ["paths"])
    assert result.exit_code == 0
    assert "warehouse" in result.output
    assert "criciq.duckdb" in result.output


def test_offline_end_to_end_run(
    fixture_archive: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRICIQ_DATA_DIR", str(tmp_path / "data"))
    snapshot = runner.invoke(app, ["snapshot", str(fixture_archive), str(PEOPLE_CSV)])
    assert snapshot.exit_code == 0, snapshot.output

    report = tmp_path / "report.md"
    result = runner.invoke(app, ["run", "--no-download", "--report", str(report)])
    assert result.exit_code == 0, result.output
    assert "[FAIL]" not in result.output
    assert (tmp_path / "data" / "warehouse" / "criciq.duckdb").exists()
    assert (tmp_path / "data" / "warehouse" / "validation.json").exists()
    text = report.read_text("utf-8")
    assert "**Overall status:** PASS" in text
    assert "| 1181768 |" in text
