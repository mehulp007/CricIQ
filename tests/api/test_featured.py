import json
from pathlib import Path

from criciq_api.db import Database
from criciq_api.featured import FEATURED, OUT_DIR, FeaturedIndex, SeasonSnapshot, season_snapshot
from criciq_api.schemas.matches import Timeline
from criciq_ml import registry


def test_bundled_featured_timelines_match_the_api_schema() -> None:
    """The web app bundles these files; they must parse as real API payloads."""
    index = FeaturedIndex.model_validate_json((OUT_DIR / "index.json").read_text("utf-8"))
    assert [m.match_id for m in index.matches] == list(FEATURED)
    for entry in index.matches:
        timeline = Timeline.model_validate_json(
            (OUT_DIR / f"{entry.match_id}.json").read_text("utf-8")
        )
        assert timeline.summary == entry.summary
        assert timeline.deliveries


def test_featured_files_are_compact() -> None:
    sizes = [p.stat().st_size for p in OUT_DIR.glob("*.json")]
    assert max(sizes) < 150_000
    assert json.loads((OUT_DIR / "index.json").read_text("utf-8"))["data_version"]


def test_featured_replays_carry_the_current_model() -> None:
    current = registry.current_version()
    for match_id in FEATURED:
        timeline = Timeline.model_validate_json((OUT_DIR / f"{match_id}.json").read_text("utf-8"))
        assert timeline.win_probability is not None
        assert timeline.win_probability.version == current


def test_season_snapshot_is_bundled_and_consistent() -> None:
    snapshot = SeasonSnapshot.model_validate_json((OUT_DIR / "snapshot.json").read_text("utf-8"))
    index = FeaturedIndex.model_validate_json((OUT_DIR / "index.json").read_text("utf-8"))
    assert snapshot.season == max(m.summary.season for m in index.matches)
    assert snapshot.matches > 0
    assert set(snapshot.leaders) == {"runs", "wickets", "runs_above_par", "runs_saved"}
    assert all(leader.value > 0 for leader in snapshot.leaders.values())


def test_season_snapshot_from_the_serving_database(fixture_serving_db: Path) -> None:
    db = Database(fixture_serving_db)
    try:
        snapshot = season_snapshot(db)
    finally:
        db.close()
    assert snapshot.leaders["runs"].value >= snapshot.leaders["runs_above_par"].value
    assert snapshot.first_innings_average > 0
