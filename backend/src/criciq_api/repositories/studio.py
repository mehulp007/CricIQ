"""Chart Studio's catalog and SQL: what each dataset can count, and the query for a spec.

A dataset is a subquery over the serving tables with the same column names (``player_id``,
``team_id``, ``opposition_id``, ``venue_id``, ``season``, ``innings_no`` and its own
figures), the measures are aggregates over it and the dimensions are its columns. Every
piece of SQL comes from this module; a spec only picks among them, and its values
(players, teams, seasons, limits) always travel as parameters.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Any

from criciq_api.repositories.common import FilterColumns, where
from criciq_api.schemas.common import Filters
from criciq_api.schemas.studio import DatasetKey, DimensionKey, MeasureKind, StudioSpec
from criciq_core import stats

LIMITED = frozenset({"T20", "ODI"})
ALL_FORMATS = frozenset({"T20", "ODI", "Test"})
MAX_SERIES = 8


@dataclass(frozen=True)
class Measure:
    key: str
    label: str
    sql: str
    kind: MeasureKind
    description: str
    descending: bool = True
    formats: frozenset[str] = ALL_FORMATS
    model: bool = False


@dataclass(frozen=True)
class Dimension:
    key: DimensionKey
    label: str
    column: str
    # Seasons, positions, innings and phases have an order of their own.
    natural: bool = False


DIMENSIONS: dict[DimensionKey, Dimension] = {
    d.key: d
    for d in (
        Dimension("player", "Player", "s.player_id"),
        Dimension("team", "Team", "s.team_id"),
        Dimension("season", "Season", "s.season", natural=True),
        Dimension("opponent", "Opponent", "s.opposition_id"),
        Dimension("ground", "Ground", "s.venue_id"),
        Dimension("position", "Batting position", "s.position", natural=True),
        Dimension("phase", "Phase", "s.phase", natural=True),
        Dimension("innings", "Innings", "s.innings_no", natural=True),
    )
}


@dataclass(frozen=True)
class Dataset:
    key: DatasetKey
    label: str
    description: str
    # The FROM subquery; {wpa} is the WPA join (or a NULL column without the model table).
    source: str
    wpa_join: str
    sample: str
    sample_label: str
    measures: tuple[Measure, ...]
    dimensions: tuple[DimensionKey, ...]
    filters: frozenset[str]
    default_measures: tuple[str, ...]
    needs_player: bool = False

    def measure(self, key: str) -> Measure | None:
        return next((m for m in self.measures if m.key == key), None)

    def available(self, match_format: str, has_wpa: bool) -> list[Measure]:
        return [m for m in self.measures if match_format in m.formats and (has_wpa or not m.model)]

    def from_sql(self, has_wpa: bool) -> str:
        """The dataset's subquery, tidied for showing beside the chart."""
        source = textwrap.dedent(self.source).strip()
        if has_wpa and self.wpa_join:
            source = source.format(wpa_column="w.wpa", wpa=textwrap.dedent(self.wpa_join))
        else:
            source = source.format(wpa_column="NULL::DOUBLE AS wpa", wpa="")
        lines = [line.rstrip() for line in source.splitlines() if line.strip()]
        return "\n".join("    " + line for line in lines)


# The columns every dataset exposes as ``s.<column>``.
COLUMNS = FilterColumns(
    season="s.season",
    team="s.team_id",
    opponent="s.opposition_id",
    venue="s.venue_id",
    innings="s.innings_no",
)

_WPA = Measure(
    "wpa",
    "Win probability added",
    "round(sum(s.wpa), 3)",
    "wpa",
    "The change in the side's chance of winning over each ball, credited to batter and "
    "bowler (in matches won: 1 is one whole win). Model estimate.",
    model=True,
)

_BAT_AVG = stats.sql_batting_average("sum(s.runs)", "count(*) FILTER (WHERE s.is_out)")

BATTING = Dataset(
    key="batting",
    label="Batting innings",
    description="Every batter's innings: runs, balls, boundaries, dismissals and par.",
    source="""
        SELECT b.player_id, b.match_id, b.innings_no, b.season, b.venue_id, b.team_id,
               b.opposition_id, b.position, b.runs, b.balls, b.fours, b.sixes, b.dots,
               b.is_out, b.par_runs, {wpa_column}
        FROM player_batting_innings b
        {wpa}
    """,
    wpa_join="""LEFT JOIN player_wpa w ON w.player_id = b.player_id AND w.match_id = b.match_id
            AND w.innings_no = b.innings_no AND w.role = 'batting'""",
    sample="sum(s.balls)",
    sample_label="balls faced",
    measures=(
        Measure("innings", "Innings", "count(*)", "count", "Innings batted."),
        Measure("runs", "Runs", "sum(s.runs)", "count", "Runs off the bat."),
        Measure("balls", "Balls faced", "sum(s.balls)", "count", "Every ball but wides."),
        Measure(
            "not_outs", "Not outs", "count(*) FILTER (WHERE NOT s.is_out)", "count", "Not out."
        ),
        Measure(
            "highest",
            "Highest score",
            "max(s.runs * 2 + (NOT s.is_out)::INTEGER)",
            "score",
            "The best innings (* not out).",
        ),
        Measure("average", "Average", _BAT_AVG, "rate", "Runs per dismissal."),
        Measure(
            "strike_rate",
            "Strike rate",
            stats.sql_strike_rate("sum(s.runs)", "sum(s.balls)"),
            "rate",
            "Runs per 100 balls faced.",
        ),
        Measure(
            "hundreds", "100s", "count(*) FILTER (WHERE s.runs >= 100)", "count", "Innings of 100+."
        ),
        Measure(
            "fifties",
            "50s",
            "count(*) FILTER (WHERE s.runs >= 50 AND s.runs < 100)",
            "count",
            "Innings of 50 to 99.",
        ),
        Measure(
            "ducks",
            "Ducks",
            "count(*) FILTER (WHERE s.runs = 0 AND s.is_out)",
            "count",
            "Out for nought.",
        ),
        Measure("fours", "4s", "sum(s.fours)", "count", "Fours hit."),
        Measure("sixes", "6s", "sum(s.sixes)", "count", "Sixes hit."),
        Measure(
            "dot_pct",
            "Dot %",
            stats.sql_percent("sum(s.dots)", "sum(s.balls)"),
            "pct",
            "Balls faced without a run.",
            descending=False,
        ),
        Measure(
            "boundary_pct",
            "Boundary %",
            stats.sql_percent("sum(s.fours + s.sixes)", "sum(s.balls)"),
            "pct",
            "Balls faced hit for four or six.",
        ),
        Measure(
            "runs_above_par",
            "Runs above par",
            "round(sum(s.runs - s.par_runs), 1)",
            "signed",
            "Runs beyond what an average batter of the competition would have made from the "
            "same balls (same season and phase).",
        ),
        _WPA,
    ),
    dimensions=("player", "team", "season", "opponent", "ground", "position", "innings"),
    filters=frozenset({"players", "team", "opponent", "venue", "season", "position", "innings"}),
    default_measures=("runs", "average", "strike_rate"),
)

_BOWL = {
    "average": stats.sql_bowling_average("sum(s.runs)", "sum(s.wickets)"),
    "economy": stats.sql_economy("sum(s.runs)", "sum(s.balls)"),
    "strike_rate": stats.sql_bowling_strike_rate("sum(s.balls)", "sum(s.wickets)"),
}

BOWLING = Dataset(
    key="bowling",
    label="Bowling innings",
    description="Every bowler's innings: balls, runs conceded, wickets, dots and par.",
    source="""
        SELECT b.player_id, b.match_id, b.innings_no, b.season, b.venue_id, b.team_id,
               b.opposition_id, b.balls, b.runs, b.wickets, b.maidens, b.dots, b.fours,
               b.sixes, b.par_runs, {wpa_column}
        FROM player_bowling_innings b
        {wpa}
    """,
    wpa_join="""LEFT JOIN player_wpa w ON w.player_id = b.player_id AND w.match_id = b.match_id
            AND w.innings_no = b.innings_no AND w.role = 'bowling'""",
    sample="sum(s.balls)",
    sample_label="balls bowled",
    measures=(
        Measure("innings", "Innings", "count(*)", "count", "Innings bowled in."),
        Measure("overs", "Overs", "sum(s.balls)", "overs", "Legal balls, as overs."),
        Measure("wickets", "Wickets", "sum(s.wickets)", "count", "Wickets credited to the bowler."),
        Measure(
            "runs", "Runs conceded", "sum(s.runs)", "count", "Off the bat, wides and no-balls."
        ),
        Measure("average", "Bowling average", _BOWL["average"], "rate", "Runs per wicket.", False),
        Measure("economy", "Economy", _BOWL["economy"], "rate", "Runs per over.", False),
        Measure(
            "strike_rate",
            "Bowling strike rate",
            _BOWL["strike_rate"],
            "rate",
            "Balls per wicket.",
            False,
        ),
        Measure("maidens", "Maidens", "sum(s.maidens)", "count", "Overs without a run."),
        Measure(
            "four_wickets",
            "4-wicket innings",
            "count(*) FILTER (WHERE s.wickets = 4)",
            "count",
            "Innings with exactly four wickets.",
        ),
        Measure(
            "five_wickets",
            "5-wicket innings",
            "count(*) FILTER (WHERE s.wickets >= 5)",
            "count",
            "Innings with five wickets or more.",
        ),
        Measure(
            "best",
            "Best figures",
            "max(s.wickets * 1000 + 999 - least(s.runs, 999))",
            "figures",
            "Most wickets in an innings, then fewest runs.",
        ),
        Measure(
            "dot_pct",
            "Dot %",
            stats.sql_percent("sum(s.dots)", "sum(s.balls)"),
            "pct",
            "Legal balls without a run.",
        ),
        Measure(
            "boundary_pct",
            "Boundary % conceded",
            stats.sql_percent("sum(s.fours + s.sixes)", "sum(s.balls)"),
            "pct",
            "Legal balls hit for four or six.",
            descending=False,
        ),
        Measure(
            "runs_saved",
            "Runs saved vs par",
            "round(sum(s.par_runs - s.runs), 1)",
            "signed",
            "Runs fewer than an average bowler of the competition would have conceded from "
            "the same balls (same season and phase).",
        ),
        _WPA,
    ),
    dimensions=("player", "team", "season", "opponent", "ground", "innings"),
    filters=frozenset({"players", "team", "opponent", "venue", "season", "innings"}),
    default_measures=("wickets", "economy", "average"),
)

_PHASE_SOURCE = """
    SELECT p.*, NULL::DOUBLE AS wpa FROM {table} p
"""

PHASE_BATTING = Dataset(
    key="phase_batting",
    label="Batting by phase",
    description="Each batter's balls in each phase of each innings.",
    source=_PHASE_SOURCE.replace("{table}", "phase_batting") + "{wpa}",
    wpa_join="",
    sample="sum(s.balls)",
    sample_label="balls faced",
    measures=(
        Measure(
            "innings",
            "Innings",
            "count(*) FILTER (WHERE s.balls > 0 OR s.outs > 0)",
            "count",
            "Innings that batted in the phase.",
        ),
        Measure("runs", "Runs", "sum(s.runs)", "count", "Runs off the bat."),
        Measure("balls", "Balls faced", "sum(s.balls)", "count", "Every ball but wides."),
        Measure("outs", "Dismissals", "sum(s.outs)", "count", "Times out (run outs included)."),
        Measure(
            "average",
            "Average",
            stats.sql_batting_average("sum(s.runs)", "sum(s.outs)"),
            "rate",
            "Runs per dismissal.",
        ),
        Measure(
            "strike_rate",
            "Strike rate",
            stats.sql_strike_rate("sum(s.runs)", "sum(s.balls)"),
            "rate",
            "Runs per 100 balls faced.",
        ),
        Measure("fours", "4s", "sum(s.fours)", "count", "Fours hit."),
        Measure("sixes", "6s", "sum(s.sixes)", "count", "Sixes hit."),
        Measure(
            "dot_pct",
            "Dot %",
            stats.sql_percent("sum(s.dots)", "sum(s.balls)"),
            "pct",
            "Balls faced without a run.",
            descending=False,
        ),
        Measure(
            "boundary_pct",
            "Boundary %",
            stats.sql_percent("sum(s.fours + s.sixes)", "sum(s.balls)"),
            "pct",
            "Balls faced hit for four or six.",
        ),
    ),
    dimensions=("player", "team", "season", "opponent", "ground", "phase", "innings"),
    filters=frozenset({"players", "team", "opponent", "venue", "season", "phase", "innings"}),
    default_measures=("runs", "strike_rate", "dot_pct"),
)

PHASE_BOWLING = Dataset(
    key="phase_bowling",
    label="Bowling by phase",
    description="Each bowler's balls in each phase of each innings.",
    source=_PHASE_SOURCE.replace("{table}", "phase_bowling") + "{wpa}",
    wpa_join="",
    sample="sum(s.balls)",
    sample_label="balls bowled",
    measures=(
        Measure(
            "innings",
            "Innings",
            "count(*) FILTER (WHERE s.balls > 0)",
            "count",
            "Innings that bowled in the phase.",
        ),
        Measure("overs", "Overs", "sum(s.balls)", "overs", "Legal balls, as overs."),
        Measure("wickets", "Wickets", "sum(s.wickets)", "count", "Wickets credited to the bowler."),
        Measure("runs", "Runs conceded", "sum(s.runs)", "count", "Off the bat, wides, no-balls."),
        Measure("average", "Bowling average", _BOWL["average"], "rate", "Runs per wicket.", False),
        Measure("economy", "Economy", _BOWL["economy"], "rate", "Runs per over.", False),
        Measure(
            "strike_rate",
            "Bowling strike rate",
            _BOWL["strike_rate"],
            "rate",
            "Balls per wicket.",
            False,
        ),
        Measure(
            "dot_pct",
            "Dot %",
            stats.sql_percent("sum(s.dots)", "sum(s.balls)"),
            "pct",
            "Legal balls without a run.",
        ),
        Measure(
            "boundary_pct",
            "Boundary % conceded",
            stats.sql_percent("sum(s.fours + s.sixes)", "sum(s.balls)"),
            "pct",
            "Legal balls hit for four or six.",
            descending=False,
        ),
    ),
    dimensions=("player", "team", "season", "opponent", "ground", "phase", "innings"),
    filters=frozenset({"players", "team", "opponent", "venue", "season", "phase", "innings"}),
    default_measures=("wickets", "economy", "dot_pct"),
)

CAREERS = Dataset(
    key="careers",
    label="Careers",
    description="Each player's matches: batting, bowling, fielding and win probability added.",
    source="""
        SELECT a.player_id, a.match_id, tm.franchise_id AS team_id,
               tm.opponent_id AS opposition_id, tm.season, tm.venue_id,
               NULL::INTEGER AS innings_no,
               bt.runs, bt.balls, bt.outs, bt.hundreds, bt.fifties, bt.sixes,
               bw.wickets, bw.balls AS bowl_balls, bw.runs AS bowl_runs, bw.five_wickets,
               f.catches, f.stumpings, {wpa_column}
        FROM match_players a
        JOIN team_matches tm ON tm.match_id = a.match_id AND tm.team_id = a.team_season_id
        LEFT JOIN (
            SELECT player_id, match_id, sum(runs) AS runs, sum(balls) AS balls,
                   count(*) FILTER (WHERE is_out) AS outs,
                   count(*) FILTER (WHERE runs >= 100) AS hundreds,
                   count(*) FILTER (WHERE runs >= 50 AND runs < 100) AS fifties,
                   sum(sixes) AS sixes
            FROM player_batting_innings GROUP BY player_id, match_id
        ) bt ON bt.player_id = a.player_id AND bt.match_id = a.match_id
        LEFT JOIN (
            SELECT player_id, match_id, sum(wickets) AS wickets, sum(balls) AS balls,
                   sum(runs) AS runs, count(*) FILTER (WHERE wickets >= 5) AS five_wickets
            FROM player_bowling_innings GROUP BY player_id, match_id
        ) bw ON bw.player_id = a.player_id AND bw.match_id = a.match_id
        LEFT JOIN player_fielding f ON f.player_id = a.player_id AND f.match_id = a.match_id
        {wpa}
    """,
    wpa_join="""LEFT JOIN (
            SELECT player_id, match_id, sum(wpa) AS wpa FROM player_wpa GROUP BY ALL
        ) w ON w.player_id = a.player_id AND w.match_id = a.match_id""",
    sample="count(*)",
    sample_label="matches",
    measures=(
        Measure("matches", "Matches", "count(*)", "count", "Appearances (substitutes included)."),
        Measure("runs", "Runs", "coalesce(sum(s.runs), 0)", "count", "Runs off the bat."),
        Measure(
            "average",
            "Batting average",
            stats.sql_batting_average("sum(s.runs)", "sum(s.outs)"),
            "rate",
            "Runs per dismissal.",
        ),
        Measure(
            "strike_rate",
            "Strike rate",
            stats.sql_strike_rate("sum(s.runs)", "sum(s.balls)"),
            "rate",
            "Runs per 100 balls faced.",
        ),
        Measure("hundreds", "100s", "coalesce(sum(s.hundreds), 0)", "count", "Innings of 100+."),
        Measure("fifties", "50s", "coalesce(sum(s.fifties), 0)", "count", "Innings of 50 to 99."),
        Measure("sixes", "6s", "coalesce(sum(s.sixes), 0)", "count", "Sixes hit."),
        Measure(
            "wickets",
            "Wickets",
            "coalesce(sum(s.wickets), 0)",
            "count",
            "Wickets credited to the bowler.",
        ),
        Measure(
            "bowling_average",
            "Bowling average",
            stats.sql_bowling_average("sum(s.bowl_runs)", "sum(s.wickets)"),
            "rate",
            "Runs conceded per wicket.",
            descending=False,
        ),
        Measure(
            "economy",
            "Economy",
            stats.sql_economy("sum(s.bowl_runs)", "sum(s.bowl_balls)"),
            "rate",
            "Runs conceded per over.",
            descending=False,
        ),
        Measure(
            "five_wickets",
            "5-wicket innings",
            "coalesce(sum(s.five_wickets), 0)",
            "count",
            "Innings with five wickets or more.",
        ),
        Measure(
            "catches",
            "Catches",
            "coalesce(sum(s.catches), 0)",
            "count",
            "Catches, caught-and-bowled included (substitutes not credited).",
        ),
        Measure("stumpings", "Stumpings", "coalesce(sum(s.stumpings), 0)", "count", "Stumpings."),
        _WPA,
    ),
    dimensions=("player", "team", "season", "opponent", "ground"),
    filters=frozenset({"players", "team", "opponent", "venue", "season"}),
    default_measures=("matches", "runs", "wickets"),
    needs_player=True,
)

_WON = "count(*) FILTER (WHERE s.result = 'won')"

TEAMS = Dataset(
    key="teams",
    label="Team results",
    description="Both sides of every match: results, totals and run rates.",
    source="""
        SELECT tm.match_id, tm.franchise_id AS team_id, tm.opponent_id AS opposition_id,
               tm.season, tm.venue_id,
               CASE WHEN tm.batted_first THEN 1 WHEN NOT tm.batted_first THEN 2 END
                   AS innings_no,
               tm.result, tm.runs_for, tm.balls_for, tm.runs_against, tm.balls_against,
               {wpa_column}
        FROM team_matches tm
        {wpa}
    """,
    wpa_join="",
    sample="count(*)",
    sample_label="matches",
    measures=(
        Measure("matches", "Matches", "count(*)", "count", "Matches played, no results included."),
        Measure("won", "Won", _WON, "count", "Wins (a super-over tie counts for its winner)."),
        Measure("lost", "Lost", "count(*) FILTER (WHERE s.result = 'lost')", "count", "Defeats."),
        Measure(
            "drawn",
            "Drawn",
            "count(*) FILTER (WHERE s.result = 'drawn')",
            "count",
            "Draws.",
            formats=frozenset({"Test"}),
        ),
        Measure(
            "no_result",
            "No result",
            "count(*) FILTER (WHERE s.result = 'no_result')",
            "count",
            "Matches without a result.",
        ),
        Measure(
            "win_pct",
            "Win %",
            stats.sql_percent(_WON, "count(*) FILTER (WHERE s.result <> 'no_result')"),
            "pct",
            "Wins per match with a result.",
        ),
        Measure(
            "average_for",
            "Average score",
            "round(avg(s.runs_for), 1)",
            "rate",
            "The side's average total.",
            formats=LIMITED,
        ),
        Measure(
            "average_against",
            "Average conceded",
            "round(avg(s.runs_against), 1)",
            "rate",
            "The opponents' average total.",
            descending=False,
            formats=LIMITED,
        ),
        Measure(
            "highest_total",
            "Highest total",
            "max(s.runs_for)",
            "count",
            "The side's best total.",
            formats=LIMITED,
        ),
        Measure(
            "run_rate_for",
            "Run rate",
            stats.sql_run_rate("sum(s.runs_for)", "sum(s.balls_for)"),
            "rate",
            "Runs per over batting.",
            formats=LIMITED,
        ),
        Measure(
            "run_rate_against",
            "Run rate conceded",
            stats.sql_run_rate("sum(s.runs_against)", "sum(s.balls_against)"),
            "rate",
            "Runs per over bowling.",
            descending=False,
            formats=LIMITED,
        ),
    ),
    dimensions=("team", "season", "opponent", "ground", "innings"),
    filters=frozenset({"team", "opponent", "venue", "season", "innings"}),
    default_measures=("matches", "won", "win_pct"),
)

DATASETS: dict[DatasetKey, Dataset] = {
    d.key: d for d in (BATTING, BOWLING, PHASE_BATTING, PHASE_BOWLING, CAREERS, TEAMS)
}

# The tables each dataset reads.
TABLES: dict[DatasetKey, tuple[str, ...]] = {
    "batting": ("player_batting_innings",),
    "bowling": ("player_bowling_innings",),
    "phase_batting": ("phase_batting",),
    "phase_bowling": ("phase_bowling",),
    "careers": (
        "match_players",
        "team_matches",
        "player_batting_innings",
        "player_bowling_innings",
        "player_fielding",
    ),
    "teams": ("team_matches",),
}


@dataclass(frozen=True)
class Query:
    sql: str
    params: list[Any]


def _filters(dataset: Dataset, spec: StudioSpec) -> tuple[str, list[Any]]:
    f = spec.filters
    clause, params = where(
        Filters(
            season_from=f.season_from,
            season_to=f.season_to,
            team=f.team,
            opponent=f.opponent,
            venue=f.venue,
            innings=f.innings,
        ),
        COLUMNS,
    )
    clauses = [clause]
    if f.players:
        clauses.append(f"s.player_id IN ({', '.join('?' for _ in f.players)})")
        params.extend(f.players)
    if f.position is not None:
        clauses.append("s.position = ?")
        params.append(f.position)
    if f.phase is not None:
        clauses.append("s.phase = ?")
        params.append(f.phase)
    return " AND ".join(clauses), params


def _order(
    dimension: Dimension,
    alias: str,
    sort: Measure | None,
    descending: bool,
    phase_keys: list[str],
) -> tuple[str, list[Any]]:
    """ORDER BY for a grouping: its own order, or by the sort measure."""
    if sort is None:
        direction = "DESC" if descending else "ASC"
        if dimension.key == "phase":
            return f"list_position(?::VARCHAR[], {alias}) {direction}", [phase_keys]
        return f"{alias} {direction}", []
    direction = "DESC" if descending else "ASC"
    return f"m_{sort.key} {direction} NULLS LAST, {alias}", []


def compile_query(
    dataset: Dataset,
    spec: StudioSpec,
    measures: list[Measure],
    sort: Measure | None,
    descending: bool,
    *,
    has_wpa: bool,
    phase_keys: list[str],
) -> Query:
    """The query for a spec already checked against the catalog (see the service)."""
    clause, params = _filters(dataset, spec)
    select = ",\n       ".join(f"{m.sql} AS m_{m.key}" for m in measures)
    source = f"(\n{dataset.from_sql(has_wpa)}\n) s"

    if spec.group_by is None:
        return Query(
            f"SELECT {select},\n       {dataset.sample} AS sample\nFROM {source}\nWHERE {clause}",
            params,
        )

    group = DIMENSIONS[spec.group_by]
    if spec.split_by is None:
        order, order_params = _order(group, "group_key", sort, descending, phase_keys)
        return Query(
            f"SELECT {group.column} AS group_key,\n       {select},\n"
            f"       {dataset.sample} AS sample\n"
            f"FROM {source}\n"
            f"WHERE {clause} AND {group.column} IS NOT NULL\n"
            f"GROUP BY {group.column}\n"
            f"HAVING {dataset.sample} >= ?\n"
            f"ORDER BY {order}\n"
            f"LIMIT ?",
            [*params, spec.min_sample, *order_params, spec.limit + 1],
        )

    split = DIMENSIONS[spec.split_by]
    g, sp = group.column, split.column
    group_order, group_params = _order(group, "group_key", sort, descending, phase_keys)
    # Series are ranked by the figure unless they have an order of their own.
    split_sort = None if split.natural else (sort or measures[0])
    split_descending = (
        False if split.natural else descending if sort is not None else measures[0].descending
    )
    split_order, split_params = _order(split, "split_key", split_sort, split_descending, phase_keys)
    return Query(
        f"""WITH agg AS (
    SELECT {g} AS group_key, {sp} AS split_key,
           GROUPING({g}) AS any_group, GROUPING({sp}) AS any_split,
           {select},
           {dataset.sample} AS sample
    FROM {source}
    WHERE {clause} AND {g} IS NOT NULL AND {sp} IS NOT NULL
    GROUP BY GROUPING SETS (({g}), ({sp}), ({g}, {sp}))
),
kept_groups AS (
    SELECT group_key FROM agg WHERE any_split = 1 AND sample >= ?
    ORDER BY {group_order} LIMIT ?
),
kept_splits AS (
    SELECT split_key FROM agg WHERE any_group = 1 AND sample >= ?
    ORDER BY {split_order} LIMIT ?
)
SELECT * FROM agg
WHERE (any_split = 1 AND group_key IN (SELECT group_key FROM kept_groups))
   OR (any_group = 1 AND split_key IN (SELECT split_key FROM kept_splits))
   OR (any_group = 0 AND any_split = 0 AND sample >= ?
       AND group_key IN (SELECT group_key FROM kept_groups)
       AND split_key IN (SELECT split_key FROM kept_splits))""",
        [
            *params,
            spec.min_sample,
            *group_params,
            spec.limit + 1,
            spec.min_sample,
            *split_params,
            spec.series,
            spec.min_sample,
        ],
    )
