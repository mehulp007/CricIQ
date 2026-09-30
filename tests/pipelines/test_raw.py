import datetime as dt
import json
import zipfile
from pathlib import Path

import pytest

from criciq_pipelines.raw import (
    compute_version,
    latest_match_date,
    latest_snapshot,
    store_snapshot,
)
from tests.pipelines.conftest import PEOPLE_CSV


def test_latest_match_date_scans_json_without_readme(fixture_archive: Path) -> None:
    # The newest fixture match is the 2025 final.
    assert latest_match_date(fixture_archive) == dt.date(2025, 6, 3)


def test_latest_match_date_prefers_readme(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(
            "README.txt",
            "2026-05-31 - club - IPL - male - 1 - A vs B\n"
            "2026-05-29 - club - IPL - male - 2 - C vs D\n",
        )
        zf.writestr("1.json", json.dumps({"info": {"dates": ["2001-01-01"]}}))
    assert latest_match_date(archive) == dt.date(2026, 5, 31)


def test_version_is_content_addressed(fixture_archive: Path, tmp_path: Path) -> None:
    version = compute_version(fixture_archive, PEOPLE_CSV)
    assert version.startswith("2025-06-03.")
    assert compute_version(fixture_archive, PEOPLE_CSV) == version

    changed = tmp_path / "people.csv"
    changed.write_text(PEOPLE_CSV.read_text("utf-8") + "\n", "utf-8")
    assert compute_version(fixture_archive, changed) != version


def test_store_snapshot_is_idempotent_and_updates_latest(
    fixture_archive: Path, tmp_path: Path
) -> None:
    first = store_snapshot(fixture_archive, PEOPLE_CSV, tmp_path)
    second = store_snapshot(fixture_archive, PEOPLE_CSV, tmp_path)
    assert first == second
    assert latest_snapshot(tmp_path) == first
    manifest = first.manifest
    assert manifest["data_version"] == first.version
    assert manifest["match_files"] == 14
    files = manifest["files"]
    assert isinstance(files, dict)
    assert set(files) == {"ipl_json.zip", "people.csv"}


def test_latest_snapshot_requires_a_download(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="criciq-data download"):
        latest_snapshot(tmp_path)
