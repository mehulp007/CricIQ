"""Analytics Lab: research notes on momentum, pressure, clutch and rivalries.

Each note asks one question of the scored data and answers it with a test
that could have come out the other way:

* **Momentum.** Does a side that has gained win probability over the last 12
  balls keep scoring faster than expected over the next 12, or win more often
  than its current win probability says?
* **Pressure.** How do strike rate, dot balls, boundaries and dismissals change
  as the pressure index rises, measured against what the ball-outcome model
  expects of those batters and bowlers in those situations?
* **Clutch.** Do some batters (or bowlers) reliably do better in high-pressure
  balls than in the rest? If so, a player's record in odd seasons should
  predict it in even seasons.
* **Rivalries.** Does a side that has dominated a rivalry beat that opponent more
  often than both sides' form that season predicts? And is winning close
  finishes a repeatable team trait, or a coin flip?

"Expected" always comes from the served ball-outcome model, which knows the
batter, the bowler, the phase, the wickets, how settled the batter is and the
chase equation, so any difference is beyond all of those.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from criciq_core import paths
from criciq_core.teams import FORM_PRIOR
from criciq_ml import registry
from criciq_ml.ball_outcome import OUT, RUNS, load_balls

LAB_DIR = paths.repo_root() / "frontend" / "data" / "lab"
SEED = 7
REPS = 400
# Pressure bands on the 0-100 index (percentiles of leverage).
BANDS: tuple[tuple[str, int, int], ...] = (
    ("Low", 0, 50),
    ("Medium", 50, 80),
    ("High", 80, 95),
    ("Very high", 95, 101),
)
HIGH_PRESSURE = 80
MOMENTUM_BANDS: tuple[tuple[str, float, float], ...] = (
    ("Lost 15+ points", -101.0, -15.0),
    ("Lost 5-15", -15.0, -5.0),
    ("Level (within 5)", -5.0, 5.0),
    ("Gained 5-15", 5.0, 15.0),
    ("Gained 15+", 15.0, 101.0),
)
CLUTCH_MIN_BALLS = 60
# A split-half correlation this high would make clutch usable as a rating (docs/PLAN.md).
RELIABLE_R = 0.3
# Rivalries: a side "leads" a rivalry after at least RIVALRY_MIN_PRIOR earlier meetings.
RIVALRY_MIN_PRIOR = 6
RIVALRY_LEAD = 0.6
FORM_BANDS: tuple[tuple[str, float, float], ...] = (
    ("Slight (50-52.5%)", 0.5, 0.525),
    ("Moderate (52.5-55%)", 0.525, 0.55),
    ("Clear (55%+)", 0.55, 1.01),
)
# Shrinkage strengths (matches at 50%) scanned to show how little form predicts.
FORM_PRIORS = (2, 10, 20, 40, 80, 160)
CLOSE_MIN_GAMES = 3
# Fewer meetings than this give no slope (e.g. on the test fixtures).
MIN_SLOPE_MEETINGS = 20


# --------------------------------------------------------------------------- data


def load_lab_balls(serving: Path) -> pd.DataFrame:
    """Every ball faced, with the model's expectation and the pressure before it was bowled."""
    balls = load_balls(serving)
    model = registry.load_current_ball_outcome()
    probs = model.predict(balls)
    balls["expected_runs"] = probs @ RUNS
    balls["p_out"] = probs[:, OUT]
    balls["is_out"] = (balls["outcome"] == OUT).astype(float)
    con = duckdb.connect(str(serving), read_only=True)
    try:
        before = con.execute(
            """
            WITH prev AS (
                SELECT match_id, innings_no, seq_no,
                       coalesce(lag(seq_no) OVER (
                           PARTITION BY match_id, innings_no ORDER BY seq_no), 0) AS prev_seq
                FROM deliveries
            )
            SELECT p.match_id, p.innings_no, p.seq_no, w.pressure, w.leverage
            FROM prev p
            JOIN wp_predictions w
              ON w.match_id = p.match_id AND w.innings_no = p.innings_no
             AND w.seq_no = p.prev_seq
            """
        ).df()
    finally:
        con.close()
    return balls.merge(before, on=["match_id", "innings_no", "seq_no"], how="left")


def load_states(serving: Path) -> pd.DataFrame:
    """Every match state with momentum and the batting side's eventual result."""
    con = duckdb.connect(str(serving), read_only=True)
    try:
        return con.execute(
            """
            SELECT w.match_id, w.innings_no, w.seq_no, w.momentum, w.pressure,
                   CASE WHEN w.innings_no = 1 THEN w.wp_team_a ELSE 1 - w.wp_team_a END
                       AS wp_batting,
                   d.legal_ball_no AS legal_balls,
                   coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over) AS max_balls,
                   CASE WHEN m.outcome_type = 'tie' THEN 0.5
                        WHEN m.outcome_type = 'win' AND m.winner_id = i.batting_team_id THEN 1.0
                        WHEN m.outcome_type = 'win' THEN 0.0 END AS result
            FROM wp_predictions w
            JOIN innings i USING (match_id, innings_no)
            JOIN matches m USING (match_id)
            LEFT JOIN deliveries d USING (match_id, innings_no, seq_no)
            WHERE w.momentum IS NOT NULL
            """
        ).df()
    finally:
        con.close()


# --------------------------------------------------------------------------- statistics


def _weights(matches: int, reps: int = REPS) -> np.ndarray:
    """How often each match appears in each bootstrap resample (resampling whole matches)."""
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, matches, size=(reps, matches))
    return np.stack([np.bincount(row, minlength=matches) for row in draws]).astype(float)


def _per_match(frame: pd.DataFrame, x: str | None, y: str) -> pd.DataFrame:
    f = frame.assign(_x=frame[x] if x else 0.0, _y=frame[y])
    f = f.assign(_xx=f["_x"] ** 2, _xy=f["_x"] * f["_y"])
    return (
        f.groupby("match_id")[["_x", "_y", "_xx", "_xy"]]
        .sum()
        .assign(n=f.groupby("match_id").size())
    )


def bootstrap_mean(
    frame: pd.DataFrame, column: str, scale: float = 1.0
) -> tuple[float, float, float]:
    """Mean with a 90% interval, resampling matches (balls within a match are not independent)."""
    if frame.empty:
        return float("nan"), float("nan"), float("nan")
    sums = _per_match(frame, None, column)
    w = _weights(len(sums))
    draws = scale * (w @ sums["_y"].to_numpy()) / (w @ sums["n"].to_numpy())
    low, high = np.nanpercentile(draws, [5, 95])
    return scale * float(frame[column].mean()), float(low), float(high)


def bootstrap_slope(
    frame: pd.DataFrame, x: str, y: str, scale: float = 1.0
) -> tuple[float, float, float]:
    """Least-squares slope of y on x with a 90% interval, resampling matches."""
    sums = _per_match(frame, x, y)
    w = _weights(len(sums))
    n, sx, sy = w @ sums["n"].to_numpy(), w @ sums["_x"].to_numpy(), w @ sums["_y"].to_numpy()
    sxx, sxy = w @ sums["_xx"].to_numpy(), w @ sums["_xy"].to_numpy()
    draws = scale * (sxy - sx * sy / n) / (sxx - sx * sx / n)
    xs, ys = frame[x].to_numpy(), frame[y].to_numpy()
    xc = xs - xs.mean()
    estimate = scale * float((xc * (ys - ys.mean())).sum() / (xc * xc).sum())
    low, high = np.nanpercentile(draws, [5, 95])
    return estimate, float(low), float(high)


def _ci(values: tuple[float, float, float], digits: int = 3) -> dict[str, float]:
    estimate, low, high = values
    return {
        "value": round(estimate, digits),
        "low": round(low, digits),
        "high": round(high, digits),
    }


# --------------------------------------------------------------------------- momentum


def momentum_note(balls: pd.DataFrame, states: pd.DataFrame) -> dict[str, Any]:
    """Momentum against the next 12 balls (beyond expectation) and against the result."""
    balls = balls.sort_values(["match_id", "innings_no", "seq_no"])
    balls["resid_runs"] = balls["runs_batter"] - balls["expected_runs"]
    balls["resid_outs"] = balls["is_out"] - balls["p_out"]
    # For each state at the end of an over: what the next 12 balls faced brought.
    ends = states[
        (states["legal_balls"] % 6 == 0)
        & (states["legal_balls"] >= 12)
        & (states["legal_balls"] <= states["max_balls"] - 12)
    ].copy()
    by_innings = {k: g for k, g in ends.groupby(["match_id", "innings_no"], sort=False)}
    rows = []
    for (mid, inn), group in balls.groupby(["match_id", "innings_no"], sort=False):
        seqs = group["seq_no"].to_numpy()
        runs = np.concatenate([[0.0], np.cumsum(group["resid_runs"].to_numpy())])
        outs = np.concatenate([[0.0], np.cumsum(group["resid_outs"].to_numpy())])
        actual = np.concatenate([[0.0], np.cumsum(group["runs_batter"].to_numpy())])
        mine = by_innings.get((mid, inn))
        if mine is None:
            continue
        for state in mine.itertuples(index=False):
            start = int(np.searchsorted(seqs, state.seq_no, side="right"))
            stop = start + 12
            if stop > len(seqs):
                continue
            rows.append(
                (
                    mid,
                    inn,
                    state.momentum,
                    state.wp_batting,
                    state.result,
                    runs[stop] - runs[start],
                    outs[stop] - outs[start],
                    actual[stop] - actual[start],
                )
            )
    sample = pd.DataFrame(
        rows,
        columns=[
            "match_id",
            "innings_no",
            "momentum",
            "wp",
            "result",
            "runs_above",
            "wickets_above",
            "runs",
        ],
    )
    sample["result_above"] = sample["result"] - sample["wp"]
    resolved = sample.dropna(subset=["result"])
    bands = []
    for label, low, high in MOMENTUM_BANDS:
        band = sample[(sample["momentum"] >= low) & (sample["momentum"] < high)]
        res = resolved[(resolved["momentum"] >= low) & (resolved["momentum"] < high)]
        bands.append(
            {
                "label": label,
                "states": len(band),
                "runs_next_12": round(float(band["runs"].mean()), 2),
                "runs_above_expected": _ci(bootstrap_mean(band, "runs_above"), 2),
                "wickets_above_expected": _ci(bootstrap_mean(band, "wickets_above"), 3),
                "result_above_wp": _ci(bootstrap_mean(res, "result_above"), 3),
            }
        )
    return {
        "slug": "momentum",
        "states": len(sample),
        "matches": int(sample["match_id"].nunique()),
        "momentum_sd": round(float(sample["momentum"].std()), 1),
        "runs_per_10_points": _ci(bootstrap_slope(sample, "momentum", "runs_above", 10), 3),
        "wickets_per_10_points": _ci(bootstrap_slope(sample, "momentum", "wickets_above", 10), 4),
        "result_per_10_points": _ci(bootstrap_slope(resolved, "momentum", "result_above", 10), 4),
        "bands": bands,
    }


# --------------------------------------------------------------------------- pressure


def _band_of(pressure: pd.Series) -> pd.Series:
    labels = pd.Series("", index=pressure.index)
    for label, low, high in BANDS:
        labels[(pressure >= low) & (pressure < high)] = label
    return labels


def pressure_note(
    balls: pd.DataFrame, top_moments: list[dict[str, Any]], check: list[dict[str, Any]]
) -> dict[str, Any]:
    scored = balls.dropna(subset=["pressure"]).copy()
    scored["band"] = _band_of(scored["pressure"])
    rows = []
    for label, low, high in BANDS:
        for innings in (1, 2):
            b = scored[(scored["band"] == label) & (scored["innings_no"] == innings)]
            if b.empty:
                continue
            n = len(b)
            rows.append(
                {
                    "band": label,
                    "from": low,
                    "to": min(high, 100),
                    "innings_no": innings,
                    "balls": n,
                    "share": round(n / len(scored[scored["innings_no"] == innings]), 4),
                    "strike_rate": round(100 * b["runs_batter"].sum() / n, 1),
                    "expected_strike_rate": round(100 * b["expected_runs"].sum() / n, 1),
                    "dot_pct": round(100 * float((b["runs_batter"] == 0).mean()), 1),
                    "boundary_pct": round(100 * float(b["runs_batter"].isin([4, 6]).mean()), 1),
                    "dismissals_per_100": round(100 * float(b["is_out"].mean()), 2),
                    "expected_dismissals_per_100": round(100 * float(b["p_out"].mean()), 2),
                    "runs_above_expected_per_100": _ci(
                        bootstrap_mean(b.assign(r=b["runs_batter"] - b["expected_runs"]), "r", 100),
                        2,
                    ),
                }
            )
    return {
        "slug": "pressure",
        "balls": len(scored),
        "bands": [
            {"label": label, "from": low, "to": min(high, 100)} for label, low, high in BANDS
        ],
        "rows": rows,
        "top_moments": top_moments,
        "swing_check": check,
    }


def swing_check(serving: Path, bins: int = 10) -> list[dict[str, Any]]:
    """Does leverage anticipate how far the win probability actually moves on the next ball?

    States are grouped by leverage; for each group, the average realised change
    in the batting side's win probability on the next ball is compared with
    the average for every ball (so 1 means a typical ball, like leverage).
    """
    con = duckdb.connect(str(serving), read_only=True)
    try:
        frame = con.execute(
            """
            WITH w AS (
                SELECT match_id, innings_no, seq_no, leverage,
                       CASE WHEN innings_no = 1 THEN wp_team_a ELSE 1 - wp_team_a END AS wp
                FROM wp_predictions WHERE innings_no <= 2
            )
            SELECT match_id, leverage,
                   abs(lead(wp) OVER (PARTITION BY match_id, innings_no ORDER BY seq_no) - wp)
                       AS realised
            FROM w
            """
        ).df()
    finally:
        con.close()
    frame = frame.dropna(subset=["leverage", "realised"])
    mean_realised = frame["realised"].mean()
    frame["group"] = pd.qcut(frame["leverage"].rank(method="first"), bins, labels=False)
    out = []
    for _, g in frame.groupby("group"):
        realised = bootstrap_mean(g.assign(r=g["realised"] / mean_realised), "r")
        out.append(
            {
                "balls": len(g),
                "leverage": round(float(g["leverage"].mean()), 3),
                "realised": _ci(realised, 3),
            }
        )
    return out


def top_moments(serving: Path, count: int = 10) -> list[dict[str, Any]]:
    """The highest-pressure balls in IPL history, one per match, and what happened."""
    con = duckdb.connect(str(serving), read_only=True)
    try:
        rows = con.execute(
            """
            WITH ranked AS (
                SELECT w.*, row_number() OVER (PARTITION BY match_id ORDER BY leverage DESC) AS r
                FROM wp_predictions w WHERE leverage IS NOT NULL AND innings_no <= 2
            ),
            nxt AS (
                SELECT r.match_id, r.innings_no, r.seq_no AS state_seq, r.leverage,
                       min(d.seq_no) AS next_seq
                FROM ranked r JOIN deliveries d
                  ON d.match_id = r.match_id AND d.innings_no = r.innings_no
                 AND d.seq_no > r.seq_no
                WHERE r.r = 1
                GROUP BY ALL
            )
            SELECT n.match_id, n.innings_no, n.next_seq, n.leverage, d.ball_label,
                   d.team_runs - d.runs_total AS runs_before, d.legal_ball_no, d.runs_total,
                   d.is_four, d.is_six, d.team_wickets, i.target_runs,
                   coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over) AS max_balls,
                   wk.kind AS wicket_kind, pb.name AS batter, pw.name AS bowler,
                   ms.season, ms.match_date, ms.team_a_short, ms.team_b_short, ms.stage,
                   ms.result_text
            FROM nxt n
            JOIN deliveries d ON d.match_id = n.match_id AND d.innings_no = n.innings_no
                             AND d.seq_no = n.next_seq
            JOIN innings i ON i.match_id = n.match_id AND i.innings_no = n.innings_no
            JOIN matches m ON m.match_id = n.match_id
            JOIN match_summaries ms ON ms.match_id = n.match_id
            JOIN players pb ON pb.player_id = d.batter_id
            JOIN players pw ON pw.player_id = d.bowler_id
            LEFT JOIN wickets wk ON wk.match_id = d.match_id AND wk.innings_no = d.innings_no
                                AND wk.seq_no = d.seq_no AND wk.is_dismissal
            ORDER BY n.leverage DESC LIMIT ?
            """,
            [count],
        ).df()
    finally:
        con.close()
    moments = []
    for r in rows.itertuples(index=False):
        if r.wicket_kind is not None and r.wicket_kind == r.wicket_kind:
            happened = f"{r.batter} out ({r.wicket_kind})"
        elif r.is_six:
            happened = f"{r.batter} hit a six"
        elif r.is_four:
            happened = f"{r.batter} hit a four"
        else:
            happened = f"{int(r.runs_total)} run{'s' if r.runs_total != 1 else ''}"
        balls_before = int(r.legal_ball_no) - 1
        needed = None if pd.isna(r.target_runs) else int(r.target_runs) - int(r.runs_before)
        moments.append(
            {
                "match_id": int(r.match_id),
                "innings_no": int(r.innings_no),
                "seq_no": int(r.next_seq),
                "ball_label": r.ball_label,
                "season": int(r.season),
                "date": str(r.match_date)[:10],
                "teams": f"{r.team_a_short} v {r.team_b_short}",
                "stage": r.stage,
                "result": r.result_text,
                "leverage": round(float(r.leverage), 1),
                "situation": (
                    f"{needed} needed from {int(r.max_balls) - balls_before} "
                    f"{'ball' if int(r.max_balls) - balls_before == 1 else 'balls'}"
                    if needed is not None
                    else f"{int(r.runs_before)}/{int(r.team_wickets)} after {balls_before} balls"
                ),
                "bowler": r.bowler,
                "happened": happened,
            }
        )
    return moments


# --------------------------------------------------------------------------- clutch


def _clutch_table(balls: pd.DataFrame, role: str) -> pd.DataFrame:
    """Per player and half (odd/even seasons): runs above expected in high and in other balls."""
    player = "batter_id" if role == "batting" else "bowler_id"
    sign = 1.0 if role == "batting" else -1.0  # bowlers gain by conceding less
    b = balls.dropna(subset=["pressure"]).assign(
        value=lambda f: sign * (f["runs_batter"] - f["expected_runs"]),
        high=lambda f: f["pressure"] >= HIGH_PRESSURE,
        half=lambda f: f["season"] % 2,
    )
    return (
        b.groupby([player, "half", "high"])["value"]
        .agg(["sum", "count", "var"])
        .unstack("high")
        .rename_axis(index=["player_id", "half"])
    )


def clutch_note(balls: pd.DataFrame, names: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {"slug": "clutch", "high_pressure": HIGH_PRESSURE, "roles": {}}
    for role in ("batting", "bowling"):
        t = _clutch_table(balls, role)
        hi_n, lo_n = t[("count", True)], t[("count", False)]
        clutch = 100 * (t[("sum", True)] / hi_n - t[("sum", False)] / lo_n)
        per_half = pd.DataFrame({"clutch": clutch, "high_balls": hi_n}).reset_index()
        per_half = per_half[per_half["high_balls"] >= CLUTCH_MIN_BALLS]
        wide = (
            per_half.pivot(index="player_id", columns="half", values="clutch")
            .reindex(columns=[0, 1])
            .dropna()
        )
        r = float(np.corrcoef(wide[0], wide[1])[0, 1]) if len(wide) >= 10 else None
        # Correlation of the halves under no clutch skill, by permutation.
        rng = np.random.default_rng(SEED)
        null = (
            [
                float(np.corrcoef(wide[0], rng.permutation(wide[1].to_numpy()))[0, 1])
                for _ in range(500)
            ]
            if len(wide) >= 10
            else []
        )
        # Career view, descriptive: players with the most high-pressure balls.
        career = t.groupby(level="player_id").sum(min_count=1)
        c_hi, c_lo = career[("count", True)], career[("count", False)]
        c_clutch = 100 * (career[("sum", True)] / c_hi - career[("sum", False)] / c_lo)
        var = float((balls["runs_batter"] - balls["expected_runs"]).var())
        se = 100 * np.sqrt(var / c_hi + var / c_lo)
        leaders = (
            pd.DataFrame({"clutch": c_clutch, "se": se, "high_balls": c_hi, "other_balls": c_lo})
            .dropna()
            .sort_values("high_balls", ascending=False)
            .head(15)
        )
        out["roles"][role] = {
            "players": len(wide),
            "min_high_balls": CLUTCH_MIN_BALLS,
            "split_half_r": None if r is None else round(r, 3),
            "null_90": None if not null else round(float(np.percentile(np.abs(null), 90)), 3),
            "p_value": None
            if r is None or not null
            else round(float(np.mean(np.abs(null) >= abs(r))), 3),
            "reliable_r": RELIABLE_R,
            "halves": [
                {
                    "player_id": pid,
                    "name": names.get(pid, pid),
                    "odd": round(o, 1),
                    "even": round(e, 1),
                }
                for pid, o, e in zip(wide.index, wide[1], wide[0], strict=True)
            ],
            "most_exposed": [
                {
                    "player_id": pid,
                    "name": names.get(pid, pid),
                    "high_balls": int(row.high_balls),
                    "clutch": round(float(row.clutch), 1),
                    "low": round(float(row.clutch - 1.645 * row.se), 1),
                    "high": round(float(row.clutch + 1.645 * row.se), 1),
                }
                for pid, row in leaders.iterrows()
            ],
        }
    return out


# --------------------------------------------------------------------------- rivalries


def load_team_matches(serving: Path) -> pd.DataFrame:
    """Decided matches from each side's point of view (team Analytics tables)."""
    con = duckdb.connect(str(serving), read_only=True)
    try:
        return con.execute(
            """
            SELECT match_id, match_order, season, franchise_id, opponent_id, is_close,
                   form_won, form_decided, (result = 'won')::DOUBLE AS won
            FROM team_matches WHERE result <> 'no_result'
            ORDER BY match_order, franchise_id
            """
        ).df()
    finally:
        con.close()


def _log5(p_a: np.ndarray, p_b: np.ndarray) -> np.ndarray:
    num = p_a * (1 - p_b)
    return np.asarray(num / (num + p_b * (1 - p_a)), dtype=float)


def _form(won: pd.Series, decided: pd.Series, prior: float = FORM_PRIOR) -> np.ndarray:
    return np.asarray((won + prior / 2) / (decided + prior), dtype=float)


def meetings_with_form(sides: pd.DataFrame) -> pd.DataFrame:
    """One row per decided match (from the alphabetically first side), with each side's form.

    Form is the side's shrunk win rate in its previous matches (``form_won`` of
    ``form_decided``, built by the pipeline from results before the match only;
    see criciq_core.teams); log5 turns the two forms into the chance the first
    side wins. ``prior_won``/``prior_n`` are the first side's earlier meetings
    with this opponent, in any season.
    """
    first = sides[sides["franchise_id"] < sides["opponent_id"]]
    other = sides[["match_id", "franchise_id", "form_won", "form_decided"]].rename(
        columns={
            "franchise_id": "opponent_id",
            "form_won": "opp_form_won",
            "form_decided": "opp_form_decided",
        }
    )
    first = first.merge(other, on=["match_id", "opponent_id"])
    first = first.sort_values("match_order").reset_index(drop=True)
    first["expected"] = _log5(
        _form(first["form_won"], first["form_decided"]),
        _form(first["opp_form_won"], first["opp_form_decided"]),
    )
    pair = first.groupby(["franchise_id", "opponent_id"])
    first["prior_won"] = pair["won"].cumsum() - first["won"]
    first["prior_n"] = pair.cumcount()
    return first


def _leader_view(meetings: pd.DataFrame) -> pd.DataFrame:
    """Each meeting from the side that had won more of the earlier meetings."""
    m = meetings[meetings["prior_n"] > 0].copy()
    share = m["prior_won"] / m["prior_n"]
    flip = share < 0.5
    m["lead_share"] = np.where(flip, 1 - share, share)
    m["won"] = np.where(flip, 1 - m["won"], m["won"])
    m["expected"] = np.where(flip, 1 - m["expected"], m["expected"])
    m["excess"] = m["won"] - m["expected"]
    return m[share != 0.5]


def _group(frame: pd.DataFrame, label: str) -> dict[str, Any]:
    some = len(frame) > 0
    return {
        "label": label,
        "meetings": len(frame),
        "win_pct": round(100 * float(frame["won"].mean()), 1) if some else None,
        "expected_pct": round(100 * float(frame["expected"].mean()), 1) if some else None,
        "excess": _ci(bootstrap_mean(frame, "excess", 100), 1) if len(frame) >= 2 else None,
    }


def _persistence(sides: pd.DataFrame) -> dict[str, Any]:
    """Season-to-season correlation of close-finish and other win rates for each franchise."""
    rates = (
        sides.assign(kind=np.where(sides["is_close"], "close", "other"))
        .groupby(["franchise_id", "season", "kind"])["won"]
        .agg(["mean", "count"])
        .unstack("kind")
    )
    rates.columns = [f"{a}_{b}" for a, b in rates.columns]
    rates = rates.reset_index()
    nxt = rates.assign(season=rates["season"] - 1)
    pairs = rates.merge(nxt, on=["franchise_id", "season"], suffixes=("", "_next"))
    # Reference: how much a side's whole record carries over to the next season.
    overall = sides.groupby(["franchise_id", "season"])["won"].mean().reset_index()
    following = overall.assign(season=overall["season"] - 1)
    both = overall.merge(following, on=["franchise_id", "season"], suffixes=("", "_next"))
    win_r = float(np.corrcoef(both["won"], both["won_next"])[0, 1]) if len(both) >= 10 else None
    pairs = pairs[
        (pairs["count_close"] >= CLOSE_MIN_GAMES) & (pairs["count_close_next"] >= CLOSE_MIN_GAMES)
    ]
    out: dict[str, Any] = {
        "pairs": len(pairs),
        "min_close": CLOSE_MIN_GAMES,
        "season_pairs": len(both),
        "win_r": None if win_r is None else round(win_r, 3),
    }
    if len(pairs) < 10:
        return out | {"close_r": None, "other_r": None, "null_90": None, "p_value": None}
    close_r = float(np.corrcoef(pairs["mean_close"], pairs["mean_close_next"])[0, 1])
    other_r = float(np.corrcoef(pairs["mean_other"], pairs["mean_other_next"])[0, 1])
    rng = np.random.default_rng(SEED)
    nxt_close = pairs["mean_close_next"].to_numpy()
    null = [
        float(np.corrcoef(pairs["mean_close"], rng.permutation(nxt_close))[0, 1])
        for _ in range(500)
    ]
    return out | {
        "close_r": round(close_r, 3),
        "other_r": round(other_r, 3),
        "null_90": round(float(np.percentile(np.abs(null), 90)), 3),
        "p_value": round(float(np.mean(np.abs(null) >= abs(close_r))), 3),
        "points": [
            {
                "team": row.franchise_id,
                "season": int(row.season),
                "close": round(100 * float(row.mean_close), 1),
                "close_next": round(100 * float(row.mean_close_next), 1),
                "games": int(row.count_close),
                "games_next": int(row.count_close_next),
            }
            for row in pairs.itertuples()
        ],
    }


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def form_scan(meetings: pd.DataFrame) -> list[dict[str, float]]:
    """Log loss of the form expectation at several shrinkage strengths."""
    y = meetings["won"].to_numpy()
    return [
        {
            "prior": prior,
            "log_loss": round(
                _log_loss(
                    y,
                    _log5(
                        _form(meetings["form_won"], meetings["form_decided"], prior),
                        _form(meetings["opp_form_won"], meetings["opp_form_decided"], prior),
                    ),
                ),
                4,
            ),
        }
        for prior in FORM_PRIORS
    ]


def rivalries_note(sides: pd.DataFrame) -> dict[str, Any]:
    meetings = meetings_with_form(sides)
    # Does the form expectation itself work? From the side form favours.
    fav = meetings.assign(
        won=np.where(meetings["expected"] >= 0.5, meetings["won"], 1 - meetings["won"]),
        expected=np.maximum(meetings["expected"], 1 - meetings["expected"]),
    )
    fav = fav.assign(excess=fav["won"] - fav["expected"])
    calibration = [
        _group(fav[(fav["expected"] >= lo) & (fav["expected"] < hi)], label)
        for label, lo, hi in FORM_BANDS
    ]
    leaders = _leader_view(meetings)
    seasoned = leaders[leaders["prior_n"] >= RIVALRY_MIN_PRIOR]
    rivalry = [
        _group(seasoned[seasoned["lead_share"] >= RIVALRY_LEAD], f"Won {RIVALRY_LEAD:.0%}+"),
        _group(
            seasoned[seasoned["lead_share"] < RIVALRY_LEAD],
            f"Won 50-{RIVALRY_LEAD:.0%}",
        ),
    ]
    leaders = leaders.assign(edge=leaders["lead_share"] - 0.5)
    tested = leaders[leaders["prior_n"] >= RIVALRY_MIN_PRIOR]
    close = fav[fav["is_close"]]
    other = fav[~fav["is_close"]]
    return {
        "slug": "rivalries",
        "meetings": len(meetings),
        "min_prior": RIVALRY_MIN_PRIOR,
        "form_prior": FORM_PRIOR,
        "form_scan": form_scan(meetings),
        "coin_flip_log_loss": round(float(np.log(2)), 4),
        "favourite": _group(fav, "Side in better form"),
        "calibration": calibration,
        "rivalry": rivalry,
        "edge_per_10": _ci(bootstrap_slope(tested, "edge", "excess", 10), 3)
        if len(tested) >= MIN_SLOPE_MEETINGS
        else None,
        "close_share": round(100 * float(fav["is_close"].mean()), 1),
        "favourites": [_group(close, "Close finishes"), _group(other, "All other results")],
        "persistence": _persistence(sides),
    }


# --------------------------------------------------------------------------- output


def _names(serving: Path) -> dict[str, str]:
    con = duckdb.connect(str(serving), read_only=True)
    try:
        return dict(
            con.execute("SELECT player_id, coalesce(full_name, name) FROM players").fetchall()
        )
    finally:
        con.close()


def notes(serving: Path) -> dict[str, dict[str, Any]]:
    balls = load_lab_balls(serving)
    states = load_states(serving)
    return {
        "momentum": momentum_note(balls, states),
        "pressure": pressure_note(balls, top_moments(serving), swing_check(serving)),
        "clutch": clutch_note(balls, _names(serving)),
    } | ({"rivalries": rivalries_note(load_team_matches(serving))} if _has_teams(serving) else {})


def _has_teams(serving: Path) -> bool:
    con = duckdb.connect(str(serving), read_only=True)
    try:
        return bool(
            con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name = 'team_matches'"
            ).fetchone()[0]  # type: ignore[index]
        )
    finally:
        con.close()


def write_all(serving: Path, out_dir: Path = LAB_DIR) -> list[Path]:
    con = duckdb.connect(str(serving), read_only=True)
    try:
        columns = {
            c
            for (c,) in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'wp_predictions'"
            ).fetchall()
        }
        version = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
    finally:
        con.close()
    if "pressure" not in columns:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, note in notes(serving).items():
        note["data_version"] = version[0] if version else "unknown"
        path = out_dir / f"{slug}.json"
        path.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written
