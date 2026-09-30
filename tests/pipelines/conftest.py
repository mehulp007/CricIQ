"""Shared fixtures: a Cricsheet archive, raw snapshot and warehouse built from
the committed edge-case matches in tests/fixtures/cricsheet."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from criciq_core import paths
from criciq_pipelines.extract import extract_archive
from criciq_pipelines.raw import RawSnapshot, store_snapshot
from criciq_pipelines.warehouse import BuildInputs, build_warehouse

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cricsheet"
MATCHES_DIR = FIXTURES / "matches"
PEOPLE_CSV = FIXTURES / "people.csv"


def load_match(match_id: int) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((MATCHES_DIR / f"{match_id}.json").read_text("utf-8"))
    return doc


@pytest.fixture(scope="session")
def fixture_archive(tmp_path_factory: pytest.TempPathFactory) -> Path:
    archive = tmp_path_factory.mktemp("cricsheet") / "ipl_json.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(MATCHES_DIR.glob("*.json")):
            zf.write(path, arcname=path.name)
    return archive


@pytest.fixture(scope="session")
def fixture_snapshot(
    fixture_archive: Path, tmp_path_factory: pytest.TempPathFactory
) -> RawSnapshot:
    return store_snapshot(fixture_archive, PEOPLE_CSV, tmp_path_factory.mktemp("raw"))


@pytest.fixture(scope="session")
def fixture_interim(
    fixture_snapshot: RawSnapshot, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    out = tmp_path_factory.mktemp("interim")
    extract_archive(fixture_snapshot.archive, out)
    return out


@pytest.fixture(scope="session")
def fixture_warehouse(
    fixture_snapshot: RawSnapshot, fixture_interim: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    target = tmp_path_factory.mktemp("warehouse") / "criciq.duckdb"
    build_warehouse(
        BuildInputs(
            interim_dir=fixture_interim,
            people_csv=fixture_snapshot.people,
            data_version=fixture_snapshot.version,
            attributes_csv=paths.reference_dir() / "player_attributes.csv",
        ),
        target,
    )
    return target
