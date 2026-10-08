"""Leak-free match states of Test cricket.

One row describes a Test *after* a delivery, plus one row per innings before
its first ball (``seq_no = 0``). Rows combine:

* **Match state**, known at that moment: the batting side's lead (negative
  while behind), wickets in hand, the innings so far, the last ten overs, and
  the time left. Cricsheet records no sessions or times of day, so the time
  left is estimated as five days of 90 overs less the overs bowled
  (:data:`SCHEDULED_OVERS`). It ignores time lost to rain, bad light and the
  breaks between innings, so it overstates what is left: drawn Tests in the
  data averaged 361 overs, not 450.
* **Context known before the match**, from earlier Tests only (strictly smaller
  ``match_order``): the scoring era (runs per wicket and per over over the
  previous Tests), each side's rating from its results (Elo style), whether a
  side is at home, and the XIs' Test records (shrunk batting averages and
  bowling strike rates). Matches are processed in order and history is updated
  only after a match's rows are built, so no row sees its own match's result.

Labels are the batting side's result: 2 won, 1 drawn, 0 lost. Ties and awarded
matches have none.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import numpy.typing as npt
import pandas as pd
import yaml

from criciq_core import paths
from criciq_ml.data import check_formats

# Five days of 90 overs: the time a Test is scheduled for, in overs.
SCHEDULED_OVERS = 450
BALLS_PER_OVER = 6
# The batting side's result.
LOST, DRAWN, WON = 0, 1, 2
LABEL = "label"
KEY_COLUMNS = ["match_id", "innings_no", "seq_no", "match_order", "season", "year"]
# Columns that describe how a match ended: never features.
FORBIDDEN = {"label", "outcome_type", "winner_id", "final_runs"}
# The last ten overs of an innings, in legal balls.
RECENT_BALLS = 60
# Decimals kept by derived ratios, so equal values stay equal on every CPU.
STABLE_DECIMALS = 9

MATCHES_SQL = """
SELECT m.match_id, m.match_order, s.year AS season, year(m.match_date)::INTEGER AS year,
       m.match_date, m.competition_id, v.country AS venue_country,
       m.team1_id, m.team2_id, t1.franchise_id AS side1, t2.franchise_id AS side2,
       m.outcome_type, m.winner_id, m.win_method
FROM matches m
JOIN seasons s USING (season_id)
JOIN venues v USING (venue_id)
JOIN team_seasons t1 ON t1.team_season_id = m.team1_id
JOIN team_seasons t2 ON t2.team_season_id = m.team2_id
ORDER BY m.match_order
"""

INNINGS_SQL = """
SELECT i.match_id, i.innings_no, i.batting_team_id, i.bowling_team_id, i.runs, i.wickets,
       i.legal_balls, i.declared, i.follow_on, i.forfeited
FROM innings i JOIN matches m USING (match_id)
WHERE NOT i.is_super_over
ORDER BY m.match_order, i.innings_no
"""

DELIVERIES_SQL = """
WITH outs AS (
    SELECT match_id, innings_no, seq_no,
           list(player_out_id ORDER BY wicket_no) FILTER (WHERE is_dismissal) AS out_ids,
           count(*) FILTER (WHERE bowler_credited) AS bowler_wickets
    FROM wickets GROUP BY ALL
)
SELECT d.match_id, d.innings_no, d.seq_no, d.legal_ball_no, d.is_legal,
       d.batter_id, d.non_striker_id, d.bowler_id, d.runs_batter, d.runs_total,
       d.extras_wides, d.extras_noballs, d.team_runs, d.team_wickets,
       coalesce(o.out_ids, []::VARCHAR[]) AS out_ids,
       coalesce(o.bowler_wickets, 0)::INTEGER AS bowler_wickets
FROM deliveries d
JOIN matches m USING (match_id)
JOIN innings i USING (match_id, innings_no)
LEFT JOIN outs o USING (match_id, innings_no, seq_no)
WHERE NOT i.is_super_over
ORDER BY m.match_order, d.innings_no, d.seq_no
"""

SQUADS_SQL = """
SELECT match_id, team_season_id, player_id
FROM match_players WHERE selection = 'playing_xi'
ORDER BY match_id, team_season_id, list_position
"""


@dataclass(frozen=True)
class TestInputs:
    __test__ = False  # not a pytest test class

    matches: pd.DataFrame
    innings: pd.DataFrame
    deliveries: pd.DataFrame
    squads: pd.DataFrame
    data_version: str

    def up_to(self, match_order: int) -> TestInputs:
        """History as it stood after ``match_order`` (later matches removed)."""
        kept = self.matches[self.matches["match_order"] <= match_order]
        ids = set(kept["match_id"])
        return TestInputs(
            matches=kept,
            innings=self.innings[self.innings["match_id"].isin(ids)],
            deliveries=self.deliveries[self.deliveries["match_id"].isin(ids)],
            squads=self.squads[self.squads["match_id"].isin(ids)],
            data_version=self.data_version,
        )


def load_test_inputs(database: Path) -> TestInputs:
    """The Test copy of the warehouse (or a Test serving database)."""
    con = duckdb.connect(str(database), read_only=True)
    try:
        check_formats(con)
        version = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
        return TestInputs(
            matches=con.execute(MATCHES_SQL).df(),
            innings=con.execute(INNINGS_SQL).df(),
            deliveries=con.execute(DELIVERIES_SQL).df(),
            squads=con.execute(SQUADS_SQL).df(),
            data_version=str(version[0]) if version else "unknown",
        )
    finally:
        con.close()


# ---------------------------------------------------------------- settings


@dataclass(frozen=True)
class TestFeatureConfig:
    """History settings (``features`` in config/models/test/win_probability.yaml)."""

    __test__ = False  # not a pytest test class

    # Previous Tests the scoring era is measured over.
    env_window_matches: int = 40
    # Shrinkage towards the era's average: dismissals for a batting average, wickets
    # for a bowling strike rate.
    bat_prior_outs: float = 6.0
    bowl_prior_wickets: float = 8.0
    # History is down-weighted by this much per Test the player plays.
    player_decay: float = 0.98
    # Elo-style side ratings: points moved by a full surprise, the home side's edge.
    elo_k: float = 24.0
    elo_home: float = 60.0
    # Batters counted in an XI's batting strength, bowlers in its bowling strength.
    xi_batters: int = 7
    xi_bowlers: int = 5

    @classmethod
    def of(cls, settings: dict[str, Any] | None) -> TestFeatureConfig:
        return cls(**(settings or {}))


# Before any history: a Test era of 32 runs per wicket and 3.2 runs per over.
INITIAL_RPW = 32.0
INITIAL_RPO = 3.2
INITIAL_ELO = 1500.0
# A bowler is a bowler once they have bowled this many legal balls in Tests.
BOWLER_MIN_BALLS = 300


# ---------------------------------------------------------------- history


@dataclass
class _Player:
    bat_runs: float = 0.0
    bat_outs: float = 0.0
    bowl_balls: float = 0.0
    bowl_wickets: float = 0.0


@dataclass
class _Era:
    window: int
    recent: deque[tuple[int, int, int]] = field(default_factory=deque)  # runs, wickets, balls

    def rates(self) -> tuple[float, float]:
        """Runs per wicket and runs per over over the previous Tests."""
        runs = sum(r for r, _, _ in self.recent)
        wickets = sum(w for _, w, _ in self.recent)
        balls = sum(b for _, _, b in self.recent)
        if balls < 20_000:
            return INITIAL_RPW, INITIAL_RPO
        return runs / max(wickets, 1), runs * BALLS_PER_OVER / balls

    def add(self, runs: int, wickets: int, balls: int) -> None:
        self.recent.append((runs, wickets, balls))
        while len(self.recent) > self.window:
            self.recent.popleft()


@cache
def home_countries() -> dict[str, frozenset[str]]:
    """Each national side's home countries (config/teams/national.yaml)."""
    with (paths.config_dir() / "teams" / "national.yaml").open(encoding="utf-8") as fh:
        teams = yaml.safe_load(fh)["teams"]
    return {
        str(t["id"]): frozenset([str(t["name"]), *map(str, t.get("home_countries", []))])
        for t in teams
    }


def _at_home(side: str, country: str | None) -> bool:
    return country is not None and country in home_countries().get(side, frozenset())


def _bat_idx(p: _Player | None, rpw: float, cfg: TestFeatureConfig) -> float:
    """A shrunk batting average as a share of the era's runs per wicket (1 = average)."""
    p = p or _Player()
    prior = cfg.bat_prior_outs
    return (p.bat_runs + prior * rpw) / (p.bat_outs + prior) / rpw


def _bowl_idx(p: _Player | None, era_sr: float, cfg: TestFeatureConfig) -> float:
    """A shrunk bowling strike rate against the era's balls per wicket (1 = average,
    above 1 takes wickets faster)."""
    p = p or _Player()
    prior = cfg.bowl_prior_wickets
    strike = (p.bowl_balls + prior * era_sr) / (p.bowl_wickets + prior)
    return era_sr / strike


@dataclass(frozen=True)
class _SideContext:
    elo: float
    home: bool
    bat_xi: float
    bowl_xi: float
    bat_idx: dict[str, float]


def _side_context(
    side: str,
    country: str | None,
    xi: list[str],
    players: dict[str, _Player],
    elo: dict[str, float],
    rates: tuple[float, float],
    cfg: TestFeatureConfig,
) -> _SideContext:
    rpw, rpo = rates
    era_sr = rpw * BALLS_PER_OVER / rpo
    bat = {p: _bat_idx(players.get(p), rpw, cfg) for p in xi}
    # The bowlers: the XI's most experienced, by Test balls bowled.
    by_balls = sorted(xi, key=lambda p: -(players.get(p) or _Player()).bowl_balls)
    bowlers = [
        _bowl_idx(players.get(p), era_sr, cfg)
        if (players.get(p) or _Player()).bowl_balls >= BOWLER_MIN_BALLS
        else 0.85  # an unproven bowler is assumed below average
        for p in by_balls[: cfg.xi_bowlers]
    ]
    return _SideContext(
        elo=elo.get(side, INITIAL_ELO),
        home=_at_home(side, country),
        bat_xi=float(sum(sorted(bat.values(), reverse=True)[: cfg.xi_batters])),
        bowl_xi=float(np.mean(bowlers)) if bowlers else 0.85,
        bat_idx=bat,
    )


def _update(
    match: Any,
    dels: pd.DataFrame,
    players: dict[str, _Player],
    elo: dict[str, float],
    era: _Era,
    cfg: TestFeatureConfig,
) -> None:
    """Add a finished match to the history."""
    seen = set(dels["batter_id"]) | set(dels["bowler_id"])
    for player in seen:
        p = players.setdefault(player, _Player())
        p.bat_runs *= cfg.player_decay
        p.bat_outs *= cfg.player_decay
        p.bowl_balls *= cfg.player_decay
        p.bowl_wickets *= cfg.player_decay
    faced = dels[dels["extras_wides"] == 0]
    for player, runs in faced.groupby("batter_id")["runs_batter"].sum().items():
        players[str(player)].bat_runs += float(runs)
    for ids in dels["out_ids"]:
        for player in ids:
            players.setdefault(str(player), _Player()).bat_outs += 1.0
    legal = dels[dels["is_legal"]]
    for player, balls in legal.groupby("bowler_id").size().items():
        players[str(player)].bowl_balls += float(balls)
    for player, wickets in dels.groupby("bowler_id")["bowler_wickets"].sum().items():
        players[str(player)].bowl_wickets += float(wickets)
    era.add(
        int(dels["runs_total"].sum()),
        int(sum(len(ids) for ids in dels["out_ids"])),
        int(dels["is_legal"].sum()),
    )
    # Side ratings: a win scores 1, a draw a half.
    if match.outcome_type not in ("win", "draw") or match.win_method == "Awarded":
        return
    a, b = str(match.side1), str(match.side2)
    ra = elo.get(a, INITIAL_ELO) + cfg.elo_home * _at_home(a, match.venue_country)
    rb = elo.get(b, INITIAL_ELO) + cfg.elo_home * _at_home(b, match.venue_country)
    expected = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
    if match.outcome_type == "draw":
        score = 0.5
    else:
        score = 1.0 if match.winner_id == match.team1_id else 0.0
    elo[a] = elo.get(a, INITIAL_ELO) + cfg.elo_k * (score - expected)
    elo[b] = elo.get(b, INITIAL_ELO) - cfg.elo_k * (score - expected)


# ---------------------------------------------------------------- per-match rows


def _label(match: Any, batting_team: str) -> float:
    if match.win_method == "Awarded" or match.outcome_type not in ("win", "draw"):
        return float("nan")
    if match.outcome_type == "draw":
        return float(DRAWN)
    return float(WON if match.winner_id == batting_team else LOST)


def _match_rows(
    match: Any,
    inns: pd.DataFrame,
    dels: pd.DataFrame,
    sides: dict[str, _SideContext],
    rates: tuple[float, float],
) -> pd.DataFrame:
    """Every state of one match: each innings' start, then each ball."""
    rpw, rpo = rates
    team_a = str(inns.iloc[0]["batting_team_id"]) if len(inns) else str(match.team1_id)
    frames = []
    totals: dict[str, int] = defaultdict(int)
    balls_before = 0
    for inn in inns.itertuples(index=False):
        number = int(inn.innings_no)
        batting, bowling = str(inn.batting_team_id), str(inn.bowling_team_id)
        d = dels[dels["innings_no"] == number]
        start = pd.DataFrame(
            {
                "seq_no": [0],
                "team_runs": [0],
                "team_wickets": [0],
                "legal_ball_no": [0],
                "runs_total": [0],
                "is_legal": [False],
                "out_ids": [[]],
            }
        )
        cols = ["seq_no", "team_runs", "team_wickets", "legal_ball_no", "runs_total", "is_legal"]
        rows = pd.concat([start, d[[*cols, "out_ids"]]], ignore_index=True)
        own, opp = totals[batting], totals[bowling]
        runs = rows["team_runs"].to_numpy(dtype=np.int64)
        wickets = rows["team_wickets"].to_numpy(dtype=np.int64)
        legal = rows["legal_ball_no"].to_numpy(dtype=np.int64)
        match_balls = balls_before + legal
        overs_left = np.maximum(SCHEDULED_OVERS - match_balls / BALLS_PER_OVER, 0.0)
        lead = own + runs - opp
        needed = np.where(number == 4, np.maximum(opp - own + 1 - runs, 0), 0)
        # The last ten overs, by legal balls: runs and wickets since then.
        recent_runs, recent_wickets = _recent(runs, wickets, legal)
        bat_idx = sides[batting].bat_idx
        out_idx = np.array(
            [sum(bat_idx.get(str(p), 1.0) for p in ids) for ids in rows["out_ids"]], dtype=float
        )
        # A substitute dismissed in place of an XI player can take it just below zero.
        bat_left = np.maximum(sum(bat_idx.values()) - np.cumsum(out_idx), 0.0)
        frame = pd.DataFrame(
            {
                "match_id": int(match.match_id),
                "innings_no": number,
                "seq_no": rows["seq_no"].to_numpy(dtype=np.int64),
                "match_order": int(match.match_order),
                "season": int(match.season),
                "year": int(match.year),
                "competition_id": str(match.competition_id),
                "batting_team_id": batting,
                "batted_first": float(batting == team_a),
                "runs": runs,
                "wickets": wickets,
                "legal_balls": legal,
                "wickets_in_hand": 10 - wickets,
                "lead": lead,
                "overs_left": overs_left,
                "match_overs": match_balls / BALLS_PER_OVER,
                "innings_rpo": runs * BALLS_PER_OVER / np.maximum(legal, 1),
                "runs_last_10": recent_runs,
                "wickets_last_10": recent_wickets,
                "runs_needed": needed,
                "required_rpo": np.where(number == 4, needed / np.maximum(overs_left, 1.0), 0.0),
                "follow_on": float(bool(inn.follow_on)),
                "env_rpw": rpw,
                "env_rpo": rpo,
                "elo_diff": sides[batting].elo - sides[bowling].elo,
                "home": float(sides[batting].home) - float(sides[bowling].home),
                "bat_xi_own": sides[batting].bat_xi,
                "bat_xi_opp": sides[bowling].bat_xi,
                "bowl_xi_own": sides[batting].bowl_xi,
                "bowl_xi_opp": sides[bowling].bowl_xi,
                "bat_left": bat_left,
                LABEL: _label(match, batting),
            }
        )
        frames.append(frame)
        totals[batting] += int(inn.runs)
        balls_before += int(inn.legal_balls)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _recent(
    runs: np.ndarray, wickets: np.ndarray, legal: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Runs and wickets over the last RECENT_BALLS legal balls of the innings."""
    # The state when the innings had RECENT_BALLS fewer legal balls: the last row
    # with legal <= legal - RECENT_BALLS (rows are in order, legal is non-decreasing).
    earlier = np.searchsorted(legal, legal - RECENT_BALLS, side="right") - 1
    before_runs = np.where(earlier >= 0, runs[np.maximum(earlier, 0)], 0)
    before_wickets = np.where(earlier >= 0, wickets[np.maximum(earlier, 0)], 0)
    return runs - before_runs, wickets - before_wickets


# Ratios computed with floating-point maths, rounded so every CPU agrees.
STABLE_COLUMNS = (
    "overs_left",
    "match_overs",
    "innings_rpo",
    "required_rpo",
    "env_rpw",
    "env_rpo",
    "elo_diff",
    "bat_xi_own",
    "bat_xi_opp",
    "bowl_xi_own",
    "bowl_xi_opp",
    "bat_left",
)


def build_states(inputs: TestInputs, cfg: TestFeatureConfig | None = None) -> pd.DataFrame:
    """Every state of every Test, with its features and label."""
    cfg = cfg or TestFeatureConfig()
    players: dict[str, _Player] = {}
    elo: dict[str, float] = {}
    era = _Era(cfg.env_window_matches)
    deliveries = {mid: df for mid, df in inputs.deliveries.groupby("match_id", sort=False)}
    innings = {mid: df for mid, df in inputs.innings.groupby("match_id", sort=False)}
    squads = {
        mid: df.groupby("team_season_id")["player_id"].apply(list).to_dict()
        for mid, df in inputs.squads.groupby("match_id", sort=False)
    }
    frames = []
    for match in inputs.matches.sort_values("match_order").itertuples(index=False):
        mid = int(match.match_id)
        dels, inns = deliveries.get(mid), innings.get(mid)
        if dels is None or inns is None:
            continue
        rates = era.rates()
        xis = squads.get(mid, {})
        sides = {
            str(team): _side_context(
                str(side),
                match.venue_country,
                [str(p) for p in xis.get(team, [])],
                players,
                elo,
                rates,
                cfg,
            )
            for team, side in ((match.team1_id, match.side1), (match.team2_id, match.side2))
        }
        frames.append(_match_rows(match, inns, dels, sides, rates))
        _update(match, dels, players, elo, era, cfg)
    frame = pd.concat(frames, ignore_index=True)
    for column in STABLE_COLUMNS:
        frame[column] = frame[column].astype(float).round(STABLE_DECIMALS)
    return frame.sort_values(["match_order", "innings_no", "seq_no"]).reset_index(drop=True)


def context_now(inputs: TestInputs, cfg: TestFeatureConfig | None = None) -> dict[str, Any]:
    """The pre-match context after the last Test: each side's rating and the scoring era
    (for a chase calculated from scratch, between any two sides)."""
    cfg = cfg or TestFeatureConfig()
    players: dict[str, _Player] = {}
    elo: dict[str, float] = {}
    era = _Era(cfg.env_window_matches)
    deliveries = {mid: df for mid, df in inputs.deliveries.groupby("match_id", sort=False)}
    last = None
    for match in inputs.matches.sort_values("match_order").itertuples(index=False):
        dels = deliveries.get(int(match.match_id))
        if dels is None:
            continue
        _update(match, dels, players, elo, era, cfg)
        last = match.match_date
    rpw, rpo = era.rates()
    return {
        "ratings": {side: round(rating, 1) for side, rating in sorted(elo.items())},
        "env_rpw": round(rpw, 4),
        "env_rpo": round(rpo, 4),
        "as_of": None if last is None else str(pd.Timestamp(last).date()),
    }


def final_rows(states: pd.DataFrame) -> npt.NDArray[np.bool_]:
    """Whether each row is its match's last state (where the result is settled)."""
    last_innings = states.groupby("match_id")["innings_no"].transform("max")
    last_seq = states.groupby(["match_id", "innings_no"])["seq_no"].transform("max")
    last = (states["innings_no"] == last_innings) & (states["seq_no"] == last_seq)
    return np.asarray(last.to_numpy(), dtype=bool)
