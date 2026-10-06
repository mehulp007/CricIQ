"""Data-quality reports: the main (IPL) report and one per other T20 competition."""

from __future__ import annotations

from pathlib import Path

import pytest

from criciq_pipelines.reference import load_competitions
from criciq_pipelines.report import (
    render_competition_report,
    render_report,
    report_path_for,
)
from criciq_pipelines.validation import ValidationReport, validate


@pytest.fixture(scope="module")
def validation(fixture_full_warehouse: Path) -> ValidationReport:
    return validate(fixture_full_warehouse, require_all_golden=False)


def _report(warehouse: Path, validation: ValidationReport, competition: str) -> str:
    return render_competition_report(warehouse, validation, load_competitions().get(competition))


def test_the_main_report_links_each_competitions_report(
    fixture_warehouse: Path, fixture_full_warehouse: Path, validation: ValidationReport
) -> None:
    text = render_report(fixture_warehouse, validation, fixture_full_warehouse)
    assert text.startswith("# Data Quality Report\n")
    for competition in ("bbl", "psl", "cpl", "sa20", "t20i"):
        assert f"(data-quality/{competition}.md)" in text
    assert "(data-quality/odi.md)" not in text  # one-day and Test reports come later


def test_a_competition_report_covers_its_own_matches(
    fixture_full_warehouse: Path, validation: ValidationReport
) -> None:
    text = _report(fixture_full_warehouse, validation, "BBL")
    assert text.startswith("# Data Quality Report: Big Bash League\n")
    assert "| teams | 8 |" in text
    assert "| 2023/24 | 2 |" in text  # seasons named by the years they span
    assert "| 1386137 | BBL 2023/24 final — Brisbane Heat by 54 runs | pass |" in text
    assert "1343973" not in text  # the SA20 final belongs to the SA20's report
    for section in ("## Teams", "## Quarantined matches", "## Grounds added automatically"):
        assert section in text


def test_notes_and_quarantine_are_listed_with_their_matches(
    fixture_full_warehouse: Path, validation: ValidationReport
) -> None:
    text = _report(fixture_full_warehouse, validation, "T20I")
    assert "- **Overall status:** PASS (" in text
    assert "- `eleven_players_per_side`: 1481295" in text  # a side of ten
    assert "| 1229824 | player_on_both_sides |" in text
    assert "| eleven_players_per_side" not in _report(fixture_full_warehouse, validation, "PSL")


def test_competition_reports_sit_beside_the_main_report(tmp_path: Path) -> None:
    main = tmp_path / "docs" / "data-quality-report.md"
    assert report_path_for(main, "SA20") == tmp_path / "docs" / "data-quality" / "sa20.md"
