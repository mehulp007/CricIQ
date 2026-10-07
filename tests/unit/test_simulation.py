"""Match simulation engine: cricket rules, the ball model's arithmetic and setup helpers."""

from __future__ import annotations

import numpy as np
import pytest

from criciq_core import simulation as sim


def _side(name: str, bowlers: int = 6) -> sim.Side:
    batters = tuple(sim.Player(f"{name}{i}", "right", "pace" if i > 6 else None) for i in range(11))
    return sim.Side(name, batters, batters[11 - bowlers :], np.ones((bowlers, sim.OVERS)))


def _rates(extras: float = 0.05, run_out: float = 0.003) -> sim.LeagueRates:
    p = np.zeros((2, 3, 6))
    p[..., 0] = 1 - extras
    p[..., 1] = extras
    return sim.LeagueRates(extras=p, run_out=np.full((2, 3), run_out), env=1.4)


def _model(**terms: list[float]) -> sim.BallModel:
    # A plausible T20 ball: dot 33%, 1 38%, 2 6%, 3 0.3%, 4 13%, 6 6%, out 5%.
    base = np.log([0.33, 0.38, 0.06, 0.003, 0.13, 0.06, 0.05])
    return sim.BallModel(terms={"intercept": list(base), **terms}, era=0.0)


def test_innings_obey_the_laws() -> None:
    rng = np.random.default_rng(1)
    a, b = _side("a"), _side("b")
    r = sim.simulate_innings(_model(), _rates(), a, b, innings=1, n=3000, rng=rng)
    assert (r.balls <= sim.MAX_BALLS).all()
    assert (r.wickets <= 10).all()
    # An innings ends at 120 balls or all out.
    assert ((r.balls == sim.MAX_BALLS) | (r.wickets == 10)).all()
    # Runs off the bat add up, and extras account for the rest.
    assert (r.bat_runs.sum(axis=1) <= r.runs).all()
    assert (r.bowl_runs.sum(axis=1) == r.bat_runs.sum(axis=1)).all()
    assert (r.bowl_balls.sum(axis=1) == r.balls).all()
    # Nobody bowls more than four overs.
    assert (r.bowl_balls <= sim.QUOTA * 6).all()
    assert r.forced_overs == 0
    # Wickets credited to bowlers never exceed the wickets that fell.
    assert (r.bowl_wickets.sum(axis=1) <= r.wickets).all()
    assert (r.bat_out.sum(axis=1) == r.wickets).all()
    assert 120 < r.runs.mean() < 220


def test_a_chase_stops_at_the_target() -> None:
    rng = np.random.default_rng(2)
    a, b = _side("a"), _side("b")
    target = np.full(2000, 150)
    r = sim.simulate_innings(_model(), _rates(), a, b, innings=2, n=2000, rng=rng, target=target)
    won = r.runs >= 150
    assert won.any()
    assert not won.all()
    # A successful chase ends within one ball of reaching the target.
    assert (r.runs[won] <= 150 + 6 + 5).all()
    assert (r.balls[won] <= sim.MAX_BALLS).all()


def test_no_bowler_bowls_consecutive_overs_with_five_options() -> None:
    rng = np.random.default_rng(3)
    usage = np.ones((5, sim.OVERS))
    used = np.zeros((4000, 5), dtype=np.int64)
    last = np.full(4000, -1)
    for over in range(sim.OVERS):
        pick, stuck = sim._pick_bowlers(usage, over, used, last, rng)
        assert stuck == 0
        assert (pick != last).all()
        used[np.arange(4000), pick] += 1
        last = pick
    assert (used == sim.QUOTA).all()


def test_usage_steers_the_choice_of_bowler() -> None:
    rng = np.random.default_rng(4)
    usage = np.full((6, sim.OVERS), 1e-3)
    usage[0, 0] = 1.0  # only bowler 0 has ever opened the bowling
    pick, _ = sim._pick_bowlers(usage, 0, np.zeros((500, 6), dtype=np.int64), np.full(500, -1), rng)
    assert np.mean(pick == 0) > 0.95


def test_better_batters_score_more() -> None:
    rng = np.random.default_rng(5)
    strong = sim.Side(
        "s",
        tuple(sim.Player(f"s{i}") for i in range(11)),
        tuple(sim.Player(f"s{i}") for i in range(5, 11)),
        np.ones((6, sim.OVERS)),
    )
    boost = [-0.3, 0.0, 0.0, 0.0, 0.3, 0.3, -0.3]
    model = _model(**{f"batter=s{i}": boost for i in range(11)})
    plain = sim.simulate_innings(
        model, _rates(), _side("a"), _side("b"), innings=1, n=2000, rng=rng
    )
    better = sim.simulate_innings(model, _rates(), strong, _side("b"), innings=1, n=2000, rng=rng)
    assert better.runs.mean() > plain.runs.mean() + 15


def test_start_state_continues_an_innings() -> None:
    rng = np.random.default_rng(6)
    a, b = _side("a"), _side("b")
    start = sim.InningsState(
        runs=100,
        wickets=3,
        balls=90,
        striker=4,
        non_striker=2,
        next_in=5,
        bat_runs=[30, 20, 25, 15, 0],
        bat_balls=[25, 15, 20, 10, 0],
        bat_out=[True, True, False, True, False],
        bowl_overs=[3, 3, 3, 3, 3, 0],
        last_bowler=4,
    )
    r = sim.simulate_innings(_model(), _rates(), a, b, innings=1, n=1000, rng=rng, start=start)
    assert (r.runs >= 100).all()
    assert (r.wickets >= 3).all()
    assert (r.bat_out[:, [0, 1, 3]]).all()
    # Fifteen overs were bowled by five bowlers; the last five have to fit the quota.
    assert r.forced_overs == 0


def test_match_outcome_is_consistent() -> None:
    rng = np.random.default_rng(7)
    res = sim.simulate_match(_model(), _rates(), _side("a"), _side("b"), n=2000, rng=rng)
    first_won = res.first.runs > res.second.runs
    assert ((res.outcome == 1) == first_won).all()
    assert ((res.outcome == 0) == (res.first.runs == res.second.runs)).all()


def test_conditions_widen_the_spread_of_totals() -> None:
    a, b = _side("a"), _side("b")
    calm = sim.simulate_match(
        _model(), _rates(), a, b, n=3000, rng=np.random.default_rng(8), conditions_sd=0.0
    )
    varied = sim.simulate_match(
        _model(), _rates(), a, b, n=3000, rng=np.random.default_rng(8), conditions_sd=0.4
    )
    assert varied.first.runs.std() > calm.first.runs.std() * 1.1
    assert abs(varied.first.runs.mean() - calm.first.runs.mean()) < 10


def test_league_rates_and_priors() -> None:
    rows = [(1, "powerplay", 100, 1, 90, 8, 1, 0, 1, 0), (2, "death", 50, 2, 45, 5, 0, 0, 0, 0)]
    rates = sim.league_rates(rows, env=1.5)
    assert rates.extras[0, 0].sum() == pytest.approx(1.0)
    assert rates.extras[0, 0, 1] == pytest.approx(0.08)
    assert rates.run_out[1, 2] == pytest.approx(0.04)
    # No data for a phase: no extras.
    assert rates.extras[0, 1, 0] == 1.0
    priors = sim.usage_priors([("pace", 0, 10.0), ("spin", 10, 5.0), (None, 19, 1.0)])
    assert priors["pace"][0] == 1.0
    assert priors["any"].sum() == pytest.approx(1.0)


def test_default_bowlers_and_order() -> None:
    def cand(pid: str, position: float | None, overs: float) -> sim.Candidate:
        by_over = np.zeros(sim.OVERS)
        by_over[0] = overs
        return sim.Candidate(sim.Player(pid), position, by_over)

    xi = [cand(f"p{i}", float(i + 1), 0.0) for i in range(7)] + [
        cand("b1", 8.0, 60.0),
        cand("b2", 9.0, 50.0),
        cand("b3", None, 40.0),
        cand("b4", 11.0, 2.0),
    ]
    bowlers = sim.default_bowlers(xi)
    # Three regulars, topped up to five by the most-used others.
    assert bowlers[:3] == ["b1", "b2", "b3"]
    assert len(bowlers) == 5
    assert "b4" in bowlers
    order = [c.player.player_id for c in sim.typical_order(xi)]
    # No batting record: placed at position 9, after the specialists ahead of them.
    assert order.index("b2") < order.index("b3") < order.index("b4")
    side = sim.build_side("x", sim.typical_order(xi), bowlers, sim.usage_priors([("any", 0, 1)]))
    assert side.usage.shape == (5, sim.OVERS)
    assert np.allclose(side.usage.sum(axis=1), 1.0)


def test_sides_are_validated() -> None:
    players = tuple(sim.Player(f"x{i}") for i in range(11))
    with pytest.raises(ValueError, match="bowling options"):
        sim.Side("x", players, players[:4], np.ones((4, sim.OVERS)))
    with pytest.raises(ValueError, match="bats"):
        sim.Side("x", players[:1], players[:5], np.ones((5, sim.OVERS)))


def test_an_odi_innings_follows_the_odi_rules() -> None:
    odi = sim.rules_for("ODI")
    assert (odi.overs, odi.quota, odi.max_balls, odi.min_bowling_options) == (50, 10, 300, 5)
    # Powerplay overs 1-10, middle 11-40, death 41-50.
    assert odi.over_phase.tolist() == [0] * 10 + [1] * 30 + [2] * 10
    rng = np.random.default_rng(11)
    batters = tuple(sim.Player(f"o{i}", "right", "pace") for i in range(11))
    side = sim.Side("o", batters, batters[6:], np.ones((5, odi.overs)), odi)
    r = sim.simulate_innings(_model(), _rates(), side, side, innings=1, n=2000, rng=rng)
    assert (r.balls <= 300).all()
    assert ((r.balls == 300) | (r.wickets == 10)).all()
    # Five bowlers share fifty overs: ten each, never more.
    assert (r.bowl_balls <= 10 * 6).all()
    assert r.forced_overs == 0
    with pytest.raises(ValueError, match="at least 5 bowling options"):
        sim.Side("o", batters, batters[7:], np.ones((4, odi.overs)), odi)


def test_only_limited_overs_formats_are_simulated() -> None:
    with pytest.raises(ValueError, match="does not play Test"):
        sim.rules_for("Test")
