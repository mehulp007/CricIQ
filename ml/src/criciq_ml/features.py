"""Leak-free match-state features for the win probability model.

One row describes the match *after* a delivery (plus one row per innings
before its first ball, ``seq_no = 0``). Rows combine:

* **Match state**: score, wickets, balls, the chase equation and the last two
  overs, all known at that moment.
* **As-of context**: player, venue and scoring-era strength computed only from
  matches played *earlier* (strictly smaller ``match_order``). Matches are
  processed in order and history is updated only after a match's rows are
  emitted, so no row can see its own match's result or any later match.

Team identity is deliberately not a feature: squads turn over every season.
Player strength enters through the actual XI's records instead.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from criciq_ml import chase
from criciq_ml.data import Inputs

# ---------------------------------------------------------------- feature sets

# The served model: match state plus the scoring era. Every candidate below was
# built leak-free and tested; none improved out-of-sample predictions, so they
# stay out (the evaluation re-runs that test on every training run).
FEATURES: dict[int, list[str]] = {
    1: ["legal_balls", "runs", "wickets", "runs_vs_par", "runs_last_12", "wickets_last_12"],
    2: [
        "legal_balls",
        "balls_remaining",
        "runs_needed",
        "wickets",
        "required_rate",
        "chase_ratio",
        "required_rate_rel",
        "chase_dp",
        "runs_last_12",
        "wickets_last_12",
    ],
}

# Candidate context features, tested by adding each group to the served set.
CANDIDATES: dict[str, dict[int, list[str]]] = {
    "crease": {
        1: ["crease_sr_idx", "crease_avg_idx", "crease_balls"],
        2: ["crease_sr_idx", "crease_avg_idx", "crease_balls"],
    },
    "depth": {1: ["depth_avg_sum"], 2: ["depth_avg_sum"]},
    "bowling": {1: ["bowl_left_econ_idx"], 2: ["bowl_left_econ_idx"]},
    "squads": {1: ["opp_bat_strength", "own_bowl_strength"], 2: []},
    "venue": {1: ["venue_idx"], 2: ["venue_idx"]},
    "target_size": {1: [], 2: ["target_vs_par"]},
}

# Match state only, without the era adjustment (ablation).
STATE_FEATURES: dict[int, list[str]] = {
    1: ["legal_balls", "runs", "wickets", "runs_last_12", "wickets_last_12"],
    2: [
        "legal_balls",
        "balls_remaining",
        "runs_needed",
        "wickets",
        "required_rate",
        "runs_last_12",
        "wickets_last_12",
    ],
}

# Cricket common sense the model must respect: +1 = more is better for the batting side.
MONOTONE: dict[int, dict[str, int]] = {
    1: {"runs": 1, "wickets": -1, "legal_balls": -1, "runs_vs_par": 1},
    2: {
        "legal_balls": -1,
        "runs_needed": -1,
        "wickets": -1,
        "balls_remaining": 1,
        "required_rate": -1,
        "chase_ratio": -1,
        "required_rate_rel": -1,
        "chase_dp": 1,
    },
}

# Fan-level concepts used to explain a prediction. Every served feature belongs to one.
GROUPS: dict[str, dict[int, list[str]]] = {
    "situation": {
        1: ["legal_balls", "runs", "runs_vs_par"],
        2: [
            "legal_balls",
            "balls_remaining",
            "runs_needed",
            "required_rate",
            "chase_ratio",
            "required_rate_rel",
            "chase_dp",
        ],
    },
    "wickets": {1: ["wickets"], 2: ["wickets"]},
    "recent": {1: ["runs_last_12", "wickets_last_12"], 2: ["runs_last_12", "wickets_last_12"]},
}
GROUP_KEYS = list(GROUPS)

KEY_COLUMNS = ["match_id", "innings_no", "seq_no", "match_order", "season"]
LABEL = "label"

# Columns that describe how a match *ended*. They must never be features.
FORBIDDEN = {"winner_id", "outcome_type", "label", "final_runs", "final_wickets", "result"}


@dataclass(frozen=True)
class FeatureConfig:
    """Shrinkage and memory settings (see config/models/win_probability.yaml)."""

    bat_prior_balls: float = 100.0
    bowl_prior_balls: float = 120.0
    venue_prior_balls: float = 1_500.0
    player_decay: float = 0.97
    env_window_matches: int = 60
    # Prior run environment before any history exists (7.8 runs an over).
    initial_rpb: float = 1.30


# ---------------------------------------------------------------- history


@dataclass
class _PlayerHistory:
    bat_runs: float = 0.0
    bat_balls: float = 0.0
    bat_outs: float = 0.0
    bowl_runs: float = 0.0
    bowl_balls: float = 0.0


@dataclass
class _MatchTotals:
    runs: int = 0
    legal_balls: int = 0
    bat_runs: int = 0
    bat_balls: int = 0
    outs: int = 0
    bowl_runs: int = 0
    bowl_balls: int = 0


@dataclass
class _League:
    """Rolling league averages over the most recent matches (the scoring era)."""

    window: int
    initial_rpb: float
    recent: deque[_MatchTotals] = field(default_factory=deque)

    def _sum(self, attr: str) -> float:
        return float(sum(getattr(m, attr) for m in self.recent))

    def rates(self) -> dict[str, float]:
        balls = self._sum("legal_balls")
        if balls < 1_000:
            rpb = self.initial_rpb
            return {
                "rpb": rpb,
                "bat_rpb": rpb * 0.94,
                "out_rate": 0.052,
                "bowl_rpb": rpb * 0.98,
            }
        return {
            "rpb": self._sum("runs") / balls,
            "bat_rpb": self._sum("bat_runs") / max(self._sum("bat_balls"), 1.0),
            "out_rate": self._sum("outs") / max(self._sum("bat_balls"), 1.0),
            "bowl_rpb": self._sum("bowl_runs") / max(self._sum("bowl_balls"), 1.0),
        }

    def add(self, totals: _MatchTotals) -> None:
        self.recent.append(totals)
        while len(self.recent) > self.window:
            self.recent.popleft()


@dataclass(frozen=True)
class _PlayerRatings:
    sr_idx: float  # shrunk runs per ball / league
    avg_idx: float  # shrunk runs per dismissal / league
    econ_idx: float  # shrunk runs conceded per legal ball / league (lower is better)
    bowl_balls: float  # decayed legal balls bowled (experience as a bowler)


def _ratings(
    h: _PlayerHistory | None, league: dict[str, float], cfg: FeatureConfig
) -> _PlayerRatings:
    h = h or _PlayerHistory()
    kb, kw = cfg.bat_prior_balls, cfg.bowl_prior_balls
    rpb = (h.bat_runs + kb * league["bat_rpb"]) / (h.bat_balls + kb)
    avg = (h.bat_runs + kb * league["bat_rpb"]) / (h.bat_outs + kb * league["out_rate"])
    econ = (h.bowl_runs + kw * league["bowl_rpb"]) / (h.bowl_balls + kw)
    league_avg = league["bat_rpb"] / league["out_rate"]
    return _PlayerRatings(
        sr_idx=rpb / league["bat_rpb"],
        avg_idx=avg / league_avg,
        econ_idx=econ / league["bowl_rpb"],
        bowl_balls=h.bowl_balls,
    )


# ---------------------------------------------------------------- per-innings state


def _bowler_quota(max_balls: int, balls_per_over: int) -> int:
    """Legal balls one bowler may bowl: a fifth of the overs, rounded up."""
    overs = math.ceil(max_balls / balls_per_over)
    return math.ceil(overs / 5) * balls_per_over


def _bowling_left(
    pool: Iterable[str],
    ratings: dict[str, _PlayerRatings],
    bowled: dict[str, int],
    balls_left: int,
    quota: int,
) -> float:
    """Average economy index of the balls still to come, best bowlers first.

    Assumes the fielding captain uses their best remaining options up to each
    bowler's quota; overs nobody is known to be able to bowl count as average.
    """
    if balls_left <= 0:
        return float("nan")
    options = sorted(
        (ratings[p].econ_idx, quota - bowled.get(p, 0))
        for p in pool
        if ratings[p].bowl_balls >= 30 or bowled.get(p, 0) > 0
    )
    need, total = balls_left, 0.0
    for econ, available in options:
        if need <= 0:
            break
        take = min(max(available, 0), need)
        total += econ * take
        need -= take
    total += 1.0 * need
    return total / balls_left


def _top(values: Iterable[float], k: int, *, reverse: bool = True) -> list[float]:
    return sorted(values, reverse=reverse)[:k]


class _Squads:
    """Who is available to each side, applying substitutions as they happen."""

    def __init__(self, squad_rows: pd.DataFrame, subs: pd.DataFrame) -> None:
        self._base: dict[str, list[str]] = defaultdict(list)
        for team, player, selection in squad_rows[
            ["team_season_id", "player_id", "selection"]
        ].itertuples(index=False):
            if selection == "playing_xi":
                self._base[team].append(player)
        self._subs = [
            ((int(r.innings_no), int(r.seq_no)), r.team_season_id, r.player_in_id, r.player_out_id)
            for r in subs.itertuples(index=False)
        ]

    def members(self, team: str, at: tuple[int, int]) -> list[str]:
        players = list(self._base[team])
        for key, sub_team, player_in, player_out in self._subs:
            if sub_team != team or key > at:
                continue
            if player_out in players:
                players.remove(player_out)
            if player_in not in players:
                players.append(player_in)
        return players

    def all_players(self) -> set[str]:
        players = {p for members in self._base.values() for p in members}
        players.update(p for _, _, p, _ in self._subs)
        return players


# ---------------------------------------------------------------- builder


def build_states(inputs: Inputs, cfg: FeatureConfig | None = None) -> pd.DataFrame:
    """Every match state of every main innings (super overs excluded), with features."""
    cfg = cfg or FeatureConfig()
    players: dict[str, _PlayerHistory] = {}
    venues: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # runs, expected runs
    league = _League(window=cfg.env_window_matches, initial_rpb=cfg.initial_rpb)
    rows: list[dict[str, Any]] = []

    deliveries = {mid: df for mid, df in inputs.deliveries.groupby("match_id", sort=False)}
    innings = {mid: df for mid, df in inputs.innings.groupby("match_id", sort=False)}
    squads = {mid: df for mid, df in inputs.squads.groupby("match_id", sort=False)}
    subs = {mid: df for mid, df in inputs.substitutions.groupby("match_id", sort=False)}
    empty_subs = inputs.substitutions.iloc[0:0]
    season_of = inputs.matches.set_index("match_id")["season"]
    tables = chase.SeasonTables(inputs.deliveries, inputs.deliveries["match_id"].map(season_of))

    for match in inputs.matches.sort_values("match_order").itertuples(index=False):
        mid = int(match.match_id)
        rates = league.rates()
        venue_runs, venue_expected = venues[match.venue_id]
        venue_idx = (venue_runs + cfg.venue_prior_balls * rates["rpb"]) / (
            venue_expected + cfg.venue_prior_balls * rates["rpb"]
        )
        match_squads = _Squads(squads.get(mid, inputs.squads.iloc[0:0]), subs.get(mid, empty_subs))
        match_dels = deliveries.get(mid)
        match_inns = innings.get(mid)
        if match_dels is None or match_inns is None:
            continue

        seen = (
            match_squads.all_players()
            | set(match_dels["batter_id"])
            | set(match_dels["non_striker_id"])
            | set(match_dels["bowler_id"])
        )
        ratings = {p: _ratings(players.get(p), rates, cfg) for p in seen}
        label_for = _labeller(match)

        for inn in match_inns.itertuples(index=False):
            if inn.is_super_over or inn.innings_no > 2:
                continue
            inn_dels = match_dels[match_dels["innings_no"] == inn.innings_no]
            if inn_dels.empty:
                continue
            context = {
                "match_id": mid,
                "innings_no": int(inn.innings_no),
                "match_order": int(match.match_order),
                "season": int(match.season),
                "venue_idx": venue_idx,
                "dp_table": tables.for_season(int(match.season)) if inn.innings_no == 2 else None,
                "env_rpb": rates["rpb"],
                LABEL: label_for(inn.batting_team_id),
            }
            rows.extend(
                _innings_rows(
                    inn, inn_dels, context, match_squads, ratings, rates, int(match.balls_per_over)
                )
            )

        _update_history(match_dels, match_inns, venues[match.venue_id], players, league, rates, cfg)

    frame = pd.DataFrame(rows)
    return frame.sort_values(["match_order", "innings_no", "seq_no"]).reset_index(drop=True)


def _labeller(match: Any) -> Any:
    def label(batting_team: str) -> float:
        if match.outcome_type == "tie":
            return 0.5
        if match.outcome_type == "win":
            return 1.0 if match.winner_id == batting_team else 0.0
        return float("nan")  # no result: kept for scoring, never trained on

    return label


def _innings_rows(
    inn: Any,
    dels: pd.DataFrame,
    context: dict[str, Any],
    squads: _Squads,
    ratings: dict[str, _PlayerRatings],
    rates: dict[str, float],
    balls_per_over: int,
) -> list[dict[str, Any]]:
    inn_no = int(inn.innings_no)
    dp_table = context.pop("dp_table")
    max_balls = int(inn.max_balls)
    target = None if pd.isna(inn.target_runs) else int(inn.target_runs)
    quota = _bowler_quota(max_balls, balls_per_over)
    records = dels.to_dict("records")

    opp = squads.members(inn.bowling_team_id, (inn_no, 0))
    own = squads.members(inn.batting_team_id, (inn_no, 0))
    opp_bat_strength = sum(_top((min(ratings[p].avg_idx, 2.0) for p in opp), 7))
    own_bowl = [ratings[p] for p in own]
    own_bowl_strength = float(
        np.mean([r.econ_idx for r in sorted(own_bowl, key=lambda r: -r.bowl_balls)[:5]] or [1.0])
    )

    appeared: set[str] = set()
    faced: dict[str, int] = defaultdict(int)
    out: set[str] = set()
    bowled: dict[str, int] = defaultdict(int)
    window: deque[tuple[int, int, int]] = deque()  # legal_ball_no, runs, wickets
    rows = []

    def row(seq_no: int, runs: int, wickets: int, legal: int, pair: tuple[str, str]) -> None:
        at = (inn_no, seq_no + 1)
        appeared.update(pair)
        batting = squads.members(inn.batting_team_id, at)
        bowling = squads.members(inn.bowling_team_id, at)
        yet_to_bat = [p for p in batting if p not in appeared and p not in out]
        crease = [ratings[p] for p in pair]
        balls_left = max(max_balls - legal, 0)
        state: dict[str, Any] = {
            **context,
            "seq_no": seq_no,
            "max_balls": max_balls,
            "legal_balls": legal,
            "balls_remaining": balls_left,
            "runs": runs,
            "wickets": wickets,
            "runs_last_12": sum(r for _, r, _ in window),
            "wickets_last_12": sum(w for _, _, w in window),
            "crease_sr_idx": float(np.mean([r.sr_idx for r in crease])),
            "crease_avg_idx": float(np.mean([r.avg_idx for r in crease])),
            "crease_balls": min(faced[pair[0]] + faced[pair[1]], 120),
            "depth_avg_sum": sum(min(ratings[p].avg_idx, 2.0) for p in yet_to_bat),
            "bowl_left_econ_idx": _bowling_left(bowling, ratings, bowled, balls_left, quota),
        }
        if inn_no == 1:
            state["opp_bat_strength"] = opp_bat_strength
            state["own_bowl_strength"] = own_bowl_strength
        else:
            assert target is not None, "second innings without a target"
            needed = max(target - runs, 0)
            state["target"] = target
            state["runs_needed"] = needed
            state["required_rate"] = (
                min(needed * balls_per_over / balls_left, 36.0) if balls_left else 36.0
            )
            state["chase_ratio"] = math.log1p(needed) - math.log1p(balls_left)
            state["required_rate_rel"] = state["required_rate"] / (balls_per_over * rates["rpb"])
            state["chase_dp"] = chase.lookup(dp_table, needed, balls_left, wickets)
            state["target_vs_par"] = target - rates["rpb"] * max_balls
        state["runs_vs_par"] = runs - rates["rpb"] * legal
        rows.append(state)

    first = records[0]
    row(0, 0, 0, 0, (first["batter_id"], first["non_striker_id"]))

    for i, d in enumerate(records):
        if not d["extras_wides"]:
            faced[d["batter_id"]] += 1
        if d["is_legal"]:
            bowled[d["bowler_id"]] += 1
        out.update(d["out_ids"])
        window.append((int(d["legal_ball_no"]), int(d["runs_total"]), len(d["out_ids"])))
        while window and window[0][0] <= d["legal_ball_no"] - 12:
            window.popleft()
        nxt = records[i + 1] if i + 1 < len(records) else None
        if nxt is not None:
            pair = (nxt["batter_id"], nxt["non_striker_id"])
        else:
            remaining = [p for p in (d["batter_id"], d["non_striker_id"]) if p not in out]
            remaining = remaining or [d["batter_id"]]
            pair = (remaining[0], remaining[-1])
        row(
            int(d["seq_no"]),
            int(d["team_runs"]),
            int(d["team_wickets"]),
            int(d["legal_ball_no"]),
            pair,
        )
    return rows


def _update_history(
    dels: pd.DataFrame,
    inns: pd.DataFrame,
    venue: list[float],
    players: dict[str, _PlayerHistory],
    league: _League,
    rates: dict[str, float],
    cfg: FeatureConfig,
) -> None:
    """Fold a finished match into player, venue and league history."""
    main = set(
        inns.loc[~inns["is_super_over"] & (inns["innings_no"] <= 2), "innings_no"].astype(int)
    )
    d = dels[dels["innings_no"].isin(main)]
    totals = _MatchTotals()
    per_player: dict[str, _PlayerHistory] = defaultdict(_PlayerHistory)
    for r in d.itertuples(index=False):
        conceded = int(r.runs_batter) + int(r.extras_wides) + int(r.extras_noballs)
        if not r.extras_wides:
            per_player[r.batter_id].bat_balls += 1
            totals.bat_balls += 1
        per_player[r.batter_id].bat_runs += r.runs_batter
        per_player[r.bowler_id].bowl_runs += conceded
        totals.bat_runs += int(r.runs_batter)
        totals.bowl_runs += conceded
        totals.runs += int(r.runs_total)
        if r.is_legal:
            per_player[r.bowler_id].bowl_balls += 1
            totals.legal_balls += 1
            totals.bowl_balls += 1
        for pid in r.out_ids:
            per_player[pid].bat_outs += 1
            totals.outs += 1

    for pid, stats in per_player.items():
        h = players.setdefault(pid, _PlayerHistory())
        for name in ("bat_runs", "bat_balls", "bat_outs", "bowl_runs", "bowl_balls"):
            setattr(h, name, getattr(h, name) * cfg.player_decay + getattr(stats, name))

    first = d[d["innings_no"] == 1]
    if 1 in main and not first.empty:
        # Venue strength: first-innings runs relative to what the era would expect.
        venue[0] += float(first["runs_total"].sum())
        venue[1] += rates["rpb"] * int(first["legal_ball_no"].max())
    league.add(totals)
