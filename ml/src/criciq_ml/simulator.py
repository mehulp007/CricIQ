"""Backtest of the match simulator (criciq_core.simulation).

The spread of match conditions is tuned on validation seasons (the 80% range of
first-innings totals should hold 80% of them). Then every test match is simulated
before a ball is bowled, with nothing the captain would not have known:

- a ball-outcome model refit on the seasons before the test (with the served
  model's settings), so no test ball has trained it;
- the actual playing XIs, in each player's usual batting order from earlier
  matches, with bowling options and how each bowler is used taken from the
  three previous seasons;
- extras and run-out rates from the three previous seasons, and the scoring era
  as of the match;
- the actual choice of who batted first (the toss is decided before the start).

With ``level_windows``, the simulator can also follow the scoring level of the
competition's recent matches: before each match, the scoring era is shifted so the
ball model's expected runs per ball over a window of previous matches (with their
real batters, bowlers and situations) equal the runs actually scored. It uses
nothing a captain would not have known: the results of matches already played.
The window (or none) is chosen on the validation seasons by the CRPS of simulated
first-innings totals, so it is only used where it helps there.

The test reports the Brier score and log loss of the simulated chance that the
side batting first wins, against a coin flip, the base rate of batting first and
the two sides' recent form, and checks the simulated first-innings totals with a
probability integral transform (PIT): if the simulated distributions are right,
the actual total's percentile within its simulated distribution is uniform.

v2 backtests each competition in ``competitions`` on that competition's own
serving-shaped database, with the pooled ball model refit on every T20
competition before the test years and folded for it.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel

from criciq_core import simulation as sim
from criciq_core.phases import model_format
from criciq_core.teams import form_probability, log5
from criciq_ml import formats
from criciq_ml.ball_outcome import CLASSES, BallOutcomeModel, softmax

Log = Callable[[str], None]
PIT_BINS = 10
XI = 11


def _quiet(_: str) -> None:
    pass


class SimulatorConfig(BaseModel):
    name: str = "simulator"
    version: str
    # Competitions backtested (v2); v1 backtested the IPL alone.
    competitions: list[str] = ["IPL"]
    valid: list[int]
    test: list[int]
    conditions_grid: list[float]
    tuning_simulations: int
    simulations: int
    history_seasons: int
    timing_simulations: int
    seed: int
    # Windows (in matches) the recent scoring level may be followed over; the best on
    # the validation seasons, or none, is used (see the module docstring).
    level_windows: list[int] = []
    # How the conditions spread is chosen on the validation seasons: "coverage" (the
    # 80% range holds closest to 80% of first-innings totals) or "pit" (the totals'
    # percentiles closest to uniform, the gate's own test). CRPS breaks ties.
    tune_spread: str = "coverage"


def load_simulator_config(path: Path | None = None) -> SimulatorConfig:
    source = path or formats.config_path("simulator")
    with source.open(encoding="utf-8") as fh:
        return SimulatorConfig.model_validate(yaml.safe_load(fh))


@dataclass
class SimulatorSettings:
    """What the registry stores for the simulator: its settings, no fitted terms."""

    manifest: dict[str, Any]

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    def for_competition(self, competition: str) -> SimulatorSettings:
        """One competition's settings (v2 tunes them per competition; v1 is the IPL's)."""
        if "competitions" not in self.manifest:
            return self
        base = {k: v for k, v in self.manifest.items() if k != "competitions"}
        return SimulatorSettings({**base, **self.manifest["competitions"][competition]})

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


# --------------------------------------------------------------------------- inputs


def ball_model_inputs(
    model: BallOutcomeModel, env: float, sides: dict[str, list[str]] | None = None
) -> sim.BallModel:
    """The engine's ball model at a scoring era. ``sides`` maps a national side to its
    players: one without an effect of their own (a debutant) plays at the side's level."""
    era = (math.log(env) - float(model.manifest["env_mean"])) / float(model.manifest["env_std"])
    terms = {k: list(v) for k, v in model.terms.items()}
    for side, players in (sides or {}).items():
        for role in ("batter", "bowler"):
            level = model.side_effect(role, side)
            if level is None:
                continue
            for player in players:
                terms.setdefault(f"{role}={player}", list(level))
    return sim.BallModel(terms=terms, era=era)


# Runs off the bat for each outcome (CLASSES; a 3 includes the rare 5).
OUTCOME_RUNS = np.array([0, 1, 2, 3, 4, 6, 0], dtype=float)
# Era shifts searched for the level (standardised units of the scoring era).
SHIFT_GRID = np.linspace(-3.0, 8.0, 45)


def level_shifts(
    model: BallOutcomeModel, balls: pd.DataFrame, window: int
) -> tuple[pd.Series, float]:
    """The era shift before each match of one competition, by ``match_order``, and the
    shift after its last match: the shift that makes the model's expected runs per ball
    over the previous ``window`` matches equal the runs actually scored off the bat.

    ``balls`` are the competition's balls with their situation (``add_situation``) and
    ``model`` its ball model; a match with no earlier matches gets no shift."""
    assert len(CLASSES) == len(OUTCOME_RUNS)
    if balls.empty:
        return pd.Series(dtype=float), 0.0
    logits = model.logits(balls)
    env_term = np.asarray(model.terms["env"], dtype=float)
    orders, index = np.unique(balls["match_order"].to_numpy(), return_inverse=True)
    count = np.bincount(index, minlength=len(orders)).astype(float)
    actual = np.bincount(index, weights=balls["runs_batter"].to_numpy(float), minlength=len(orders))
    expected = np.stack(
        [
            np.bincount(
                index,
                weights=softmax(logits + shift * env_term) @ OUTCOME_RUNS,
                minlength=len(orders),
            )
            for shift in SHIFT_GRID
        ]
    )

    def previous(values: np.ndarray) -> np.ndarray:
        # Sums over the ``window`` matches before each match, and after the last one.
        total = np.concatenate([[0.0], np.cumsum(values)])
        at = np.arange(len(orders) + 1)
        out: np.ndarray = total[at] - total[np.maximum(at - window, 0)]
        return out

    n = previous(count)
    runs = previous(actual)
    curves = np.stack([previous(row) for row in expected])
    shifts = np.zeros(len(orders) + 1)
    for j in np.flatnonzero(n > 0):
        curve = np.maximum.accumulate(curves[:, j] / n[j])  # rises with the era
        shifts[j] = float(np.interp(runs[j] / n[j], curve, SHIFT_GRID))
    return pd.Series(np.round(shifts[:-1], 4), index=orders), round(float(shifts[-1]), 4)


def rules() -> sim.FormatRules:
    """The simulator's rules in the models' format (a 20- or 50-over innings)."""
    return sim.rules_for(model_format())


def test_matches(con: duckdb.DuckDBPyConnection, seasons: list[int]) -> pd.DataFrame:
    """Test matches with a result, who batted first, and whether the first innings
    ran its full course (all its overs or all out, no rain revision)."""
    marks = ", ".join("?" for _ in seasons)
    r = rules()
    return con.execute(
        f"""
        SELECT m.match_id, m.match_order, s.year AS season,
               i1.batting_team_id AS first_id, i1.bowling_team_id AS second_id,
               i1.runs AS first_runs, i1.wickets AS first_wickets,
               m.winner_id, m.outcome_type,
               m.win_method IS NULL AND m.scheduled_overs = {r.overs}
                   AND (i1.legal_balls >= {r.max_balls} OR i1.wickets >= 10) AS full_first
        FROM matches m
        JOIN seasons s USING (season_id)
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        WHERE s.year IN ({marks}) AND m.outcome_type <> 'no_result'
        ORDER BY m.match_order
        """,
        seasons,
    ).df()


def candidates(
    con: duckdb.DuckDBPyConnection,
    match_id: int,
    team_season_id: str,
    match_order: int,
    season: int,
    history: int,
) -> list[sim.Candidate]:
    """A side's playing XI with batting positions from earlier matches and bowling
    usage from the previous ``history`` seasons."""
    r = rules()
    rows = con.execute(
        f"""
        WITH xi AS (
            SELECT player_id, list_position FROM match_players
            WHERE match_id = ? AND team_season_id = ? AND selection = 'playing_xi'
        ),
        pos AS (
            SELECT player_id, avg(position) AS position FROM player_batting_innings
            WHERE match_order < ? AND player_id IN (SELECT player_id FROM xi)
            GROUP BY player_id
        ),
        bowl AS (
            SELECT player_id, list(struct_pack(over_no := over_no, overs := overs)) AS overs
            FROM (
                SELECT player_id, over_no, sum(overs) AS overs FROM bowling_usage
                WHERE season BETWEEN ? AND ? AND over_no < {r.overs}
                  AND player_id IN (SELECT player_id FROM xi)
                GROUP BY ALL
            )
            GROUP BY player_id
        )
        SELECT x.player_id, p.batting_hand, p.bowling_type, pos.position, bowl.overs
        FROM xi x JOIN players p USING (player_id)
        LEFT JOIN pos USING (player_id) LEFT JOIN bowl USING (player_id)
        ORDER BY x.list_position
        """,
        [match_id, team_season_id, match_order, season - history, season - 1],
    ).fetchall()
    out = []
    for pid, hand, kind, position, overs in rows:
        by_over = np.zeros(r.overs)
        for item in overs or []:
            by_over[int(item["over_no"])] = float(item["overs"])
        out.append(
            sim.Candidate(
                player=sim.Player(pid, hand, kind),
                position=None if position is None else float(position),
                overs_by_over=by_over,
            )
        )
    return out


def priors(con: duckdb.DuckDBPyConnection, first: int, last: int) -> dict[str, Any]:
    rows = con.execute(
        """
        SELECT p.bowling_type, u.over_no, sum(u.overs) FROM bowling_usage u
        LEFT JOIN players p USING (player_id)
        WHERE u.season BETWEEN ? AND ? GROUP BY ALL
        """,
        [first, last],
    ).fetchall()
    return sim.usage_priors(rows, rules())


def rates(con: duckdb.DuckDBPyConnection, first: int, last: int, env: float) -> sim.LeagueRates:
    rows = con.execute(
        """
        SELECT innings_no, phase, sum(legal_balls), sum(run_outs),
               sum(x0), sum(x1), sum(x2), sum(x3), sum(x4), sum(x5)
        FROM sim_league_rates WHERE season BETWEEN ? AND ? GROUP BY ALL
        """,
        [first, last],
    ).fetchall()
    return sim.league_rates(rows, env, rules())


def franchise(con: duckdb.DuckDBPyConnection, team_season_id: str) -> str:
    found = con.execute(
        "SELECT franchise_id FROM team_seasons WHERE team_season_id = ?", [team_season_id]
    ).fetchone()
    return str(found[0]) if found else ""


def side_for(name: str, xi: list[sim.Candidate], shapes: dict[str, Any]) -> sim.Side:
    # Under supersub rules (2005-06 T20Is, the BBL's X-factor, some associate T20Is) twelve are
    # named; the side is the eleven who usually bat highest.
    side = sim.typical_order(xi)[:XI]
    r = rules()
    return sim.build_side(name, side, sim.default_bowlers(side, r), shapes, rules=r)


# --------------------------------------------------------------------------- metrics


def _brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _log_loss(p: np.ndarray, y: np.ndarray) -> float:
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def _scores(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    return {"brier": round(_brier(p, y), 4), "log_loss": round(_log_loss(p, y), 4)}


def _bootstrap_gain(
    p: np.ndarray, base: np.ndarray, y: np.ndarray, seed: int, reps: int = 2000
) -> dict[str, float]:
    """Brier of the baseline minus the simulator's (positive = simulator better), 90%."""
    rng = np.random.default_rng(seed)
    loss = (base - y) ** 2 - (p - y) ** 2
    draws = loss[rng.integers(0, len(y), size=(reps, len(y)))].mean(axis=1)
    low, high = np.percentile(draws, [5, 95])
    return {
        "value": round(float(loss.mean()), 4),
        "low": round(float(low), 4),
        "high": round(float(high), 4),
    }


def calibration(p: np.ndarray, y: np.ndarray, bins: int = 5) -> list[dict[str, float]]:
    """Predicted against observed by equal-count bins of the predicted chance."""
    order = np.argsort(p)
    out = []
    for chunk in np.array_split(order, bins):
        if len(chunk):
            out.append(
                {
                    "matches": len(chunk),
                    "predicted": round(float(p[chunk].mean()), 3),
                    "observed": round(float(y[chunk].mean()), 3),
                }
            )
    return out


def pit(simulated: np.ndarray, actual: float, rng: np.random.Generator) -> float:
    """Randomised PIT of an integer total within its simulated distribution."""
    below = float(np.mean(simulated < actual))
    equal = float(np.mean(simulated == actual))
    return below + equal * float(rng.random())


# --------------------------------------------------------------------------- backtest


@dataclass
class Setup:
    """One match ready to simulate, with only what was known before it."""

    match: Any
    model: sim.BallModel
    rates: sim.LeagueRates
    first: sim.Side
    second: sim.Side


def with_shifts(setups: list[Setup], shifts: dict[int, float]) -> list[Setup]:
    """The same matches with each one's scoring era moved by its shift (by match order)."""
    if not shifts:
        return setups
    return [
        Setup(
            match=s.match,
            model=sim.BallModel(
                terms=s.model.terms,
                era=s.model.era + shifts.get(int(s.match.match_order), 0.0),
            ),
            rates=s.rates,
            first=s.first,
            second=s.second,
        )
        for s in setups
    ]


def choose_window(
    setups: list[Setup],
    shifts_for: Callable[[int], dict[int, float]],
    cfg: SimulatorConfig,
    log: Log,
) -> tuple[int, list[dict[str, float]]]:
    """The window the recent scoring level is followed over (0 = not followed) with the
    lowest CRPS of first-innings totals on the validation seasons."""
    grid = []
    for window in [0, *cfg.level_windows]:
        done, _ = simulate_all(
            with_shifts(setups, shifts_for(window)), cfg.tuning_simulations, 0.3, cfg.seed
        )
        full = done[done["full_first"]]
        row = {
            "window": window,
            "crps": round(float(full["crps"].mean()), 3),
            "bias": round(float((full["sim_first_mean"] - full["first_runs"]).mean()), 2),
        }
        grid.append(row)
        log(f"    level window {window}: CRPS {row['crps']}, totals {row['bias']:+} runs off")
    best = min(grid, key=lambda r: r["crps"])
    return int(best["window"]), grid


def crps(simulated: np.ndarray, actual: float) -> float:
    """Continuous ranked probability score of a sample (lower is better)."""
    x = np.sort(simulated.astype(float))
    n = len(x)
    spread = float(np.sum((2 * np.arange(1, n + 1) - n - 1) * x)) / (n * n)
    return float(np.mean(np.abs(x - actual))) - spread


def prepare(
    con: duckdb.DuckDBPyConnection,
    seasons: list[int],
    model: BallOutcomeModel,
    envs: dict[int, float],
    history: int,
) -> list[Setup]:
    """Every test match ready to simulate; ``envs`` is the scoring era by match id."""
    setups = []
    matches = test_matches(con, seasons)
    for season in sorted(matches["season"].unique()):
        first, last = int(season) - history, int(season) - 1
        shapes = priors(con, first, last)
        for m in matches[matches["season"] == season].itertuples():
            env = envs[int(m.match_id)]
            a = candidates(con, m.match_id, m.first_id, m.match_order, int(season), history)
            b = candidates(con, m.match_id, m.second_id, m.match_order, int(season), history)
            if len(a) < 11 or len(b) < 11:
                continue
            sides = {
                franchise(con, m.first_id): [c.player.player_id for c in a],
                franchise(con, m.second_id): [c.player.player_id for c in b],
            }
            setups.append(
                Setup(
                    match=m,
                    model=ball_model_inputs(model, env, sides),
                    rates=rates(con, first, last, env),
                    first=side_for(m.first_id, a, shapes),
                    second=side_for(m.second_id, b, shapes),
                )
            )
    return setups


def simulate_all(
    setups: list[Setup], n: int, conditions_sd: float, seed: int, *, chases: bool = False
) -> tuple[pd.DataFrame, int]:
    """One row per match: simulated chance the side batting first wins, and the
    simulated first-innings totals against the actual one."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    forced = 0
    for s in setups:
        m = s.match
        result = sim.simulate_match(
            s.model, s.rates, s.first, s.second, n=n, rng=rng, conditions_sd=conditions_sd
        )
        forced += result.first.forced_overs + result.second.forced_overs
        totals = result.first.runs
        rows.append(
            {
                "match_id": int(m.match_id),
                "season": int(m.season),
                "p_first": float(np.mean(result.outcome == 1) + 0.5 * np.mean(result.outcome == 0)),
                "first_won": float(m.winner_id == m.first_id),
                "full_first": bool(m.full_first),
                "first_runs": int(m.first_runs),
                "first_wickets": int(m.first_wickets),
                "sim_first_mean": float(totals.mean()),
                "sim_first_wickets": float(result.first.wickets.mean()),
                "sim_q10": float(np.percentile(totals, 10)),
                "sim_q25": float(np.percentile(totals, 25)),
                "sim_q75": float(np.percentile(totals, 75)),
                "sim_q90": float(np.percentile(totals, 90)),
                "pit": pit(totals, float(m.first_runs), rng),
                "crps": crps(totals, float(m.first_runs)),
                "sim_tie": float(np.mean(result.outcome == 0)),
                "p_chase": chase_chance(s, n, conditions_sd, rng) if chases else None,
            }
        )
    return pd.DataFrame(rows), forced


def chase_chance(setup: Setup, n: int, conditions_sd: float, rng: np.random.Generator) -> float:
    """Simulated chance of chasing the actual target, from the first ball of the chase."""
    m = setup.match
    conditions = rng.normal(0.0, conditions_sd, n) if conditions_sd > 0 else None
    chase = sim.simulate_innings(
        setup.model,
        setup.rates,
        setup.second,
        setup.first,
        innings=2,
        n=n,
        rng=rng,
        target=np.full(n, int(m.first_runs) + 1),
        conditions=conditions,
    )
    reached = chase.runs >= int(m.first_runs) + 1
    tied = chase.runs == int(m.first_runs)
    return float(np.mean(reached) + 0.5 * np.mean(tied))


def pit_chi2(values: np.ndarray) -> float:
    """Chi-square of a PIT histogram against a uniform one (``PIT_BINS`` bins)."""
    if len(values) == 0:
        return 0.0
    counts, _ = np.histogram(values, bins=PIT_BINS, range=(0.0, 1.0))
    expected = len(values) / PIT_BINS
    return float(((counts - expected) ** 2 / expected).sum())


def tune_conditions(
    setups: list[Setup], cfg: SimulatorConfig, log: Log
) -> tuple[float, list[dict[str, float]]]:
    """The conditions spread whose 80% range holds closest to 80% of first-innings
    totals on the validation seasons, or (``tune_spread: pit``) whose PIT histogram is
    closest to uniform; CRPS is reported too, and breaks ties."""
    grid = []
    for sd in cfg.conditions_grid:
        done, _ = simulate_all(setups, cfg.tuning_simulations, sd, cfg.seed)
        full = done[done["full_first"]]
        inside = (full["first_runs"] >= full["sim_q10"]) & (full["first_runs"] <= full["sim_q90"])
        y, p = done["first_won"].to_numpy(), done["p_first"].to_numpy()
        row = {
            "conditions_sd": sd,
            "crps": round(float(full["crps"].mean()), 3),
            "coverage_80": round(float(inside.mean()), 3),
            "pit_chi2": round(pit_chi2(full["pit"].to_numpy()), 2),
            "brier": round(_brier(p, y), 4),
        }
        grid.append(row)
        log(
            f"    sd {sd}: CRPS {row['crps']}, 80% coverage {row['coverage_80']}, "
            f"PIT chi-square {row['pit_chi2']}, Brier {row['brier']}"
        )
    if cfg.tune_spread == "pit":
        best = min(grid, key=lambda r: (r["pit_chi2"], r["crps"]))
    else:  # the 80% range should hold 80% of totals; ties go to the lower CRPS
        best = min(grid, key=lambda r: (round(abs(r["coverage_80"] - 0.8), 3), r["crps"]))
    return float(best["conditions_sd"]), grid


def _form_baseline(con: duckdb.DuckDBPyConnection, match_ids: list[int]) -> dict[int, float]:
    """Chance the side batting first wins from both sides' recent form (log5)."""
    rows = con.execute(
        """
        SELECT a.match_id, a.form_won, a.form_decided, b.form_won, b.form_decided
        FROM team_matches a
        JOIN team_matches b ON b.match_id = a.match_id AND b.franchise_id = a.opponent_id
        WHERE a.batted_first
        """
    ).fetchall()
    wanted = set(match_ids)
    return {
        int(mid): log5(form_probability(aw, ad), form_probability(bw, bd))
        for mid, aw, ad, bw, bd in rows
        if mid in wanted
    }


def _bat_first_rate(con: duckdb.DuckDBPyConnection, before: int) -> float:
    row = con.execute(
        """
        SELECT avg((winner_id = team_a_id)::DOUBLE) FROM match_summaries
        WHERE season < ? AND outcome_type = 'win'
        """,
        [before],
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.5


def evaluate(
    done: pd.DataFrame,
    form: dict[int, float],
    base_rate: float,
    forced: int,
    cfg: SimulatorConfig,
) -> dict[str, Any]:
    y = done["first_won"].to_numpy()
    p = done["p_first"].to_numpy()
    p_form = done["match_id"].map(form).fillna(0.5).to_numpy()
    p_base = np.full(len(y), base_rate)
    coin = np.full(len(y), 0.5)
    full = done[done["full_first"]]
    counts, _ = np.histogram(full["pit"], bins=PIT_BINS, range=(0.0, 1.0))
    inside80 = (full["first_runs"] >= full["sim_q10"]) & (full["first_runs"] <= full["sim_q90"])
    inside50 = (full["first_runs"] >= full["sim_q25"]) & (full["first_runs"] <= full["sim_q75"])
    # Chi-square test of a uniform PIT histogram.
    expected = len(full) / PIT_BINS
    chi2 = float(((counts - expected) ** 2 / expected).sum()) if len(full) else 0.0
    return {
        "matches": len(done),
        "simulations_per_match": cfg.simulations,
        "forced_overs": forced,
        "win": {
            "simulator": _scores(p, y),
            "coin_flip": _scores(coin, y),
            "bat_first_rate": {**_scores(p_base, y), "rate": round(base_rate, 3)},
            "form": _scores(p_form, y),
            "gain_vs_coin_flip": _bootstrap_gain(p, coin, y, cfg.seed),
            "gain_vs_form": _bootstrap_gain(p, p_form, y, cfg.seed + 1),
            "calibration": calibration(p, y),
            "mean_predicted": round(float(p.mean()), 3),
            "observed": round(float(y.mean()), 3),
            "spread": {
                "min": round(float(p.min()), 3),
                "max": round(float(p.max()), 3),
                "sd": round(float(p.std()), 3),
            },
        },
        "first_innings": {
            "matches": len(full),
            "pit_counts": counts.tolist(),
            "pit_chi2": round(chi2, 2),
            # 5% critical value of chi-square with 9 degrees of freedom.
            "pit_chi2_critical": 16.92,
            "crps": round(float(full["crps"].mean()), 2) if len(full) else None,
            "coverage_80": round(float(inside80.mean()), 3) if len(full) else None,
            "coverage_50": round(float(inside50.mean()), 3) if len(full) else None,
            "actual_mean": round(float(full["first_runs"].mean()), 1),
            "simulated_mean": round(float(full["sim_first_mean"].mean()), 1),
            "actual_wickets": round(float(full["first_wickets"].mean()), 2),
            "simulated_wickets": round(float(full["sim_first_wickets"].mean()), 2),
        },
        "ties": {"simulated": round(float(done["sim_tie"].mean()), 4)},
    }


def _chase_rate(con: duckdb.DuckDBPyConnection, before: int) -> float:
    return 1.0 - _bat_first_rate(con, before)


def evaluate_chases(done: pd.DataFrame, chase_rate: float, cfg: SimulatorConfig) -> dict[str, Any]:
    """From the first ball of each chase (full first innings), the simulated chance
    of reaching the actual target against what happened."""
    full = done[done["full_first"] & done["p_chase"].notna()]
    y = 1.0 - full["first_won"].to_numpy()
    p = full["p_chase"].to_numpy(dtype=float)
    base = np.full(len(y), chase_rate)
    return {
        "matches": len(full),
        "simulator": _scores(p, y),
        "chase_rate": {**_scores(base, y), "rate": round(chase_rate, 3)},
        "gain_vs_chase_rate": _bootstrap_gain(p, base, y, cfg.seed + 2),
        "calibration": calibration(p, y),
        "mean_predicted": round(float(p.mean()), 3),
        "observed": round(float(y.mean()), 3),
    }


def gate(evaluation: dict[str, Any]) -> list[str]:
    """Reasons not to serve: simulated totals must be calibrated, and the bowling
    rules must almost never have to give."""
    problems = []
    first = evaluation["first_innings"]
    if first["pit_chi2"] > first["pit_chi2_critical"]:
        problems.append("first-innings PIT is not uniform at the 5% level")
    overs = evaluation["matches"] * evaluation["simulations_per_match"] * 2 * rules().overs
    if evaluation["forced_overs"] > 0.001 * overs:
        problems.append("more than 0.1% of simulated overs broke a bowling rule")
    return problems


def timing(
    setup: Setup, cfg: SimulatorConfig, conditions_sd: float, repeats: int = 3
) -> dict[str, Any]:
    """Seconds for ``timing_simulations`` complete matches (best of ``repeats``)."""
    best = math.inf
    for i in range(repeats):
        rng = np.random.default_rng(i)
        start = time.perf_counter()
        sim.simulate_match(
            setup.model,
            setup.rates,
            setup.first,
            setup.second,
            n=cfg.timing_simulations,
            rng=rng,
            conditions_sd=conditions_sd,
        )
        best = min(best, time.perf_counter() - start)
    return {"simulations": cfg.timing_simulations, "seconds": round(best, 3)}


def run(
    serving: Path,
    balls: pd.DataFrame,
    fit: Callable[[pd.DataFrame], BallOutcomeModel],
    cfg: SimulatorConfig,
    *,
    data_version: str,
    log: Log = _quiet,
    competition: str | None = None,
) -> tuple[SimulatorSettings, dict[str, Any]]:
    """Tune the conditions spread on the validation seasons, then simulate every
    test match with a ball model that has never seen the test seasons. ``competition``
    picks its balls out of ``balls`` for the tracked scoring level.

    ``balls`` are what ``fit`` trains on (every T20 competition, for a pooled
    model); ``serving`` holds the competition being simulated.
    """
    envs = balls.groupby("match_id")["env"].first().to_dict()
    own = balls if competition is None else balls[balls["competition_id"] == competition]

    def shifts(model: BallOutcomeModel, window: int) -> dict[int, float]:
        if window <= 0:
            return {}
        found, _ = level_shifts(model, own, window)
        return {int(k): float(v) for k, v in found.items()}

    con = duckdb.connect(str(serving), read_only=True)
    try:
        log(f"  validation {cfg.valid}: ball model refit on earlier seasons")
        valid_model = fit(balls[balls["season"] < min(cfg.valid)])
        valid = prepare(con, cfg.valid, valid_model, envs, cfg.history_seasons)
        window = 0
        level_grid: list[dict[str, float]] = []
        if cfg.level_windows:
            window, level_grid = choose_window(valid, lambda w: shifts(valid_model, w), cfg, log)
            log(f"    chosen level window {window or 'none'}")
            valid = with_shifts(valid, shifts(valid_model, window))
        conditions_sd, grid = tune_conditions(valid, cfg, log)
        log(f"    chosen conditions spread {conditions_sd}")

        log(f"  test {cfg.test}: ball model refit on earlier seasons")
        test_model = fit(balls[balls["season"] < min(cfg.test)])
        test = with_shifts(
            prepare(con, cfg.test, test_model, envs, cfg.history_seasons),
            shifts(test_model, window),
        )
        done, forced = simulate_all(test, cfg.simulations, conditions_sd, cfg.seed, chases=True)
        chase_rate = _chase_rate(con, min(cfg.test))
        form = _form_baseline(con, done["match_id"].tolist())
        base_rate = _bat_first_rate(con, min(cfg.test))
    finally:
        con.close()
    evaluation = evaluate(done, form, base_rate, forced, cfg)
    evaluation["chase"] = evaluate_chases(done, chase_rate, cfg)
    evaluation["timing"] = timing(test[-1], cfg, conditions_sd)
    log(
        f"    Brier {evaluation['win']['simulator']['brier']:.4f} "
        f"(coin flip {evaluation['win']['coin_flip']['brier']:.4f}); "
        f"first-innings 80% coverage {evaluation['first_innings']['coverage_80']}, "
        f"PIT chi-square {evaluation['first_innings']['pit_chi2']}; "
        f"{evaluation['timing']['simulations']} matches in {evaluation['timing']['seconds']} s"
    )
    manifest = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "conditions_sd": conditions_sd,
        "history_seasons": cfg.history_seasons,
        "usage_strength": sim.USAGE_STRENGTH,
        "urgent_from_over": rules().urgent_from_over,
        "min_bowling_overs": float(rules().quota),
        **({"level_window": window} if window else {}),
    }
    evaluation = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "valid": cfg.valid,
        "test": cfg.test,
        "settings": manifest,
        "tuning": grid,
        **({"level": {"window": window, "grid": level_grid}} if cfg.level_windows else {}),
        **evaluation,
    }
    return SimulatorSettings(manifest), evaluation
