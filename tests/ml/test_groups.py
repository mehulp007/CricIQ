"""Model groups: each set of competitions trains on and is served by models of its own
(ADR-0013)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from criciq_core import paths
from criciq_core.groups import group, group_of, model_groups
from criciq_core.phases import model_format
from criciq_ml import cli as ml_cli
from criciq_ml import formats, players_scoring, ratings, registry
from criciq_pipelines import pipeline
from criciq_pipelines.reference import load_competitions

LEAGUES = ["BBL", "CPL", "PSL", "SA20"]


def test_every_served_competition_has_exactly_one_group() -> None:
    served = [c.id for c in load_competitions().competitions if c.switcher and c.format != "Test"]
    for competition in served:
        owner = group_of(competition)
        assert owner is not None, competition
        assert sum(competition in g.competitions for g in model_groups().groups) == 1


def test_groups_never_mix_the_ipl_leagues_and_internationals() -> None:
    assert group("ipl").competitions == ["IPL"]
    assert group("leagues").competitions == LEAGUES
    assert group("t20i").competitions == ["T20I"]
    assert group("odi").competitions == ["ODI"]
    copies = [g.copy_name for g in model_groups().groups]
    assert len(set(copies)) == len(copies)


def test_each_group_has_its_own_folders_and_format() -> None:
    config = paths.config_dir() / "models"
    with formats.use_group("leagues"):
        assert model_format() == "T20"
        assert formats.config_path("ratings") == config / "leagues" / "ratings.yaml"
        assert formats.models_root() == paths.models_dir() / "leagues"
    with formats.use_group("odi"):
        assert model_format() == "ODI"
        assert formats.models_root() == paths.models_dir() / "odi"
    # The IPL's versions keep v1's places, marked by CURRENT.IPL.
    with formats.use_group("ipl"):
        assert formats.models_root() == paths.models_dir()
        assert formats.config_path("simulator") == config / "ipl" / "simulator.yaml"
        assert registry.current_version(registry.NAME) == registry.current_version(
            registry.NAME, "IPL"
        )
    assert formats.current_group() is None


def test_the_pipeline_builds_a_copy_per_group() -> None:
    copies = pipeline.model_copies()
    assert sorted(copies["LEAGUES"]) == LEAGUES
    assert copies["T20I"] == ["T20I"]
    assert copies["ODI"] == ["ODI"]
    assert "IPL" not in copies  # the IPL's is its scoped copy
    assert pipeline.POOLED in copies


def test_a_model_scores_from_its_own_groups_copy(tmp_path: Path) -> None:
    sources = ml_cli._Sources(tmp_path / "ipl.duckdb", tmp_path / "t20.duckdb")

    def copy(*competitions: str) -> Path:
        return sources.warehouse({"trained_on": {"competitions": list(competitions)}})

    assert copy() == tmp_path / "ipl.duckdb"  # v1's manifests list nothing
    assert copy("IPL") == tmp_path / "ipl.duckdb"
    assert copy(*LEAGUES) == paths.warehouse_path("LEAGUES")
    assert copy("BBL", "PSL") == paths.warehouse_path("LEAGUES")
    assert copy("T20I") == paths.warehouse_path("T20I")
    assert copy("ODI") == paths.warehouse_path("ODI")
    # The pooled versions of V2-3 span groups.
    assert copy("BBL", "IPL", "T20I") == tmp_path / "t20.duckdb"


@pytest.fixture
def registries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty models folder holding only pooled T20 versions."""
    monkeypatch.setenv("CRICIQ_MODELS_DIR", str(tmp_path))
    for name, pointers in {
        registry.NAME: {"CURRENT": "2.0.0"},
        registry.SIMULATOR: {"CURRENT": "1.0.0", "CURRENT.BBL": "2.1.0"},
    }.items():
        for pointer, version in pointers.items():
            (tmp_path / name).mkdir(exist_ok=True)
            (tmp_path / name / pointer).write_text(version + "\n", encoding="utf-8")
            (tmp_path / name / version).mkdir(exist_ok=True)
    return tmp_path


def _save(root: Path, name: str, version: str, pointer: str | None = "CURRENT") -> None:
    folder = root / name / version
    folder.mkdir(parents=True)
    (folder / "evaluation.json").write_text("{}", encoding="utf-8")
    if pointer is not None:
        (root / name / pointer).write_text(version + "\n", encoding="utf-8")


def test_scoring_falls_back_to_the_pooled_model_until_a_group_has_its_own(
    registries: Path,
) -> None:
    with formats.use_group("leagues"):
        # Training and reports never fall back.
        assert registry.current_version(registry.NAME, "BBL") is None
    with formats.use_group("leagues", serving=True):
        assert registry.current_version(registry.NAME, "BBL") == "2.0.0"
        assert registry.fallback_version(registry.NAME, "BBL") == "2.0.0"
        assert registry.current_dir(registry.NAME, "BBL") == registries / registry.NAME / "2.0.0"
        assert registry.current_version(registry.SIMULATOR, "BBL") == "2.1.0"
    _save(registries / "leagues", registry.NAME, "1.0.0")
    with formats.use_group("leagues", serving=True):
        assert registry.current_version(registry.NAME, "BBL") == "1.0.0"
        assert registry.fallback_version(registry.NAME, "BBL") is None
        assert (
            registry.current_dir(registry.NAME, "BBL")
            == registries / "leagues" / registry.NAME / "1.0.0"
        )


def test_a_group_with_a_simulator_of_its_own_never_borrows_the_pooled_one(
    registries: Path,
) -> None:
    # Its backtest failed for the BBL and passed for the CPL: the BBL has no simulator.
    _save(registries / "leagues", registry.SIMULATOR, "1.0.0", pointer="CURRENT.CPL")
    with formats.use_group("leagues", serving=True):
        assert registry.current_version(registry.SIMULATOR, "CPL") == "1.0.0"
        assert registry.current_version(registry.SIMULATOR, "BBL") is None


def test_odis_never_fall_back_to_a_t20_model(registries: Path) -> None:
    with formats.use_group("odi", serving=True):
        assert registry.current_version(registry.NAME, "ODI") is None


def test_promotion_writes_the_groups_own_pointer(registries: Path) -> None:
    with formats.use_group("ipl"):
        _save(registries, registry.NAME, "1.1.0", pointer=None)
        registry.promote("1.1.0", registry.NAME)
        assert (registries / registry.NAME / "CURRENT.IPL").read_text().strip() == "1.1.0"
        assert registry.current_version(registry.NAME) == "1.1.0"
    # The pooled version keeps its pointer.
    assert (registries / registry.NAME / "CURRENT").read_text().strip() == "2.0.0"


def test_leagues_ratings_borrow_from_the_leagues_only(fixture_scored_players_db: Path) -> None:
    cfg = ratings.load_ratings_config(paths.config_dir() / "models" / "leagues" / "ratings.yaml")
    cfg = cfg.model_copy(update={"min_pairs": 10**9})  # every component borrows
    scopes = [
        (s["scope_id"], s["schema_name"])
        for s in players_scoring.scopes(fixture_scored_players_db)
        if s["scope_id"] in LEAGUES
    ]
    assert len(scopes) > 1
    model, evaluation = ratings.train_scopes(
        fixture_scored_players_db, scopes, cfg, data_version="fixture", pool="LEAGUES"
    )
    assert evaluation["pool"]["scopes"] == [scope for scope, _ in scopes]
    assert set(model.manifest["scopes"]) == {scope for scope, _ in scopes}
    lent = {(c["role"], c["key"]): c["k"] for c in evaluation["pool"]["components"]}
    for part in model.manifest["scopes"].values():
        for role, components in part["components"].items():
            for key, served in components.items():
                assert served["borrowed"] == "LEAGUES"
                assert served["k"] == lent[(role, key)]


def _runner() -> ModuleType:
    path = paths.repo_root() / "scripts" / "train_group.py"
    spec = importlib.util.spec_from_file_location("train_group", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["train_group"] = module
    spec.loader.exec_module(module)
    return module


def test_a_new_training_run_names_a_new_version(tmp_path: Path) -> None:
    runner = _runner()
    assert runner.next_version("1.0.0", []) == "1.0.0"
    assert runner.next_version("1.0.0", ["1.0.0"]) == "1.1.0"
    assert runner.next_version("1.0.0", ["1.0.0", "1.1.0", "2.0.0"]) == "1.2.0"
    assert runner.next_version("1.1.0", ["1.0.0", "1.1.0"]) == "1.2.0"
    config = tmp_path / "model.yaml"
    config.write_text("# keep me\nname: x\nversion: 1.0.0\nscope: T20I\n", encoding="utf-8")
    runner.set_config_version(config, "1.1.0")
    assert config.read_text(encoding="utf-8") == "# keep me\nname: x\nversion: 1.1.0\nscope: T20I\n"
    assert runner.config_version(config) == "1.1.0"
