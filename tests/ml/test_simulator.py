"""Match simulator: the engine reproduces the ball model, and the backtest's pieces."""

from __future__ import annotations

import json
import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from criciq_core import simulation as sim
from criciq_ml import registry, simulator
from criciq_ml.ball_outcome import GROUPS, BallOutcomeModel, load_balls


@pytest.fixture(scope="module")
def balls(fixture_warehouse: Path) -> pd.DataFrame:
    return load_balls(fixture_warehouse)


@pytest.fixture(scope="module")
def model(balls: pd.DataFrame) -> BallOutcomeModel:
    return BallOutcomeModel.fit(balls, player_scale=0.1, c=1.0, max_iter=2000)


def test_engine_levels_match_the_ball_model() -> None:
    assert [lv for lv, _ in sim.WICKET_LEVELS] == list(GROUPS["wickets"])
    assert [lv for lv, _ in sim.SETTLED_LEVELS] == list(GROUPS["settled"])
    assert list(sim.PRESSURE_LEVELS) == list(GROUPS["pressure"])
    assert [f"{p}_{i}" for i in (1, 2) for p in sim.PHASES] == list(GROUPS["phase"])


def test_engine_logits_equal_the_model(model: BallOutcomeModel, balls: pd.DataFrame) -> None:
    sample = balls.sample(80, random_state=3)
    want = model.logits(sample)
    for (_, ball), expected in zip(sample.iterrows(), want, strict=True):
        era = (math.log(ball["env"]) - model.manifest["env_mean"]) / model.manifest["env_std"]
        engine = simulator.ball_model_inputs(model, ball["env"])
        assert engine.era == pytest.approx(era)
        bat = sim.Side(
            "a",
            (sim.Player(ball["batter_id"], ball["batting_hand"]), sim.Player("x")),
            (sim.Player("y"),) * 5,
            np.ones((5, sim.OVERS)),
        )
        bowl = sim.Side(
            "b",
            (sim.Player("z"), sim.Player("w")),
            tuple(sim.Player(ball["bowler_id"], None, ball["bowling_type"]) for _ in range(5)),
            np.ones((5, sim.OVERS)),
        )
        base = sim._base_logits(engine, bat, bowl, int(ball["innings_no"]))
        got = (
            base[sim.PHASES.index(ball["phase"]), 0, 0]
            + engine.term(f"wickets={ball['g_wickets']}")
            + engine.term(f"settled={ball['g_settled']}")
            + engine.term(f"pressure={ball['g_pressure']}")
        )
        np.testing.assert_allclose(got, expected, atol=1e-9)


def test_backtest_pieces(
    model: BallOutcomeModel, balls: pd.DataFrame, fixture_scored_serving_db: Path
) -> None:
    envs = balls.groupby("match_id")["env"].first().to_dict()
    con = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    try:
        matches = simulator.test_matches(con, [2019, 2023])
        assert len(matches) > 0
        setups = simulator.prepare(con, [2019, 2023], model, envs, history=3)
    finally:
        con.close()
    assert setups
    for s in setups:
        assert len(s.first.batters) == 11
        assert len(s.second.bowlers) >= sim.MIN_BOWLING_OPTIONS
    done, forced = simulator.simulate_all(setups, 300, 0.3, seed=1, chases=True)
    assert len(done) == len(setups)
    assert forced == 0
    assert done["p_first"].between(0, 1).all()
    assert done["pit"].between(0, 1).all()
    assert (done["crps"] >= 0).all()


def test_supersub_side_bats_eleven() -> None:
    def cand(pid: str, position: float | None, overs: float) -> sim.Candidate:
        by_over = np.zeros(sim.OVERS)
        by_over[0] = overs
        return sim.Candidate(sim.Player(pid), position, by_over)

    # Twelve named (supersub rules): the one who usually bats lowest drops out.
    twelve = [cand(f"p{i}", float(i + 1), 30.0 if i >= 6 else 0.0) for i in range(11)]
    twelve.append(cand("extra", 12.0, 40.0))
    side = simulator.side_for("x", twelve, sim.usage_priors([("any", 0, 1)]))
    assert len(side.batters) == 11
    assert "extra" not in {p.player_id for p in side.batters + side.bowlers}


def test_crps_and_pit() -> None:
    sample = np.array([150, 160, 170, 180, 190])
    assert simulator.crps(sample, 170) < simulator.crps(sample, 230)
    assert simulator.crps(np.full(10, 170), 170) == pytest.approx(0.0)
    rng = np.random.default_rng(1)
    assert simulator.pit(sample, 100, rng) == 0.0
    assert simulator.pit(sample, 300, rng) == 1.0
    assert 0.4 <= simulator.pit(sample, 170, rng) <= 0.6


def test_gate() -> None:
    evaluation = {
        "matches": 10,
        "simulations_per_match": 100,
        "forced_overs": 0,
        "first_innings": {"pit_chi2": 5.0, "pit_chi2_critical": 16.92},
    }
    assert simulator.gate(evaluation) == []
    assert simulator.gate({**evaluation, "forced_overs": 100})
    assert simulator.gate(
        {**evaluation, "first_innings": {"pit_chi2": 30.0, "pit_chi2_critical": 16.92}}
    )


def test_committed_settings_are_published(fixture_scored_serving_db: Path) -> None:
    settings = registry.load_current_simulator("IPL").for_competition("IPL")
    con = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    try:
        row = con.execute("SELECT version, info FROM models WHERE name = 'simulator'").fetchone()
    finally:
        con.close()
    assert row is not None
    assert row[0] == settings.version
    assert '"conditions_sd"' in row[1]


def test_the_card_follows_the_newest_pooled_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from criciq_ml import simulator_report

    monkeypatch.setenv("CRICIQ_MODELS_DIR", str(tmp_path))
    root = tmp_path / "simulator"
    for version, evaluation in (
        ("1.0.0", {"test": [2025]}),
        ("2.0.0", {"competitions": {"T20I": {}}}),
        ("10.0.0", {"competitions": {"T20I": {}, "BBL": {}}}),
    ):
        (root / version).mkdir(parents=True)
        (root / version / "evaluation.json").write_text(json.dumps(evaluation))
    # Versions compare as versions (10 after 2); v1 backtested the IPL alone.
    assert simulator_report.latest_pooled() == "10.0.0"
    registry.promote("1.0.0", registry.SIMULATOR)
    registry.promote("10.0.0", registry.SIMULATOR, "BBL")
    assert simulator_report.serves("10.0.0", "BBL")
    assert not simulator_report.serves("10.0.0", "T20I")
