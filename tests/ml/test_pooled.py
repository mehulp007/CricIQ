"""Pooled T20 models: competition-aware features, per-competition serving pointers,
the ball model's competition terms, the IPL comparisons and the players database's
model outputs."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from criciq_ml import comparison, players_scoring, ratings, registry
from criciq_ml.ball_outcome import BallOutcomeModel, load_balls
from criciq_ml.data import MAX_BALLS_SQL, TARGET_SQL, Inputs, load_inputs
from criciq_ml.features import STABLE_DECIMALS, FeatureConfig, build_states
from criciq_ml.simulator import SimulatorSettings


@pytest.fixture(scope="module")
def pooled_inputs(fixture_pooled_warehouse: Path) -> Inputs:
    return load_inputs(fixture_pooled_warehouse)


@pytest.fixture(scope="module")
def pooled_states(pooled_inputs: Inputs) -> pd.DataFrame:
    return build_states(pooled_inputs, FeatureConfig(stable=True))


def test_the_pooled_copy_orders_matches_across_competitions(
    fixture_pooled_warehouse: Path, fixture_full_warehouse: Path
) -> None:
    con = duckdb.connect(str(fixture_pooled_warehouse), read_only=True)
    try:
        con.execute(f"ATTACH '{fixture_full_warehouse.as_posix()}' AS w (READ_ONLY)")
        rows = con.execute(
            """
            SELECT m.match_order, rank() OVER (ORDER BY f.global_order) AS expected,
                   m.competition_id
            FROM matches m JOIN w.matches f USING (match_id)
            """
        ).fetchall()
    finally:
        con.close()
    assert all(order == expected for order, expected, _ in rows)
    assert {c for *_, c in rows} == {"IPL", "BBL", "PSL", "CPL", "SA20", "T20I"}


def test_each_competition_keeps_its_own_era(
    pooled_states: pd.DataFrame, fixture_states: pd.DataFrame
) -> None:
    """The IPL's states in the pooled copy have the IPL's own scoring era."""
    keys = ["match_id", "innings_no", "seq_no"]
    ipl = pooled_states[pooled_states["competition_id"] == "IPL"]
    joined = ipl.merge(fixture_states, on=keys, suffixes=("_pooled", "_ipl"))
    assert len(joined) == len(fixture_states)
    for column in ("env_rpb", "runs_vs_par"):
        assert np.allclose(joined[f"{column}_pooled"], joined[f"{column}_ipl"], atol=1e-8)


def test_stable_features_are_rounded(pooled_states: pd.DataFrame) -> None:
    chase = pooled_states["chase_ratio"].dropna().to_numpy()
    scaled = chase * 10**STABLE_DECIMALS
    assert np.allclose(scaled, np.round(scaled), atol=1e-3)


def test_international_cricket_is_flagged(pooled_states: pd.DataFrame) -> None:
    flags = pooled_states.groupby("competition_id")["international"].unique()
    assert flags["T20I"].tolist() == [1.0]
    assert all(flags[c].tolist() == [0.0] for c in flags.index if c != "T20I")


def test_missing_targets_and_overlong_innings_are_read_sensibly() -> None:
    """A chase without a recorded target chases the first innings plus one, and a T20
    recorded as a 50-over match lasts 20 overs (both seen in Cricsheet's T20Is)."""
    con = duckdb.connect()
    try:
        con.execute(
            """
            CREATE TABLE innings AS SELECT * FROM (VALUES
                (1, 1, false, NULL, NULL, 150), (1, 2, false, NULL, NULL, 120)
            ) v(match_id, innings_no, is_super_over, target_runs, target_balls, runs);
            CREATE TABLE matches AS SELECT 1 AS match_id, 50 AS scheduled_overs,
                                           6 AS balls_per_over;
            """
        )
        rows = con.execute(
            f"""
            SELECT i.innings_no, {TARGET_SQL} AS target, {MAX_BALLS_SQL} AS max_balls
            FROM innings i JOIN matches m USING (match_id) ORDER BY i.innings_no
            """
        ).fetchall()
    finally:
        con.close()
    assert rows == [(1, None, 120), (2, 151, 120)]


def test_a_competition_can_keep_its_own_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRICIQ_MODELS_DIR", str(tmp_path))
    (tmp_path / registry.NAME).mkdir()
    registry.promote("2.0.0", registry.NAME)
    assert registry.current_version(registry.NAME, "IPL") == "2.0.0"  # falls back
    registry.promote("1.0.0", registry.NAME, "IPL")
    assert registry.current_version(registry.NAME, "IPL") == "1.0.0"
    assert registry.current_version(registry.NAME, "T20I") == "2.0.0"
    registry.release(registry.NAME, "IPL")
    assert registry.current_version(registry.NAME, "IPL") == "2.0.0"


def test_serving_one_competition_folds_its_term(fixture_pooled_warehouse: Path) -> None:
    balls = load_balls(fixture_pooled_warehouse)
    model = BallOutcomeModel.fit(
        balls, player_scale=0.1, c=1.0, max_iter=500, competition_terms=True
    )
    assert any(term.startswith("competition=") for term in model.terms)
    for competition in ("IPL", "T20I"):
        mine = balls[balls["competition_id"] == competition]
        served = model.for_competition(competition)
        assert not any(term.startswith("competition=") for term in served.terms)
        assert np.allclose(served.predict(mine), model.predict(mine))


def _predictions(p: list[float], match_ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": match_ids,
            "innings_no": 1,
            "seq_no": range(len(p)),
            "y": [1.0, 0.0] * (len(p) // 2),
            "p": p,
        }
    )


def test_the_comparison_reports_the_gain_and_the_verdict() -> None:
    ids = [m for m in range(20) for _ in range(2)]
    v1 = _predictions([0.6, 0.4] * 20, ids)
    sharper = _predictions([0.8, 0.2] * 20, ids)
    worse = _predictions([0.4, 0.6] * 20, ids)
    better = comparison.compare(v1, sharper, v1_version="1.0.0", v2_version="2.0.0")
    assert better["no_worse"]
    assert better["better"]
    assert better["v2_gain"]["improvement"] > 0
    assert comparison.serves_ipl(better)
    assert not comparison.compare(v1, worse, v1_version="1.0.0", v2_version="2.0.0")["no_worse"]
    with pytest.raises(ValueError, match="scored"):
        comparison.compare(v1, sharper.iloc[:10], v1_version="1.0.0", v2_version="2.0.0")


def test_a_rebuilt_v1_must_match_its_record() -> None:
    rebuilt = _predictions([0.6, 0.4] * 5, list(range(10)))
    with pytest.raises(ValueError, match="rebuilt"):
        comparison.check_reproduced(rebuilt, {"test": {"model": {"log_loss": 0.1}}})


def test_win_probability_added_is_credited_as_in_the_serving_database(
    fixture_scored_serving_db: Path,
) -> None:
    con = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    try:
        predictions = con.execute("SELECT * FROM wp_predictions").df()
        deliveries = con.execute("SELECT * FROM deliveries").df()
        expected = con.execute("SELECT * FROM player_wpa ORDER BY ALL").df()
    finally:
        con.close()
    found = players_scoring.player_wpa(predictions, deliveries)
    found = found.sort_values(list(expected.columns)).reset_index(drop=True)
    expected = expected.sort_values(list(expected.columns)).reset_index(drop=True)
    pd.testing.assert_frame_equal(found, expected, check_dtype=False)


def test_the_players_database_gets_each_scopes_outputs(
    fixture_players_db: Path, tmp_path: Path
) -> None:
    players = tmp_path / "players.duckdb"
    shutil.copyfile(fixture_players_db, players)
    wpa = pd.DataFrame(
        {
            "competition_id": ["IPL", "BBL"],
            "player_id": ["a", "b"],
            "match_id": [1, 2],
            "innings_no": [1, 1],
            "role": ["batting", "bowling"],
            "wpa": [0.1, -0.2],
        }
    )
    fitted = {"trained_on": {"seasons": [2008, 2026]}, "components": {"batting": {}}}
    model = ratings.RatingsModel(
        {"name": "ratings", "version": "9.9.9", "scopes": {"IPL": fitted, "T20": fitted}}
    )
    placed = players_scoring.publish(players, wpa, model)
    con = duckdb.connect(str(placed), read_only=True)
    try:
        assert con.execute("SELECT player_id FROM ipl.player_wpa").fetchall() == [("a",)]
        assert con.execute("SELECT count(*) FROM t20.player_wpa").fetchone() == (2,)
        assert con.execute("SELECT version FROM ipl.models").fetchone() == ("9.9.9",)
        tables = {
            (schema, name)
            for schema, name in con.execute(
                "SELECT table_schema, table_name FROM information_schema.tables"
            ).fetchall()
        }
    finally:
        con.close()
    assert ("t20", "models") in tables
    assert ("bbl", "models") not in tables  # no constants fitted for it


def test_small_competitions_borrow_the_all_t20_shrinkage(fixture_players_db: Path) -> None:
    cfg = ratings.load_ratings_config()
    model, evaluation = ratings.train_scopes(
        fixture_players_db, [("T20", "t20"), ("IPL", "ipl")], cfg, data_version="fixture"
    )
    pooled = model.manifest["scopes"]["T20"]["components"]
    for role, components in model.manifest["scopes"]["IPL"]["components"].items():
        for key, served in components.items():
            # The fixtures follow no player from one season to the next 100 times.
            assert served["borrowed"] == "T20"
            assert served["k"] == pooled[role][key]["k"]
    assert ratings.gate(evaluation) == []
    assert model.for_scope("T20I") is None


def test_simulator_settings_per_competition() -> None:
    settings = SimulatorSettings(
        {
            "name": "simulator",
            "version": "2.0.0",
            "competitions": {"T20I": {"conditions_sd": 0.4}, "IPL": {"conditions_sd": 0.3}},
        }
    )
    assert settings.for_competition("T20I").manifest["conditions_sd"] == 0.4
    assert settings.for_competition("IPL").version == "2.0.0"
    v1 = SimulatorSettings({"name": "simulator", "version": "1.0.0", "conditions_sd": 0.3})
    assert v1.for_competition("IPL") is v1


def _line(competition: str, low: float, high: float) -> dict[str, object]:
    return {
        "competition": competition,
        "model": {"log_loss": 0.5},
        "baseline": {"log_loss": 0.49},
        "vs_baseline": {"improvement": (low + high) / 2, "ci_low": low, "ci_high": high},
    }


def test_a_competition_fails_the_gate_only_when_clearly_worse() -> None:
    base = {
        "model": {"log_loss": 0.45, "brier": 0.15},
        "baseline": {"log_loss": 0.49, "brier": 0.16},
    }
    noisy = {"test": {**base, "by_competition": [_line("SA20", -0.05, 0.02)]}}
    worse = {"test": {**base, "by_competition": [_line("SA20", -0.05, -0.01)]}}
    assert registry.gate(noisy, None, 0.002) == []
    assert registry.gate(worse, None, 0.002) == [
        "clearly worse than the baseline on SA20 test log loss"
    ]


def test_ratings_gate_small_validations_out() -> None:
    def component(pairs: int) -> dict[str, object]:
        return {
            "role": "bowling",
            "key": "middle",
            "next_season": {"pairs": pairs, "mse": {"raw": 1.0, "shrunk": 1.01}},
        }

    small = {"min_pairs": 100, "scopes": {"CPL": {"components": [component(46)]}}}
    large = {"min_pairs": 100, "scopes": {"CPL": {"components": [component(146)]}}}
    assert ratings.gate(small) == []
    assert len(ratings.gate(large)) == 1


def test_the_projection_serves_the_ipl_only_inside_the_coverage_band() -> None:
    result = {
        "v1": {"pinball": 4.87, "coverage80": 0.80},
        "v2": {"pinball": 4.86, "coverage80": 0.86},
        "better": False,
    }
    assert not comparison.projection_verdict(result, (0.75, 0.85))["no_worse"]
    inside = {**result, "v2": {"pinball": 4.86, "coverage80": 0.82}}
    assert comparison.projection_verdict(inside, (0.75, 0.85))["no_worse"]
