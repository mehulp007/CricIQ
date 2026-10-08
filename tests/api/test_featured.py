import json
from pathlib import Path

import pytest

from criciq_api.db import Database
from criciq_api.featured import (
    FEATURED,
    OUT_DIR,
    FeaturedIndex,
    SeasonSnapshot,
    featured_matches,
    season_snapshot,
)
from criciq_api.schemas.matches import Timeline
from criciq_core.groups import group_of
from criciq_ml import formats, registry

# Every competition the web app bundles replays for.
BUNDLED = sorted(p.name for p in OUT_DIR.iterdir() if p.is_dir())


def _index(competition: str) -> FeaturedIndex:
    return FeaturedIndex.model_validate_json(
        (OUT_DIR / competition / "index.json").read_text("utf-8")
    )


def test_every_served_competition_is_bundled() -> None:
    assert {"ipl", "t20i", "odi", "bbl", "psl", "cpl", "sa20"} <= set(BUNDLED)
    index_ts = (OUT_DIR / "index.ts").read_text("utf-8")
    for competition in BUNDLED:
        assert f'from "./{competition}/index.json"' in index_ts


@pytest.mark.parametrize("competition", BUNDLED)
def test_bundled_featured_timelines_match_the_api_schema(competition: str) -> None:
    """The web app bundles these files; they must parse as real API payloads."""
    index = _index(competition)
    assert index.matches
    if competition in FEATURED:
        assert [m.match_id for m in index.matches] == list(FEATURED[competition])
    else:
        assert all(m.headline.endswith(" final") for m in index.matches)
    for entry in index.matches:
        timeline = Timeline.model_validate_json(
            (OUT_DIR / competition / f"{entry.match_id}.json").read_text("utf-8")
        )
        assert timeline.summary == entry.summary
        assert timeline.deliveries


def test_featured_files_are_compact() -> None:
    # About 150 KB for a T20's 240 balls; an ODI has up to 600, a Test about 2,000.
    limits = {"odi": 375_000, "test": 1_300_000}
    for path in OUT_DIR.glob("*/*.json"):
        assert path.stat().st_size < limits.get(path.parent.name, 150_000), path
    for competition in BUNDLED:
        assert json.loads((OUT_DIR / competition / "index.json").read_text("utf-8"))["data_version"]


@pytest.mark.parametrize("competition", BUNDLED)
def test_featured_replays_carry_the_model_serving_them(competition: str) -> None:
    # Each model group's models are its own (ADR-0012, ADR-0013).
    owner = group_of(competition.upper())
    assert owner is not None
    with formats.use_group(owner, serving=True):
        current = registry.current_version(registry.NAME, competition.upper())
    for entry in _index(competition).matches:
        timeline = Timeline.model_validate_json(
            (OUT_DIR / competition / f"{entry.match_id}.json").read_text("utf-8")
        )
        assert timeline.win_probability is not None
        assert timeline.win_probability.version == current


@pytest.mark.parametrize("competition", BUNDLED)
def test_season_snapshot_is_bundled_and_consistent(competition: str) -> None:
    snapshot = SeasonSnapshot.model_validate_json(
        (OUT_DIR / competition / "snapshot.json").read_text("utf-8")
    )
    assert snapshot.season >= max(m.summary.season for m in _index(competition).matches)
    assert snapshot.matches > 0
    assert set(snapshot.leaders) == {"runs", "wickets", "runs_above_par", "runs_saved"}
    assert all(leader.value > 0 for leader in snapshot.leaders.values())
    # Internationals have no single champion.
    if competition == "t20i":
        assert snapshot.champion is None


def test_season_snapshot_from_the_serving_database(fixture_serving_db: Path) -> None:
    db = Database(fixture_serving_db)
    try:
        snapshot = season_snapshot(db)
    finally:
        db.close()
    assert snapshot.leaders["runs"].value >= snapshot.leaders["runs_above_par"].value
    assert snapshot.first_innings_average > 0
    assert snapshot.label == str(snapshot.season)


def test_competitions_without_a_curated_list_feature_their_finals(
    fixture_scored_serving_db: Path,
) -> None:
    db = Database(fixture_scored_serving_db.with_name("serving-t20i.duckdb"))
    try:
        assert featured_matches(db) == FEATURED["t20i"]
    finally:
        db.close()
