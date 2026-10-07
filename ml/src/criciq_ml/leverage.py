"""Pressure (leverage) and momentum for every match state.

**Leverage** asks how much the next ball can move the match. For every state,
each possible next ball (a dot, 1, 2, 3, 4 or 6 runs, a wicket, or a wide or
no-ball) is applied to the state, the win probability model scores the
resulting state, and the swings are averaged with the league's chance of each
outcome in that situation (innings, phase, wickets in hand):

    swing(s)    = sum over outcomes o of p(o | s) * |WP(s after o) - WP(s)|
    leverage(s) = swing(s) / mean swing over every historical state
    pressure(s) = percentile of swing(s) among every historical state (0-100)

This is the Leverage Index from baseball analytics (Tango), applied to
cricket with CricIQ's own models. A leverage of 2 means the next ball matters
twice as much as a typical ball.

Tree models move in steps, so the win probability of nearby scores can jump
for no cricket reason. Every win probability in the swing is therefore
averaged over scores within four runs (triangular weights), which removes
most of the ball-to-ball jitter while keeping real spikes such as a last-ball
finish.

**Momentum** is the change in the batting side's win probability over the
last 12 legal balls of the innings, in percentage points: what just happened,
on the scale the match is decided on. Whether it predicts what happens next is
tested in ``criciq_ml.lab``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from criciq_core.phases import model_phases
from criciq_ml import chase
from criciq_ml.data import Inputs
from criciq_ml.features import CREASE_BALLS_CAP, STABLE_COLUMNS, STABLE_DECIMALS
from criciq_ml.model import InningsModel, WinProbabilityModel

# (label, runs added, wickets added, legal balls added)
OUTCOMES: tuple[tuple[str, int, int, int], ...] = (
    ("dot", 0, 0, 1),
    ("one", 1, 0, 1),
    ("two", 2, 0, 1),
    ("three", 3, 0, 1),
    ("four", 4, 0, 1),
    ("six", 6, 0, 1),
    ("wicket", 0, 1, 1),
    ("extra", 1, 0, 0),
)
# Wickets in hand -> outcome-rate bucket (tail-enders score and survive less).
IN_HAND_EDGES = (2, 4, 7)
WINDOW = 12
# (runs offset, weight): win probabilities are averaged over nearby scores.
SMOOTHING: tuple[tuple[int, float], ...] = tuple((d, (5 - abs(d)) / 25) for d in range(-4, 5))


def _phase_keys(over_index: np.ndarray) -> np.ndarray:
    phases = model_phases()
    lookup = {o: phases.phase_for_over_index(min(o, phases.limit - 1)).key for o in range(40)}
    return np.array([lookup[min(int(o), 39)] for o in over_index])


def _in_hand_bucket(in_hand: np.ndarray) -> np.ndarray:
    return np.asarray(np.digitize(in_hand, IN_HAND_EDGES, right=True))


@dataclass(frozen=True)
class OutcomeRates:
    """p(outcome) per (innings, phase, wickets-in-hand bucket), with a league fallback."""

    table: pd.DataFrame
    overall: np.ndarray

    @classmethod
    def estimate(cls, inputs: Inputs) -> OutcomeRates:
        main = inputs.innings[
            ~inputs.innings["is_super_over"] & (inputs.innings["innings_no"] <= 2)
        ]
        d = inputs.deliveries.merge(main[["match_id", "innings_no"]], on=["match_id", "innings_no"])
        outs = d["out_ids"].map(len).to_numpy()
        runs = d["runs_total"].to_numpy().clip(max=6)
        runs = np.where(runs == 5, 4, runs)
        legal = d["is_legal"].to_numpy(dtype=bool)
        label = np.select(
            [~legal, outs > 0, runs == 0, runs == 1, runs == 2, runs == 3, runs == 4],
            ["extra", "wicket", "dot", "one", "two", "three", "four"],
            default="six",
        )
        frame = pd.DataFrame(
            {
                "innings_no": d["innings_no"].to_numpy(),
                "phase": _phase_keys(d["over_no"].to_numpy()),
                "bucket": _in_hand_bucket(10 - (d["team_wickets"].to_numpy() - outs)),
                "outcome": label,
            }
        )
        counts = pd.crosstab(
            [frame["innings_no"], frame["phase"], frame["bucket"]], frame["outcome"]
        ).reindex(columns=[o[0] for o in OUTCOMES], fill_value=0)
        overall = counts.sum().to_numpy(dtype=float)
        # Thin cells borrow strength from the league's overall rates.
        prior = 50.0 * overall / overall.sum()
        table = (counts + prior).div((counts + prior).sum(axis=1), axis=0)
        return cls(table=table, overall=overall / overall.sum())

    def for_states(self, states: pd.DataFrame) -> np.ndarray:
        """Next-ball outcome probabilities for each state, in OUTCOMES order."""
        keys = pd.MultiIndex.from_arrays(
            [
                states["innings_no"].to_numpy(),
                _phase_keys(states["legal_balls"].to_numpy() // 6),
                _in_hand_bucket(10 - states["wickets"].to_numpy()),
            ]
        )
        found: np.ndarray = np.array(self.table.reindex(keys).to_numpy(dtype=float), copy=True)
        missing = np.isnan(found).any(axis=1)
        found[missing] = self.overall
        return found


def _dropping_out(states: pd.DataFrame, inputs: Inputs) -> tuple[np.ndarray, np.ndarray]:
    """Runs and wickets that leave the last-12-balls window when the next legal ball arrives."""
    d = inputs.deliveries
    per_ball = (
        d.assign(w=d["out_ids"].map(len))
        .groupby(["match_id", "innings_no", "legal_ball_no"], as_index=False)
        .agg(drop_runs=("runs_total", "sum"), drop_wkts=("w", "sum"))
    )
    keys = states[["match_id", "innings_no"]].assign(
        legal_ball_no=states["legal_balls"] - (WINDOW - 1)
    )
    merged = keys.merge(per_ball, on=["match_id", "innings_no", "legal_ball_no"], how="left")
    return (
        merged["drop_runs"].fillna(0).to_numpy(dtype=float),
        merged["drop_wkts"].fillna(0).to_numpy(dtype=float),
    )


# Columns of a state that the next ball does not change (the match context).
_CARRIED = (
    "innings_no",
    "season",
    "year",
    "competition_id",
    "max_balls",
    "env_rpb",
    "target",
    "international",
    "venue_idx",
    "opp_bat_strength",
    "own_bowl_strength",
    # The batters at the crease (pooled models): after a wicket the incoming batter is
    # not known, so their records carry over unchanged.
    "crease_sr_idx",
    "crease_avg_idx",
)


def _after(
    states: pd.DataFrame,
    runs: int,
    wickets: int,
    legal: int,
    drop: tuple[np.ndarray, np.ndarray],
    tables: chase.SeasonTables,
    chasing: bool,
    stable: bool = False,
) -> pd.DataFrame:
    """The states that would follow one outcome, with every model feature rebuilt."""
    s = states
    nxt = pd.DataFrame(index=s.index)
    for column in _CARRIED:
        if column in s:
            nxt[column] = s[column]
    nxt["legal_balls"] = s["legal_balls"] + legal
    nxt["runs"] = (s["runs"] + runs).clip(lower=0)
    nxt["wickets"] = (s["wickets"] + wickets).clip(upper=10)
    nxt["balls_remaining"] = (s["max_balls"] - nxt["legal_balls"]).clip(lower=0)
    if "crease_balls" in s:
        faced = s["crease_balls"] + (legal if not wickets else 0)
        nxt["crease_balls"] = faced.clip(upper=CREASE_BALLS_CAP)
    nxt["runs_last_12"] = s["runs_last_12"] + runs - (drop[0] if legal else 0)
    nxt["wickets_last_12"] = s["wickets_last_12"] + wickets - (drop[1] if legal else 0)
    nxt["runs_vs_par"] = nxt["runs"] - s["env_rpb"] * nxt["legal_balls"]
    if chasing:
        needed = (s["target"] - nxt["runs"]).clip(lower=0)
        left = nxt["balls_remaining"]
        nxt["runs_needed"] = needed
        nxt["required_rate"] = np.where(
            left > 0, (needed * 6 / left.clip(lower=1)).clip(upper=36.0), 36.0
        )
        nxt["chase_ratio"] = np.log1p(needed) - np.log1p(left)
        nxt["required_rate_rel"] = nxt["required_rate"] / (6 * s["env_rpb"])
        dp = np.full(len(s), np.nan)
        # Chase tables by calendar year and competition, as the features build them.
        years = s["year"].to_numpy() if "year" in s else s["season"].to_numpy()
        competitions = (
            s["competition_id"].to_numpy() if "competition_id" in s else np.full(len(s), "")
        )
        w = (10 - nxt["wickets"].to_numpy()).clip(0, 10).astype(int)
        b = left.to_numpy().clip(0, chase.MAX_BALLS).astype(int)
        r = needed.fillna(0).to_numpy().clip(0, chase.MAX_RUNS).astype(int)
        cells = {(int(y), str(c)) for y, c in zip(years, competitions, strict=True)}
        for year, competition in cells:
            mask = (years == year) & (competitions == competition)
            table = tables.for_season(year, competition)
            dp[mask] = table[w[mask], b[mask], r[mask]]
        nxt["chase_dp"] = dp
    if stable:
        for column in STABLE_COLUMNS:
            if column in nxt:
                nxt[column] = nxt[column].round(STABLE_DECIMALS)
    return nxt


def _smoothed(
    inn_model: InningsModel,
    states: pd.DataFrame,
    tables: chase.SeasonTables,
    chasing: bool,
    stable: bool = False,
) -> np.ndarray:
    """Win probability averaged over scores within a few runs (see SMOOTHING)."""
    still = (np.zeros(len(states)), np.zeros(len(states)))
    out = np.zeros(len(states))
    for delta, weight in SMOOTHING:
        out += weight * inn_model.predict(
            _after(states, delta, 0, 0, still, tables, chasing, stable)
        )
    return out


def expected_swing(
    model: WinProbabilityModel,
    states: pd.DataFrame,
    inputs: Inputs,
    rates: OutcomeRates | None = None,
) -> np.ndarray:
    """Expected absolute change in the batting side's win probability on the next ball.

    NaN where the innings is already over (no next ball).
    """
    rates = rates or OutcomeRates.estimate(inputs)
    by_match = inputs.matches.set_index("match_id")
    tables = chase.SeasonTables(
        inputs.deliveries,
        inputs.deliveries["match_id"].map(by_match["year"]),
        inputs.deliveries["match_id"].map(by_match["competition_id"]),
    )
    stable = model.feature_config.stable
    swing = np.full(len(states), np.nan)
    states = states.reset_index(drop=True)
    for number, inn_model in model.innings.items():
        mask = (states["innings_no"] == number).to_numpy()
        live = (
            mask
            & (states["legal_balls"] < states["max_balls"]).to_numpy()
            & (states["wickets"] < 10).to_numpy()
        )
        if number == 2:
            live &= (states["runs"] < states["target"]).to_numpy()
        if not live.any():
            continue
        s = states.loc[live]
        probs = rates.for_states(s)
        drop = _dropping_out(s, inputs)
        chasing = number == 2
        now = _smoothed(inn_model, s, tables, chasing, stable)
        total = np.zeros(len(s))
        for k, (_, runs, wickets, legal) in enumerate(OUTCOMES):
            nxt = _after(s, runs, wickets, legal, drop, tables, chasing, stable)
            p = _smoothed(inn_model, nxt, tables, chasing, stable)
            if number == 2:
                won = (nxt["runs"] >= s["target"]).to_numpy()
                over = ((nxt["wickets"] >= 10) | (nxt["legal_balls"] >= s["max_balls"])).to_numpy()
                tie = (nxt["runs"] == s["target"] - 1).to_numpy()
                p = np.where(won, 1.0, np.where(over, np.where(tie, 0.5, 0.0), p))
            total += probs[:, k] * np.abs(p - now)
        swing[live] = total
    return swing


def momentum(states: pd.DataFrame, wp_batting: np.ndarray) -> np.ndarray:
    """Batting side's win probability now minus 12 legal balls ago, in points.

    Measured from the innings' first state until 12 legal balls have been bowled.
    """
    frame = states[["match_id", "innings_no", "seq_no", "legal_balls"]].reset_index(drop=True)
    frame = frame.assign(wp=wp_batting)
    out = np.full(len(frame), np.nan)
    for _, group in frame.groupby(["match_id", "innings_no"], sort=False):
        g = group.sort_values("seq_no")
        legal = g["legal_balls"].to_numpy()
        wp = g["wp"].to_numpy()
        # The last state with at most (legal - 12) legal balls bowled.
        idx = np.searchsorted(legal, legal - WINDOW, side="right") - 1
        out[g.index.to_numpy()] = 100 * (wp - wp[np.maximum(idx, 0)])
    return out


def pressure_scale(swing: np.ndarray) -> dict[str, Any]:
    """Mean swing and the 101 percentiles that turn a swing into a 0-100 pressure index."""
    live = swing[~np.isnan(swing)]
    return {
        "mean_swing": float(live.mean()),
        "quantiles": [float(q) for q in np.quantile(live, np.linspace(0, 1, 101))],
    }


def pressure(swing: np.ndarray, quantiles: list[float]) -> np.ndarray:
    """Percentile (0-100) of each swing among every historical state."""
    q = np.asarray(quantiles)
    out = np.searchsorted(q, swing, side="right") - 1
    return np.where(np.isnan(swing), np.nan, np.clip(out, 0, 100))
