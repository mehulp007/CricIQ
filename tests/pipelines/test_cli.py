import shutil
from pathlib import Path

import duckdb
import pytest
from typer.testing import CliRunner

from criciq_pipelines import extras
from criciq_pipelines.cli import app
from tests.conftest import PEOPLE_CSV

runner = CliRunner()


def test_paths_command_lists_locations() -> None:
    result = runner.invoke(app, ["paths"])
    assert result.exit_code == 0
    assert "warehouse" in result.output
    assert "cricket.duckdb" in result.output
    assert "ipl.duckdb" in result.output


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
    assert (tmp_path / "data" / "warehouse" / "cricket.duckdb").exists()
    assert (tmp_path / "data" / "warehouse" / "ipl.duckdb").exists()
    assert (tmp_path / "data" / "warehouse" / "validation.json").exists()
    text = report.read_text("utf-8")
    assert "**Overall status:** PASS" in text
    assert "| 1181768 |" in text


def _published(tmp_path: Path, scored: Path) -> Path:
    exports = tmp_path / "data" / "exports"
    exports.mkdir(parents=True)
    shutil.copyfile(scored, exports / "serving.duckdb")
    return exports / "serving.duckdb"


def test_extras_with_nothing_registered_leaves_the_data_alone(
    fixture_scored_serving_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRICIQ_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(extras, "EXTRAS", ())
    serving = _published(tmp_path, fixture_scored_serving_db)
    before = serving.stat().st_mtime_ns
    result = runner.invoke(app, ["extras", "--competition", "ipl"])
    assert result.exit_code == 0, result.output
    assert "(no tables)" in result.output
    assert serving.stat().st_mtime_ns == before


def test_extras_adds_tables_and_keeps_the_scores(
    fixture_scored_serving_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRICIQ_DATA_DIR", str(tmp_path / "data"))
    stand_in = extras.Extra(
        "scored innings",
        ("extra_scored_innings",),
        lambda con: con.execute(
            "CREATE TABLE extra_scored_innings AS "
            "SELECT DISTINCT match_id, innings_no FROM wp_predictions"
        ),
        needs_scores=True,
    )
    monkeypatch.setattr(extras, "EXTRAS", (stand_in,))
    serving = _published(tmp_path, fixture_scored_serving_db)
    result = runner.invoke(app, ["extras", "--competition", "IPL"])
    assert result.exit_code == 0, result.output
    assert "extra_scored_innings" in result.output
    with duckdb.connect(str(serving), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM extra_scored_innings").fetchone() != (0,)
        assert con.execute("SELECT count(*) FROM wp_predictions").fetchone() != (0,)


def test_extras_skips_a_competition_without_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRICIQ_DATA_DIR", str(tmp_path / "data"))
    result = runner.invoke(app, ["extras", "--competition", "BBL"])
    assert result.exit_code == 0, result.output
    assert "BBL: no serving database yet" in result.output
