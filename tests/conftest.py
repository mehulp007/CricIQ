"""Shared fixtures: a Cricsheet archive, raw snapshot, warehouse, serving
database and players database built from the committed edge-case matches in
tests/fixtures/cricsheet."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from criciq_core import paths
from criciq_ml import cli as ml_cli
from criciq_ml.data import load_inputs
from criciq_ml.features import build_states
from criciq_pipelines.export import export_serving
from criciq_pipelines.extract import extract_archive
from criciq_pipelines.player_db import export_players
from criciq_pipelines.raw import RawSnapshot, store_snapshot
from criciq_pipelines.scope import build_scope
from criciq_pipelines.warehouse import BuildInputs, build_warehouse

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cricsheet"
MATCHES_DIR = FIXTURES / "matches"
# The T20 competitions in config/competitions.yaml, in config order.
T20_COMPETITIONS = ("IPL", "BBL", "PSL", "CPL", "SA20", "T20I")
PEOPLE_CSV = FIXTURES / "people.csv"


def load_match(match_id: int) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((MATCHES_DIR / f"{match_id}.json").read_text("utf-8"))
    return doc


@pytest.fixture(scope="session")
def fixture_archive(tmp_path_factory: pytest.TempPathFactory) -> Path:
    archive = tmp_path_factory.mktemp("cricsheet") / "fixtures_json.zip"
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
    extract_archive(fixture_snapshot.archives, out)
    return out


@pytest.fixture(scope="session")
def fixture_full_warehouse(
    fixture_snapshot: RawSnapshot, fixture_interim: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Every competition in the fixtures (the multi-competition warehouse)."""
    target = tmp_path_factory.mktemp("warehouse") / "cricket.duckdb"
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


@pytest.fixture(scope="session")
def fixture_warehouse(
    fixture_full_warehouse: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """The IPL warehouse in the v1 shape, as the export and the models read it."""
    target = tmp_path_factory.mktemp("scope") / "ipl.duckdb"
    build_scope(fixture_full_warehouse, "IPL", target)
    return target


@pytest.fixture(scope="session")
def fixture_serving_db(fixture_warehouse: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("exports") / "serving.duckdb"
    export_serving(fixture_warehouse, target)
    return target


@pytest.fixture(scope="session")
def fixture_players_db(
    fixture_full_warehouse: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Player Lab tables for every T20 competition in the fixtures, and all T20."""
    target = tmp_path_factory.mktemp("players") / "players.duckdb"
    export_players(fixture_full_warehouse, target)
    return target


@pytest.fixture(scope="session")
def fixture_states(fixture_warehouse: Path) -> pd.DataFrame:
    """Win probability features for every state of the fixture matches."""
    return build_states(load_inputs(fixture_warehouse))


@pytest.fixture(scope="session")
def fixture_pooled_warehouse(
    fixture_full_warehouse: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Every T20 competition in the fixtures, in one time order (what pooled models read)."""
    target = tmp_path_factory.mktemp("pooled") / "t20.duckdb"
    build_scope(fixture_full_warehouse, list(T20_COMPETITIONS), target)
    return target


@pytest.fixture(scope="session")
def fixture_scored_serving_db(
    fixture_serving_db: Path,
    fixture_warehouse: Path,
    fixture_pooled_warehouse: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """The fixture serving database scored as `criciq-ml score` scores the IPL's: with the
    committed models serving the IPL, each from the data it was trained on."""
    target = tmp_path_factory.mktemp("scored") / "serving.duckdb"
    shutil.copyfile(fixture_serving_db, target)
    ml_cli._score_serving(target, ml_cli._Sources(fixture_warehouse, fixture_pooled_warehouse))
    return target


@pytest.fixture(scope="session")
def fixture_scored_players_db(
    fixture_players_db: Path,
    fixture_warehouse: Path,
    fixture_pooled_warehouse: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """The fixture players database with win probability added and rating constants,
    as `criciq-ml score` writes them."""
    target = tmp_path_factory.mktemp("scored-players") / "players.duckdb"
    shutil.copyfile(fixture_players_db, target)
    ml_cli._score_players(target, ml_cli._Sources(fixture_warehouse, fixture_pooled_warehouse))
    return target
