"""Playing-style profiles for similar players.

A profile is a handful of per-ball rates (against par where it matters) and
usage shares, standardised within the qualified players of a season window.
Two players are similar when their standardised profiles point the same way
(cosine similarity). Shared by the API and the evaluation in
``criciq_ml.ratings``, so the served method is exactly the one tested.

Plain Python on purpose: the API ships without numerical libraries.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from criciq_core.phases import default_phase_config
from criciq_core.ratings import MIN_BALLS, Role

# Candidates (and the population that defines "average") need MIN_BALLS in the
# window; a player needs MIN_PROFILE_BALLS for a profile of their own.
MIN_PROFILE_BALLS = 120
# A standardised feature this far from average is a trait worth naming.
TRAIT_Z = 0.75


@dataclass(frozen=True)
class StyleFeature:
    key: str
    label: str
    high: str  # trait when well above the average
    low: str  # trait when well below


BATTING_FEATURES: tuple[StyleFeature, ...] = (
    StyleFeature("scoring", "Strike rate vs par", "Scores fast", "Scores slowly"),
    StyleFeature("boundaries", "Boundary rate vs par", "Boundary hitter", "Few boundaries"),
    StyleFeature("dots", "Dot balls vs par", "Many dot balls", "Rotates the strike"),
    StyleFeature("dismissals", "Dismissal rate vs par", "Gets out often", "Hard to dismiss"),
    StyleFeature("six_share", "Sixes among boundaries", "Six hitter", "Hits mostly fours"),
    StyleFeature("powerplay", "Balls in the powerplay", "Powerplay batter", "Rarely bats early"),
    StyleFeature("death", "Balls at the death", "Finisher", "Rarely bats at the death"),
    StyleFeature("position", "Batting position", "Lower order", "Top order"),
)

BOWLING_FEATURES: tuple[StyleFeature, ...] = (
    StyleFeature("economy", "Runs saved per over", "Economical", "Expensive"),
    StyleFeature("dots", "Dot balls vs par", "Builds dot-ball pressure", "Few dot balls"),
    StyleFeature("boundaries", "Boundaries conceded vs par", "Concedes boundaries", "Hard to hit"),
    StyleFeature("powerplay", "Overs in the powerplay", "Powerplay bowler", "Rarely bowls early"),
    StyleFeature("death", "Overs at the death", "Death bowler", "Rarely bowls at the death"),
    StyleFeature("spin", "Spin (1) or pace (0)", "Spinner", "Pace bowler"),
    StyleFeature("workload", "Balls per innings", "Bowls a full quota", "Part-time bowler"),
    StyleFeature("extras", "Wides and no-balls", "Bowls extras", "Rarely bowls extras"),
)


def features(role: Role) -> tuple[StyleFeature, ...]:
    return BATTING_FEATURES if role == "batting" else BOWLING_FEATURES


def _edge_phases() -> tuple[str, str]:
    ordered = sorted(default_phase_config().for_format("T20").phases, key=lambda p: p.first_over)
    return ordered[0].key, ordered[-1].key


def profile_sql(role: Role) -> str:
    """Profiles of every player for seasons between ``?`` and ``?`` (``window_params``)."""
    first, last = _edge_phases()
    phases = f"""
        SELECT player_id,
               coalesce(sum(balls) FILTER (WHERE phase = '{first}'), 0) AS early_balls,
               coalesce(sum(balls) FILTER (WHERE phase = '{last}'), 0) AS late_balls
        FROM player_{role}_phases WHERE season BETWEEN ? AND ? GROUP BY player_id
    """
    if role == "batting":
        return f"""
            WITH inn AS (
                SELECT player_id, sum(balls) AS balls, sum(runs) AS runs,
                       sum(par_runs) AS par_runs, sum(fours + sixes) AS boundaries,
                       sum(par_boundaries) AS par_boundaries, sum(dots) AS dots,
                       sum(par_dots) AS par_dots, count(*) FILTER (WHERE is_out) AS outs,
                       sum(par_outs) AS par_outs, sum(sixes) AS sixes, avg(position) AS position
                FROM player_batting_innings WHERE season BETWEEN ? AND ? GROUP BY player_id
            ),
            ph AS ({phases})
            SELECT player_id, balls::INTEGER AS balls,
                   100 * (runs - par_runs) / balls AS scoring,
                   100 * (boundaries - par_boundaries) / balls AS boundaries,
                   100 * (dots - par_dots) / balls AS dots,
                   100 * (outs - par_outs) / balls AS dismissals,
                   sixes / greatest(boundaries, 1) AS six_share,
                   early_balls / balls AS powerplay,
                   late_balls / balls AS death,
                   position
            FROM inn JOIN ph USING (player_id)
            WHERE balls > 0
        """
    return f"""
        WITH inn AS (
            SELECT player_id, sum(balls) AS balls, sum(runs) AS runs, sum(par_runs) AS par_runs,
                   sum(dots) AS dots, sum(par_dots) AS par_dots,
                   sum(fours + sixes) AS boundaries, sum(par_boundaries) AS par_boundaries,
                   sum(wides + noballs) AS extras, count(*) AS innings
            FROM player_bowling_innings WHERE season BETWEEN ? AND ? GROUP BY player_id
        ),
        ph AS ({phases})
        SELECT player_id, balls::INTEGER AS balls,
               6 * (par_runs - runs) / balls AS economy,
               100 * (dots - par_dots) / balls AS dots,
               100 * (boundaries - par_boundaries) / balls AS boundaries,
               early_balls / balls AS powerplay,
               late_balls / balls AS death,
               CASE p.bowling_type WHEN 'spin' THEN 1.0 WHEN 'pace' THEN 0.0 ELSE 0.5 END AS spin,
               balls / innings AS workload,
               100 * extras / balls AS extras
        FROM inn JOIN ph USING (player_id) JOIN player_index p USING (player_id)
        WHERE balls > 0
    """


def window_params(first: int, last: int) -> list[int]:
    return [first, last, first, last]


@dataclass(frozen=True)
class Scaler:
    """Population mean and spread of each feature."""

    keys: tuple[str, ...]
    means: tuple[float, ...]
    sds: tuple[float, ...]

    @classmethod
    def fit(cls, rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> Scaler:
        means, sds = [], []
        for key in keys:
            values = [float(r[key]) for r in rows]
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / len(values)
            means.append(mean)
            sds.append(math.sqrt(var) or 1.0)
        return cls(tuple(keys), tuple(means), tuple(sds))

    def transform(self, row: Mapping[str, Any]) -> list[float]:
        return [
            (float(row[k]) - m) / s for k, m, s in zip(self.keys, self.means, self.sds, strict=True)
        ]


def cosine(u: Sequence[float], v: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(u, v, strict=True))
    norm = math.sqrt(sum(a * a for a in u)) * math.sqrt(sum(b * b for b in v))
    return dot / norm if norm else 0.0


def traits(z: Sequence[float], role: Role, limit: int = 3) -> list[str]:
    """The most distinctive traits of one standardised profile."""
    ranked = sorted(zip(features(role), z, strict=True), key=lambda fz: -abs(fz[1]))
    return [f.high if v > 0 else f.low for f, v in ranked[:limit] if abs(v) >= TRAIT_Z]


def shared_traits(u: Sequence[float], v: Sequence[float], role: Role, limit: int = 3) -> list[str]:
    """Traits two profiles share: both well away from average in the same direction."""
    shared = [
        (min(abs(a), abs(b)), f.high if a > 0 else f.low)
        for f, a, b in zip(features(role), u, v, strict=True)
        if a * b > 0 and abs(a) >= TRAIT_Z and abs(b) >= TRAIT_Z
    ]
    return [label for _, label in sorted(shared, key=lambda s: -s[0])[:limit]]


def population(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Players who define the average and can be suggested as similar."""
    return [r for r in rows if r["balls"] >= MIN_BALLS]
