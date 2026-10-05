import shutil
from pathlib import Path

import duckdb
import pytest

from criciq_pipelines.validation import validate


def test_fixture_warehouse_passes_every_check(fixture_full_warehouse: Path) -> None:
    report = validate(fixture_full_warehouse)
    assert [(c.id, c.sample) for c in report.checks if not c.passed] == []
    assert [g.match_id for g in report.golden if not g.passed] == []
    assert len(report.golden) == 13
    assert report.passed


@pytest.fixture
def tampered(fixture_full_warehouse: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "tampered.duckdb"
    shutil.copy(fixture_full_warehouse, copy)
    return copy


def _execute(path: Path, sql: str) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(sql)
    finally:
        con.close()


def test_inconsistent_innings_total_is_caught(tampered: Path) -> None:
    _execute(
        tampered, "UPDATE innings SET runs = runs + 1 WHERE match_id = 1304066 AND innings_no = 1"
    )
    report = validate(tampered)
    assert "innings_totals_match_ball_by_ball" in {c.id for c in report.checks if not c.passed}
    assert not report.passed


def test_golden_mismatch_is_caught(fixture_full_warehouse: Path, tmp_path: Path) -> None:
    config = Path(__file__).resolve().parents[2] / "config"
    golden = (config / "golden_matches.yaml").read_text("utf-8")
    wrong = golden.replace(
        "result: { winner: MI, by_runs: 1 }", "result: { winner: MI, by_runs: 2 }"
    )
    assert wrong != golden
    (tmp_path / "golden_matches.yaml").write_text(wrong, "utf-8")
    shutil.copy(config / "competitions.yaml", tmp_path / "competitions.yaml")

    report = validate(fixture_full_warehouse, config_dir=tmp_path)
    [result] = [g for g in report.golden if g.match_id == 1181768]
    assert result.mismatches == ["win by runs: expected 2, got 1"]
    assert not report.passed


def test_missing_golden_match_fails_unless_allowed(tampered: Path) -> None:
    _execute(
        tampered,
        """
        DELETE FROM substitutions WHERE match_id = 335982;
        DELETE FROM wickets WHERE match_id = 335982;
        DELETE FROM deliveries WHERE match_id = 335982;
        DELETE FROM innings WHERE match_id = 335982;
        DELETE FROM match_players WHERE match_id = 335982;
        DELETE FROM matches WHERE match_id = 335982;
        """,
    )
    assert not validate(tampered).passed
    assert validate(tampered, require_all_golden=False).passed
