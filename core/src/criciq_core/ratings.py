"""CricIQ Ratings: the components and the population rules.

Shared by the fit (``criciq_ml.ratings``, which estimates how far each
component must be shrunk) and the API (which rates players for any season
window), so both read exactly the same evidence.

Every component is a sum of per-innings evidence ``e`` over an exposure ``n``
(balls or innings), always oriented so that higher is better:

    value = scale * sum(e) / sum(n)

A player's estimate is shrunk towards the window's average by ``k`` units of
exposure (fitted per component), and the rating is the share of qualified
players in the window whose shrunk estimate is lower (0-100).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Literal

from criciq_core.phases import default_phase_config, model_format

Role = Literal["batting", "bowling"]
Unit = Literal[
    "runs_per_100",
    "dismissals_per_100",
    "runs_per_over",
    "wickets_per_4_overs",
    "points",
    "percent",
]

# The reference population in a window: at least MIN_BALLS in the role, and
# at least the component's own ``qualify`` exposure (e.g. 120 death-over balls).
MIN_BALLS = 300
MIN_SUBSET_BALLS = 120
MIN_INNINGS = 10
# Ratings are shown (with wide intervals) from MIN_RATED_BALLS in the role.
MIN_RATED_BALLS = 60


@dataclass(frozen=True)
class Component:
    key: str
    role: Role
    label: str
    description: str
    unit: Unit
    scale: float
    exposure: Literal["balls", "innings"]
    sql: str  # one row per innings: player_id, season, e, n
    qualify: int  # minimum exposure to join the reference population
    show: int  # minimum exposure to be rated at all
    requires: str | None = None  # a table that only exists once the data is scored

    def value(self, e: float, n: float) -> float | None:
        return self.scale * e / n if n else None


_WPA = """
    SELECT w.player_id, s.year AS season, w.wpa AS e, 1 AS n
    FROM player_wpa w JOIN matches m USING (match_id) JOIN seasons s USING (season_id)
    WHERE w.role = '{role}'
"""


def _phases(match_format: str) -> list[tuple[str, str, int, int]]:
    phases = default_phase_config().for_format(match_format).phases
    return [(p.key, p.label, p.first_over, p.last_over) for p in phases if p.last_over]


def components(match_format: str | None = None) -> tuple[Component, ...]:
    """Every component in a format (the models' current one by default): the phase
    components follow its phases."""
    return _components(match_format or model_format())


@cache
def _components(match_format: str) -> tuple[Component, ...]:
    batting = [
        Component(
            key="scoring",
            role="batting",
            label="Run scoring",
            description="Runs per 100 balls above an average batter facing the same balls.",
            unit="runs_per_100",
            scale=100,
            exposure="balls",
            sql="SELECT player_id, season, runs - par_runs AS e, balls AS n "
            "FROM player_batting_innings",
            qualify=MIN_BALLS,
            show=MIN_RATED_BALLS,
        ),
        Component(
            key="survival",
            role="batting",
            label="Survival",
            description="Dismissals avoided per 100 balls, compared with par for the same balls.",
            unit="dismissals_per_100",
            scale=100,
            exposure="balls",
            sql="SELECT player_id, season, par_outs - is_out::INTEGER AS e, balls AS n "
            "FROM player_batting_innings",
            qualify=MIN_BALLS,
            show=MIN_RATED_BALLS,
        ),
    ]
    for key, label, first, last in _phases(match_format):
        batting.append(
            Component(
                key=key,
                role="batting",
                label=label,
                description=f"Runs per 100 balls above par in overs {first}\u2013{last}.",
                unit="runs_per_100",
                scale=100,
                exposure="balls",
                sql="SELECT player_id, season, runs - par_runs AS e, balls AS n "
                f"FROM player_batting_phases WHERE phase = '{key}'",
                qualify=MIN_SUBSET_BALLS,
                show=30,
            )
        )
    batting += [
        Component(
            key="chasing",
            role="batting",
            label="Chasing",
            description="Runs per 100 balls above par in the second innings.",
            unit="runs_per_100",
            scale=100,
            exposure="balls",
            sql="SELECT player_id, season, runs - par_runs AS e, balls AS n "
            "FROM player_batting_innings WHERE innings_no = 2",
            qualify=MIN_SUBSET_BALLS,
            show=30,
        ),
        Component(
            key="impact",
            role="batting",
            label="Impact",
            description="Win probability added per innings, in percentage points.",
            unit="points",
            scale=100,
            exposure="innings",
            sql=_WPA.format(role="batting"),
            qualify=MIN_INNINGS,
            show=5,
            requires="player_wpa",
        ),
        Component(
            key="consistency",
            role="batting",
            label="Consistency",
            description="Share of innings scoring at least par for the balls faced.",
            unit="percent",
            scale=100,
            exposure="innings",
            sql="SELECT player_id, season, (runs >= par_runs)::INTEGER AS e, 1 AS n "
            "FROM player_batting_innings WHERE balls > 0",
            qualify=MIN_INNINGS,
            show=5,
        ),
    ]

    bowling = [
        Component(
            key="economy",
            role="bowling",
            label="Economy",
            description="Runs per over saved against an average bowler bowling the same balls.",
            unit="runs_per_over",
            scale=6,
            exposure="balls",
            sql="SELECT player_id, season, par_runs - runs AS e, balls AS n "
            "FROM player_bowling_innings",
            qualify=MIN_BALLS,
            show=MIN_RATED_BALLS,
        ),
        Component(
            key="wickets",
            role="bowling",
            label="Wicket-taking",
            description="Wickets per four overs above par for the same balls.",
            unit="wickets_per_4_overs",
            scale=24,
            exposure="balls",
            sql="SELECT player_id, season, wickets - par_wickets AS e, balls AS n "
            "FROM player_bowling_innings",
            qualify=MIN_BALLS,
            show=MIN_RATED_BALLS,
        ),
    ]
    for key, label, first, last in _phases(match_format):
        bowling.append(
            Component(
                key=key,
                role="bowling",
                label=label,
                description=f"Runs per over saved against par in overs {first}\u2013{last}.",
                unit="runs_per_over",
                scale=6,
                exposure="balls",
                sql="SELECT player_id, season, par_runs - runs AS e, balls AS n "
                f"FROM player_bowling_phases WHERE phase = '{key}'",
                qualify=MIN_SUBSET_BALLS,
                show=30,
            )
        )
    bowling += [
        Component(
            key="defending",
            role="bowling",
            label="Defending",
            description="Runs per over saved against par in the second innings.",
            unit="runs_per_over",
            scale=6,
            exposure="balls",
            sql="SELECT player_id, season, par_runs - runs AS e, balls AS n "
            "FROM player_bowling_innings WHERE innings_no = 2",
            qualify=MIN_SUBSET_BALLS,
            show=30,
        ),
        Component(
            key="impact",
            role="bowling",
            label="Impact",
            description="Win probability added per innings bowled, in percentage points.",
            unit="points",
            scale=100,
            exposure="innings",
            sql=_WPA.format(role="bowling"),
            qualify=MIN_INNINGS,
            show=5,
            requires="player_wpa",
        ),
        Component(
            key="consistency",
            role="bowling",
            label="Consistency",
            description="Share of innings conceding no more than par for the balls bowled.",
            unit="percent",
            scale=100,
            exposure="innings",
            sql="SELECT player_id, season, (runs <= par_runs)::INTEGER AS e, 1 AS n "
            "FROM player_bowling_innings WHERE balls > 0",
            qualify=MIN_INNINGS,
            show=5,
        ),
    ]
    return (*batting, *bowling)


def role_components(
    role: Role,
    tables: frozenset[str] | set[str] | None = None,
    match_format: str | None = None,
) -> list[Component]:
    """A role's components, skipping any whose source table is missing."""
    return [
        c
        for c in components(match_format)
        if c.role == role and (tables is None or c.requires is None or c.requires in tables)
    ]


def role_balls_key(role: Role) -> str:
    """The component whose exposure is the player's balls in the role."""
    return "scoring" if role == "batting" else "economy"


def units_sql(
    role: Role,
    tables: frozenset[str] | set[str] | None = None,
    match_format: str | None = None,
) -> str:
    """Every component of a role as one query: component, player_id, season, e, n."""
    return "\nUNION ALL\n".join(
        f"SELECT '{c.key}' AS component, player_id, season, e::DOUBLE AS e, n::DOUBLE AS n "
        f"FROM ({c.sql})"
        for c in role_components(role, tables, match_format)
    )


def window_sums_sql(
    role: Role,
    tables: frozenset[str] | set[str] | None = None,
    match_format: str | None = None,
) -> str:
    """Per player and component: sum(e) and sum(n) for seasons between two parameters."""
    return f"""
        SELECT component, player_id, sum(e) AS e, sum(n) AS n
        FROM ({units_sql(role, tables, match_format)})
        WHERE season BETWEEN ? AND ?
        GROUP BY ALL
    """
