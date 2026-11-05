"""SQL for the Records hub: one query per record, over the serving database's player,
team, partnership and model tables, all returning the same columns.

Each record's query selects ``value`` (what it is ranked by), ``tiebreak`` (lower
first among equal values), the player (and partner), the side and its opponent, the
match, ground, date and season, the ball to open a replay at, a ``sample`` and up to
four extra figures ``x1``..``x4``. ``ranked`` wraps it: ranks with ties shared, the
names, and a page of rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from criciq_api.db import Database, Row
from criciq_api.repositories.common import FilterColumns, where
from criciq_api.schemas.common import Filters
from criciq_core.records import Qualification

Group = Literal[
    "batting", "bowling", "fielding", "seasons", "partnerships", "teams", "ball_by_ball"
]
ALL_FORMATS = frozenset({"T20", "ODI", "Test"})

_COLUMNS = (
    "value",
    "tiebreak",
    "player_id",
    "partner_id",
    "team_id",
    "opponent_id",
    "venue_id",
    "match_id",
    "match_date",
    "season",
    "innings_no",
    "seq_no",
    "sample",
    "flag",
    "x1",
    "x2",
    "x3",
    "x4",
)
_TYPES = {
    "player_id": "VARCHAR",
    "partner_id": "VARCHAR",
    "team_id": "VARCHAR",
    "opponent_id": "VARCHAR",
    "venue_id": "VARCHAR",
    "match_id": "BIGINT",
    "match_date": "DATE",
    "season": "INTEGER",
    "innings_no": "INTEGER",
    "seq_no": "INTEGER",
    "sample": "BIGINT",
    "flag": "BOOLEAN",
}


def _select(**columns: str) -> str:
    """The shared column list, NULL (of the right type) where a record has nothing."""
    unknown = set(columns) - set(_COLUMNS)
    assert not unknown, unknown
    return ", ".join(
        f"({columns[c]})::{_TYPES.get(c, 'DOUBLE')} AS {c}"
        if c in columns
        else f"NULL::{_TYPES.get(c, 'DOUBLE')} AS {c}"
        for c in _COLUMNS
    )


# Every source below (aliased ``s``) names its filter columns the same way: the season,
# the side (``team_id``), its opponent (``opposition_id``) and the ground.
_SOURCE = FilterColumns(
    season="s.season",
    team="s.team_id",
    opponent="s.opposition_id",
    venue="s.venue_id",
    innings=None,
)

BATTING = "player_batting_innings"
BOWLING = "player_bowling_innings"
# A player's fielding in a match, with their side, the opponent and the ground.
FIELDING = """(
    SELECT pf.player_id, pf.match_id, tm.season, tm.match_date, tm.venue_id,
           tm.franchise_id AS team_id, tm.opponent_id AS opposition_id, pf.catches, pf.stumpings
    FROM player_fielding pf
    JOIN match_players mp USING (match_id, player_id)
    JOIN team_seasons ts ON ts.team_season_id = mp.team_season_id
    JOIN team_matches tm ON tm.match_id = pf.match_id AND tm.franchise_id = ts.franchise_id
)"""
APPEARANCES = """(
    SELECT mp.player_id, mp.match_id, tm.season, tm.match_date, tm.venue_id,
           tm.franchise_id AS team_id, tm.opponent_id AS opposition_id
    FROM match_players mp
    JOIN team_seasons ts ON ts.team_season_id = mp.team_season_id
    JOIN team_matches tm ON tm.match_id = mp.match_id AND tm.franchise_id = ts.franchise_id
)"""
# A side's innings. Its target, where Cricsheet gives none (Tests), is one more than the
# opponents' runs in the match less the side's own earlier runs.
TEAM_INNINGS = """(
    SELECT i.match_id, i.innings_no, se.year AS season, m.match_date, m.venue_id,
           tb.franchise_id AS team_id, tw.franchise_id AS opposition_id,
           i.runs, i.wickets, i.legal_balls, {declared} AS declared,
           coalesce(
               i.target_runs,
               opp.runs - coalesce(sum(i.runs) OVER (
                   PARTITION BY i.match_id, i.batting_team_id ORDER BY i.innings_no
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) + 1
           ) AS target_runs,
           m.winner_id = i.batting_team_id AS won, m.win_method,
           max(i.innings_no) OVER (PARTITION BY i.match_id) AS last_innings
    FROM innings i
    JOIN matches m USING (match_id)
    JOIN seasons se USING (season_id)
    JOIN team_seasons tb ON tb.team_season_id = i.batting_team_id
    JOIN team_seasons tw ON tw.team_season_id = i.bowling_team_id
    LEFT JOIN (
        SELECT match_id, batting_team_id, sum(runs) AS runs
        FROM innings WHERE NOT is_super_over GROUP BY ALL
    ) opp ON opp.match_id = i.match_id AND opp.batting_team_id = i.bowling_team_id
    WHERE NOT i.is_super_over
)"""
RESULTS = """(
    SELECT m.match_id, se.year AS season, m.match_date, m.venue_id,
           tw.franchise_id AS team_id, tl.franchise_id AS opposition_id,
           m.win_by_runs, m.win_by_wickets, {win_by_innings} AS win_by_innings, m.win_method,
           tm.balls_to_spare
    FROM matches m
    JOIN seasons se USING (season_id)
    JOIN team_seasons tw ON tw.team_season_id = m.winner_id
    JOIN team_seasons tl ON tl.team_season_id =
        CASE WHEN m.winner_id = m.team1_id THEN m.team2_id ELSE m.team1_id END
    LEFT JOIN team_matches tm ON tm.match_id = m.match_id AND tm.franchise_id = tw.franchise_id
    WHERE NOT m.decided_by_super_over AND m.win_method IS NULL
)"""
OVERS = """(
    SELECT o.match_id, o.innings_no, o.over, o.season, m.match_date, o.venue_id,
           o.batting_id AS team_id, o.bowling_id AS opposition_id, o.runs, o.balls, o.wickets,
           b.bowler_id
    FROM team_innings_overs o
    JOIN matches m USING (match_id)
    JOIN (SELECT match_id, innings_no, over_no + 1 AS over, mode(bowler_id) AS bowler_id
          FROM deliveries GROUP BY ALL) b USING (match_id, innings_no, over)
)"""
SWINGS = """(
    SELECT w.match_id, w.innings_no, w.seq_no, w.season, w.match_date, w.venue_id,
           w.swing, w.wp_before, w.wp_after, w.batter_id, w.bowler_id,
           tg.franchise_id AS team_id, tr.franchise_id AS opposition_id
    FROM match_swings w
    JOIN match_summaries ms USING (match_id)
    JOIN team_seasons tg ON tg.team_season_id = w.team_season_id
    JOIN team_seasons tr ON tr.team_season_id =
        CASE WHEN w.team_season_id = ms.team_a_id THEN ms.team_b_id ELSE ms.team_a_id END
)"""
WPA = """(
    SELECT a.player_id, a.match_id, tm.season, tm.match_date, tm.venue_id,
           tm.franchise_id AS team_id, tm.opponent_id AS opposition_id,
           sum(a.wpa) AS wpa,
           sum(a.wpa) FILTER (WHERE a.role = 'batting') AS bat_wpa,
           sum(a.wpa) FILTER (WHERE a.role = 'bowling') AS bowl_wpa
    FROM player_wpa a
    JOIN match_players mp USING (match_id, player_id)
    JOIN team_seasons ts ON ts.team_season_id = mp.team_season_id
    JOIN team_matches tm ON tm.match_id = a.match_id AND tm.franchise_id = ts.franchise_id
    GROUP BY ALL
)"""


@dataclass(frozen=True)
class RecordDef:
    key: str
    group: Group
    label: str
    # What one entry is: a player's career, an innings, a match, a stand, a side's innings.
    level: Literal["career", "innings", "match", "season", "stand", "over"]
    # Lower is better (averages, economy, fastest).
    ascending: bool
    # The query, given the filter condition and the qualification; returns SQL and params.
    sql: Any
    # The figures beside the value, in order: (header, column, digits, kind).
    columns: tuple[tuple[str, str, int, str], ...] = ()
    formats: frozenset[str] = ALL_FORMATS
    # The table it needs (absent from a database not yet scored, for the model records).
    needs: str | None = None
    model: bool = False
    description: str = ""
    # The qualification attribute it uses, stated beside the list.
    qualification: str | None = None
    # How the value reads ("runs", "wickets", "balls").
    unit: str = ""
    extra_filters: tuple[str, ...] = field(default_factory=tuple)
    # Tests' figures where they differ (no balls to spare in a Test).
    test_columns: tuple[tuple[str, str, int, str], ...] | None = None
    # What the player and partner were doing ("batter", "bowler"); None for a stand's pair.
    roles: tuple[str | None, str | None] = (None, None)

    def columns_for(self, match_format: str) -> tuple[tuple[str, str, int, str], ...]:
        if match_format == "Test" and self.test_columns is not None:
            return self.test_columns
        return self.columns


def _career_batting(value: str, having: str = "TRUE", *, ties: str = "balls") -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=ties if ties != "balls" else "sum(balls)",
                player_id="s.player_id",
                team_id="mode(s.team_id)",
                sample="count(*)",
                x1="sum(runs)",
                x2="round(sum(runs) / nullif(count(*) FILTER (WHERE is_out), 0), 2)",
                x3="round(100.0 * sum(runs) / nullif(sum(balls), 0), 2)",
                x4="max(runs)",
            )
        }
        FROM {BATTING} s WHERE {clause}
        GROUP BY s.player_id HAVING {having.format(q=q)}
        """

    return build


def _career_bowling(value: str, having: str = "TRUE", *, ties: str = "sum(runs)") -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=ties,
                player_id="s.player_id",
                team_id="mode(s.team_id)",
                sample="count(*) FILTER (WHERE balls > 0)",
                x1="sum(wickets)",
                x2="round(sum(runs) / nullif(sum(wickets), 0), 2)",
                x3="round(6.0 * sum(runs) / nullif(sum(balls), 0), 2)",
                x4="sum(balls)",
            )
        }
        FROM {BOWLING} s WHERE {clause}
        GROUP BY s.player_id HAVING {having.format(q=q)}
        """

    return build


def _batting_innings(value: str, condition: str = "TRUE", *, ties: str = "s.balls") -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=ties,
                player_id="s.player_id",
                team_id="s.team_id",
                opponent_id="s.opposition_id",
                venue_id="s.venue_id",
                match_id="s.match_id",
                match_date="s.match_date",
                season="s.season",
                innings_no="s.innings_no",
                sample="s.balls",
                flag="NOT s.is_out",
                x1="s.runs",
                x2="s.balls",
                x3="s.fours",
                x4="s.sixes",
            )
        }
        FROM {BATTING} s
        LEFT JOIN batting_milestones ms USING (match_id, innings_no, player_id)
        WHERE {clause} AND {condition.format(q=q)}
        """

    return build


def _bowling_innings(value: str, condition: str = "TRUE", *, ties: str = "s.runs") -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=ties,
                player_id="s.player_id",
                team_id="s.team_id",
                opponent_id="s.opposition_id",
                venue_id="s.venue_id",
                match_id="s.match_id",
                match_date="s.match_date",
                season="s.season",
                innings_no="s.innings_no",
                sample="s.balls",
                x1="s.wickets",
                x2="s.runs",
                x3="s.balls",
                x4="s.dots",
            )
        }
        FROM {BOWLING} s WHERE {clause} AND {condition.format(q=q)}
        """

    return build


def _fielding(value: str) -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak="count(*)",
                player_id="s.player_id",
                team_id="mode(s.team_id)",
                sample="count(*)",
                x1="sum(catches)",
                x2="sum(stumpings)",
            )
        }
        FROM {FIELDING} s WHERE {clause}
        GROUP BY s.player_id HAVING {value} > 0
        """

    return build


def _appearances(clause: str, q: Qualification) -> str:
    return f"""
    SELECT {
        _select(
            value="count(DISTINCT s.match_id)",
            tiebreak="epoch(min(s.match_date))",  # the earlier debut first
            player_id="s.player_id",
            team_id="mode(s.team_id)",
            sample="count(DISTINCT s.match_id)",
        )
    }
    FROM {APPEARANCES} s WHERE {clause}
    GROUP BY s.player_id
    """


def _season(kind: Literal["bat", "bowl"]) -> Any:
    def build(clause: str, q: Qualification) -> str:
        if kind == "bat":
            value, extra = (
                "sum(runs)",
                "round(sum(runs) / nullif(count(*) FILTER (WHERE is_out), 0), 2)",
            )
            table, tie = BATTING, "sum(balls)"
        else:
            value, extra = "sum(wickets)", "round(sum(runs) / nullif(sum(wickets), 0), 2)"
            table, tie = BOWLING, "sum(runs)"
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=tie,
                player_id="s.player_id",
                team_id="mode(s.team_id)",
                season="s.season",
                sample="count(*)",
                x1=value,
                x2=extra,
            )
        }
        FROM {table} s WHERE {clause}
        GROUP BY s.player_id, s.season HAVING {value} > 0
        """

    return build


def _stands(clause: str, q: Qualification) -> str:
    return f"""
    SELECT {
        _select(
            value="s.runs",
            tiebreak="s.balls",
            player_id="s.first_id",
            partner_id="s.second_id",
            team_id="s.team_id",
            opponent_id="s.opposition_id",
            venue_id="s.venue_id",
            match_id="s.match_id",
            match_date="s.match_date",
            season="s.season",
            innings_no="s.innings_no",
            seq_no="s.first_seq",
            sample="s.balls",
            flag="s.unbroken",
            x1="s.wicket",
            x2="s.first_runs",
            x3="s.second_runs",
            x4="s.balls",
        )
    }
    FROM partnerships s WHERE {clause}
    """


def _team_innings(value: str, condition: str, *, ties: str) -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=ties,
                team_id="s.team_id",
                opponent_id="s.opposition_id",
                venue_id="s.venue_id",
                match_id="s.match_id",
                match_date="s.match_date",
                season="s.season",
                innings_no="s.innings_no",
                sample="s.legal_balls",
                flag="s.declared",
                x1="s.runs",
                x2="s.wickets",
                x3="s.legal_balls",
                x4="s.target_runs",
            )
        }
        FROM {TEAM_INNINGS} s WHERE {clause} AND {condition}
        """

    return build


def _wins(value: str, condition: str, *, ties: str) -> Any:
    def build(clause: str, q: Qualification) -> str:
        return f"""
        SELECT {
            _select(
                value=value,
                tiebreak=ties,
                team_id="s.team_id",
                opponent_id="s.opposition_id",
                venue_id="s.venue_id",
                match_id="s.match_id",
                match_date="s.match_date",
                season="s.season",
                x1="s.win_by_runs",
                x2="s.win_by_wickets",
                x3="s.balls_to_spare",
            )
        }
        FROM {RESULTS} s WHERE {clause} AND {condition}
        """

    return build


def _overs(clause: str, q: Qualification) -> str:
    return f"""
    SELECT {
        _select(
            value="s.runs",
            tiebreak="-s.wickets",
            player_id="s.bowler_id",
            team_id="s.team_id",
            opponent_id="s.opposition_id",
            venue_id="s.venue_id",
            match_id="s.match_id",
            match_date="s.match_date",
            season="s.season",
            innings_no="s.innings_no",
            sample="s.balls",
            x1="s.over",
            x2="s.wickets",
            x3="s.balls",
        )
    }
    FROM {OVERS} s WHERE {clause}
    """


def _swings(clause: str, q: Qualification) -> str:
    return f"""
    SELECT {
        _select(
            value="round(100 * s.swing, 1)",
            tiebreak="-s.match_id",
            player_id="s.batter_id",
            partner_id="s.bowler_id",
            team_id="s.team_id",
            opponent_id="s.opposition_id",
            venue_id="s.venue_id",
            match_id="s.match_id",
            match_date="s.match_date",
            season="s.season",
            innings_no="s.innings_no",
            seq_no="s.seq_no",
            x1="round(100 * s.wp_before, 1)",
            x2="round(100 * s.wp_after, 1)",
        )
    }
    FROM {SWINGS} s WHERE {clause}
    """


def _wpa(clause: str, q: Qualification) -> str:
    return f"""
    SELECT {
        _select(
            value="round(s.wpa, 3)",
            tiebreak="-s.match_id",
            player_id="s.player_id",
            team_id="s.team_id",
            opponent_id="s.opposition_id",
            venue_id="s.venue_id",
            match_id="s.match_id",
            match_date="s.match_date",
            season="s.season",
            x1="round(s.bat_wpa, 3)",
            x2="round(s.bowl_wpa, 3)",
        )
    }
    FROM {WPA} s WHERE {clause}
    """


# Columns beside the value: (header, column, decimals, kind) where kind is "int", "num",
# "pct" or "text".
_CAREER_BAT = (("Inns", "sample", 0, "int"), ("Avg", "x2", 2, "num"), ("SR", "x3", 2, "num"))
_CAREER_BOWL = (
    ("Inns", "sample", 0, "int"),
    ("Wkts", "x1", 0, "int"),
    ("Avg", "x2", 2, "num"),
    ("Econ", "x3", 2, "num"),
)
_INNINGS_BAT = (("Balls", "x2", 0, "int"), ("4s", "x3", 0, "int"), ("6s", "x4", 0, "int"))
_INNINGS_BOWL = (("Balls", "x3", 0, "int"), ("Dots", "x4", 0, "int"))

LIMITED = frozenset({"T20", "ODI"})

RECORDS: tuple[RecordDef, ...] = (
    # ------------------------------------------------------------------ batting
    RecordDef(
        "most-runs",
        "batting",
        "Most runs",
        "career",
        False,
        _career_batting("sum(runs)"),
        _CAREER_BAT,
        unit="runs",
    ),
    RecordDef(
        "most-hundreds",
        "batting",
        "Most hundreds",
        "career",
        False,
        _career_batting(
            "count(*) FILTER (WHERE runs >= 100)", "count(*) FILTER (WHERE runs >= 100) > 0"
        ),
        (("Inns", "sample", 0, "int"), ("Runs", "x1", 0, "int"), ("HS", "x4", 0, "int")),
        unit="hundreds",
    ),
    RecordDef(
        "most-fifties",
        "batting",
        "Most fifties",
        "career",
        False,
        _career_batting(
            "count(*) FILTER (WHERE runs BETWEEN 50 AND 99)",
            "count(*) FILTER (WHERE runs BETWEEN 50 AND 99) > 0",
        ),
        (("Inns", "sample", 0, "int"), ("Runs", "x1", 0, "int")),
        unit="fifties",
        description="Scores of 50 to 99.",
    ),
    RecordDef(
        "most-matches",
        "batting",
        "Most appearances",
        "career",
        False,
        _appearances,
        unit="matches",
        description="Matches in a playing XI (substitutes included).",
    ),
    RecordDef(
        "best-batting-average",
        "batting",
        "Highest batting average",
        "career",
        False,
        _career_batting(
            "round(sum(runs) / nullif(count(*) FILTER (WHERE is_out), 0), 2)",
            "count(*) >= {q.batting_innings} AND count(*) FILTER (WHERE is_out) > 0",
            ties="-sum(runs)",
        ),
        (("Inns", "sample", 0, "int"), ("Runs", "x1", 0, "int"), ("SR", "x3", 2, "num")),
        qualification="batting_innings",
    ),
    RecordDef(
        "best-batting-strike-rate",
        "batting",
        "Highest career strike rate",
        "career",
        False,
        _career_batting(
            "round(100.0 * sum(runs) / nullif(sum(balls), 0), 2)",
            "sum(balls) >= {q.career_balls_faced}",
            ties="-sum(runs)",
        ),
        (("Inns", "sample", 0, "int"), ("Runs", "x1", 0, "int"), ("Avg", "x2", 2, "num")),
        qualification="career_balls_faced",
    ),
    RecordDef(
        "most-fours",
        "batting",
        "Most fours",
        "career",
        False,
        _career_batting("sum(fours)", "sum(fours) > 0"),
        _CAREER_BAT,
        unit="fours",
    ),
    RecordDef(
        "most-sixes",
        "batting",
        "Most sixes",
        "career",
        False,
        _career_batting("sum(sixes)", "sum(sixes) > 0"),
        _CAREER_BAT,
        unit="sixes",
    ),
    RecordDef(
        "most-ducks",
        "batting",
        "Most ducks",
        "career",
        False,
        _career_batting(
            "count(*) FILTER (WHERE runs = 0 AND is_out)",
            "count(*) FILTER (WHERE runs = 0 AND is_out) > 0",
            ties="-count(*)",
        ),
        (("Inns", "sample", 0, "int"), ("Runs", "x1", 0, "int")),
        unit="ducks",
    ),
    RecordDef(
        "highest-scores",
        "batting",
        "Highest scores",
        "innings",
        False,
        _batting_innings("s.runs", "s.runs > 0"),
        _INNINGS_BAT,
        unit="runs",
    ),
    RecordDef(
        "highest-strike-rate-innings",
        "batting",
        "Highest strike rate in an innings",
        "innings",
        False,
        _batting_innings(
            "round(100.0 * s.runs / s.balls, 2)",
            "s.balls >= {q.innings_balls_faced}",
            ties="-s.runs",
        ),
        (("Runs", "x1", 0, "int"), ("Balls", "x2", 0, "int"), ("6s", "x4", 0, "int")),
        qualification="innings_balls_faced",
    ),
    RecordDef(
        "most-sixes-in-an-innings",
        "batting",
        "Most sixes in an innings",
        "innings",
        False,
        _batting_innings("s.sixes", "s.sixes > 0"),
        (("Runs", "x1", 0, "int"), ("Balls", "x2", 0, "int")),
        unit="sixes",
    ),
    RecordDef(
        "fastest-fifties",
        "batting",
        "Fastest fifties",
        "innings",
        True,
        _batting_innings("ms.balls_to_50", "ms.balls_to_50 IS NOT NULL", ties="-s.runs"),
        (("Runs", "x1", 0, "int"), ("4s", "x3", 0, "int"), ("6s", "x4", 0, "int")),
        unit="balls",
        description="Fewest balls faced to reach 50, worked out ball by ball.",
    ),
    RecordDef(
        "fastest-hundreds",
        "batting",
        "Fastest hundreds",
        "innings",
        True,
        _batting_innings("ms.balls_to_100", "ms.balls_to_100 IS NOT NULL", ties="-s.runs"),
        (("Runs", "x1", 0, "int"), ("4s", "x3", 0, "int"), ("6s", "x4", 0, "int")),
        unit="balls",
        description="Fewest balls faced to reach 100, worked out ball by ball.",
    ),
    # ------------------------------------------------------------------ bowling
    RecordDef(
        "most-wickets",
        "bowling",
        "Most wickets",
        "career",
        False,
        _career_bowling("sum(wickets)", "sum(wickets) > 0"),
        (("Inns", "sample", 0, "int"), ("Avg", "x2", 2, "num"), ("Econ", "x3", 2, "num")),
        unit="wickets",
    ),
    RecordDef(
        "best-bowling-average",
        "bowling",
        "Lowest bowling average",
        "career",
        True,
        _career_bowling(
            "round(sum(runs) / nullif(sum(wickets), 0), 2)",
            "sum(wickets) >= {q.bowling_wickets}",
            ties="-sum(wickets)",
        ),
        _CAREER_BOWL,
        qualification="bowling_wickets",
    ),
    RecordDef(
        "best-bowling-strike-rate",
        "bowling",
        "Lowest bowling strike rate",
        "career",
        True,
        _career_bowling(
            "round(sum(balls) / nullif(sum(wickets), 0), 2)",
            "sum(wickets) >= {q.bowling_wickets}",
            ties="-sum(wickets)",
        ),
        _CAREER_BOWL,
        qualification="bowling_wickets",
        description="Balls per wicket.",
    ),
    RecordDef(
        "best-economy",
        "bowling",
        "Lowest career economy",
        "career",
        True,
        _career_bowling(
            "round(6.0 * sum(runs) / nullif(sum(balls), 0), 2)",
            "sum(balls) >= {q.career_balls_bowled}",
            ties="-sum(balls)",
        ),
        _CAREER_BOWL,
        qualification="career_balls_bowled",
    ),
    RecordDef(
        "most-five-wicket-innings",
        "bowling",
        "Most five-wicket innings",
        "career",
        False,
        _career_bowling(
            "count(*) FILTER (WHERE wickets >= 5)",
            "count(*) FILTER (WHERE wickets >= 5) > 0",
            ties="-sum(wickets)",
        ),
        _CAREER_BOWL,
        unit="five-fors",
    ),
    RecordDef(
        "most-four-wicket-innings",
        "bowling",
        "Most four-wicket innings",
        "career",
        False,
        _career_bowling(
            "count(*) FILTER (WHERE wickets >= 4)",
            "count(*) FILTER (WHERE wickets >= 4) > 0",
            ties="-sum(wickets)",
        ),
        _CAREER_BOWL,
        formats=frozenset({"T20"}),
        unit="four-fors",
        description="Innings of four wickets or more.",
    ),
    RecordDef(
        "best-bowling-figures",
        "bowling",
        "Best bowling figures",
        "innings",
        False,
        _bowling_innings("s.wickets", "s.wickets > 0"),
        _INNINGS_BOWL,
        unit="wickets",
        description="Most wickets in an innings, then fewest runs.",
    ),
    RecordDef(
        "best-economy-in-an-innings",
        "bowling",
        "Lowest economy in an innings",
        "innings",
        True,
        _bowling_innings(
            "round(6.0 * s.runs / s.balls, 2)",
            "s.balls >= {q.innings_balls_bowled}",
            ties="-s.wickets",
        ),
        (("Wkts", "x1", 0, "int"), ("Runs", "x2", 0, "int"), ("Balls", "x3", 0, "int")),
        formats=LIMITED,
        qualification="innings_balls_bowled",
    ),
    RecordDef(
        "most-dots-in-an-innings",
        "bowling",
        "Most dot balls in an innings",
        "innings",
        False,
        _bowling_innings("s.dots", "s.dots > 0"),
        (("Wkts", "x1", 0, "int"), ("Runs", "x2", 0, "int"), ("Balls", "x3", 0, "int")),
        unit="dots",
    ),
    # ------------------------------------------------------------------ fielding
    RecordDef(
        "most-catches",
        "fielding",
        "Most catches",
        "career",
        False,
        _fielding("sum(catches)"),
        (("Matches", "sample", 0, "int"),),
        unit="catches",
        description="Catches by fielders and keepers (Cricsheet doesn't mark who kept wicket).",
    ),
    RecordDef(
        "most-stumpings",
        "fielding",
        "Most stumpings",
        "career",
        False,
        _fielding("sum(stumpings)"),
        (("Matches", "sample", 0, "int"), ("Catches", "x1", 0, "int")),
        unit="stumpings",
    ),
    # ------------------------------------------------------------------ seasons
    RecordDef(
        "most-runs-in-a-season",
        "seasons",
        "Most runs in a season",
        "season",
        False,
        _season("bat"),
        (("Inns", "sample", 0, "int"), ("Avg", "x2", 2, "num")),
        unit="runs",
    ),
    RecordDef(
        "most-wickets-in-a-season",
        "seasons",
        "Most wickets in a season",
        "season",
        False,
        _season("bowl"),
        (("Inns", "sample", 0, "int"), ("Avg", "x2", 2, "num")),
        unit="wickets",
    ),
    # ------------------------------------------------------------------ partnerships
    RecordDef(
        "highest-partnerships",
        "partnerships",
        "Highest partnerships",
        "stand",
        False,
        _stands,
        (("Wkt", "x1", 0, "int"), ("Balls", "x4", 0, "int")),
        unit="runs",
        description="Runs added for a wicket, extras included; * unbroken.",
        extra_filters=("wicket",),
    ),
    # ------------------------------------------------------------------ teams
    RecordDef(
        "highest-totals",
        "teams",
        "Highest totals",
        "innings",
        False,
        _team_innings("s.runs", "TRUE", ties="s.legal_balls"),
        (("Wkts", "x2", 0, "int"), ("Balls", "x3", 0, "int")),
        unit="runs",
    ),
    RecordDef(
        "lowest-totals",
        "teams",
        "Lowest all-out totals",
        "innings",
        True,
        _team_innings("s.runs", "s.wickets >= 10", ties="-s.legal_balls"),
        (("Balls", "x3", 0, "int"),),
        unit="runs",
        description="Innings with ten wickets down.",
    ),
    RecordDef(
        "highest-chases",
        "teams",
        "Highest successful chases",
        "innings",
        False,
        _team_innings(
            "s.runs",
            "s.won AND s.innings_no = s.last_innings AND s.innings_no > 1 AND s.win_method IS NULL",
            ties="s.legal_balls",
        ),
        (("Wkts", "x2", 0, "int"), ("Target", "x4", 0, "int")),
        unit="runs",
        description="Totals made batting last to win, where the target wasn't revised.",
    ),
    RecordDef(
        "biggest-wins-by-runs",
        "teams",
        "Biggest wins by runs",
        "match",
        False,
        _wins(
            "s.win_by_runs",
            "s.win_by_runs IS NOT NULL AND s.win_by_innings IS NULL",
            ties="-s.match_id",
        ),
        (),
        unit="runs",
        description="Results decided without a revised target.",
    ),
    RecordDef(
        "biggest-wins-by-wickets",
        "teams",
        "Biggest wins by wickets",
        "match",
        False,
        _wins(
            "s.win_by_wickets",
            "s.win_by_wickets IS NOT NULL",
            ties="-coalesce(s.balls_to_spare, 0)",
        ),
        (("Balls to spare", "x3", 0, "int"),),
        unit="wickets",
        test_columns=(),
        description="Then most balls to spare; results decided without a revised target.",
    ),
    RecordDef(
        "biggest-innings-wins",
        "teams",
        "Biggest wins by an innings",
        "match",
        False,
        _wins("s.win_by_runs", "s.win_by_innings IS NOT NULL", ties="-s.match_id"),
        (),
        formats=frozenset({"Test"}),
        unit="runs",
        description="By an innings and the most runs.",
    ),
    # ------------------------------------------------------------------ ball by ball
    RecordDef(
        "most-runs-in-an-over",
        "ball_by_ball",
        "Most runs in an over",
        "over",
        False,
        _overs,
        (("Over", "x1", 0, "int"), ("Wkts", "x2", 0, "int")),
        unit="runs",
        roles=("bowler", None),
        description="Runs off one over, extras included, by the side batting, with the "
        "bowler who bowled it.",
    ),
    RecordDef(
        "biggest-win-probability-swings",
        "ball_by_ball",
        "Biggest swings from one ball",
        "match",
        False,
        _swings,
        (("Before", "x1", 1, "pct"), ("After", "x2", 1, "pct")),
        needs="match_swings",
        model=True,
        unit="points",
        roles=("batter", "bowler"),
        description="The largest change in a side's chance of winning from a single ball, one per "
        "match (results decided by a revised target left out).",
    ),
    RecordDef(
        "highest-wpa-in-a-match",
        "ball_by_ball",
        "Most win probability added in a match",
        "match",
        False,
        _wpa,
        (("Batting", "x1", 3, "num"), ("Bowling", "x2", 3, "num")),
        needs="player_wpa",
        model=True,
        unit="wins",
        description="The sum of every change in the side's chance of winning on the player's "
        "balls.",
    ),
)

BY_KEY = {r.key: r for r in RECORDS}


def available(db: Database, record: RecordDef) -> bool:
    return db.match_format in record.formats and (
        record.needs is None or db.has_table(record.needs)
    )


def has_record_tables(db: Database) -> bool:
    return db.has_table("partnerships") and db.has_table("batting_milestones")


def ranked(
    db: Database,
    record: RecordDef,
    filters: Filters,
    qualification: Qualification,
    *,
    wicket: int | None = None,
    limit: int,
    offset: int = 0,
) -> list[Row]:
    """A page of the record's entries, ranked (equal values share a rank), with names."""
    clause, params = where(filters, _SOURCE)
    if wicket is not None and "wicket" in record.extra_filters:
        clause += " AND s.wicket = ?"
        params.append(wicket)
    # Only Tests have declarations and innings wins (the columns exist in Test databases alone).
    test = db.match_format == "Test"
    inner = (
        record.sql(clause, qualification)
        .replace("{declared}", "coalesce(i.declared, FALSE)" if test else "FALSE")
        .replace("{win_by_innings}", "m.win_by_innings" if test else "NULL::INTEGER")
    )
    direction = "ASC" if record.ascending else "DESC"
    return db.rows(
        f"""
        WITH r AS ({inner}),
        k AS (
            SELECT r.*,
                   rank() OVER (ORDER BY r.value {direction})::INTEGER AS rank,
                   (count(*) OVER (PARTITION BY r.value) > 1) AS tied,
                   count(*) OVER ()::INTEGER AS total
            FROM r WHERE r.value IS NOT NULL
        )
        SELECT k.*,
               (count(*) FILTER (WHERE k.rank = 1) OVER ())::INTEGER AS first_count,
               coalesce(p1.full_name, p1.name) AS player_name,
               coalesce(p2.full_name, p2.name) AS partner_name,
               ft.name AS team_name, ft.primary_color AS team_color,
               fo.name AS opponent_name, fo.primary_color AS opponent_color,
               v.name AS venue_name
        FROM k
        LEFT JOIN players p1 ON p1.player_id = k.player_id
        LEFT JOIN players p2 ON p2.player_id = k.partner_id
        LEFT JOIN franchises ft ON ft.franchise_id = k.team_id
        LEFT JOIN franchises fo ON fo.franchise_id = k.opponent_id
        LEFT JOIN venues v ON v.venue_id = k.venue_id
        ORDER BY k.value {direction}, k.tiebreak, k.match_date, k.player_id
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    )
