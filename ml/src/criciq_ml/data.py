"""Load the warehouse tables the models need into memory.

Everything downstream (features, training, scoring) works on an :class:`Inputs`
bundle rather than on the database, so tests can truncate or tamper with
history and prove that features only ever look backwards in time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import duckdb
import pandas as pd

from criciq_core.phases import check_model_format, model_phases

# ``season`` is the competition's season; ``year`` the calendar year of the
# match, which the training splits use (date cut-offs on 1 January).
MATCHES_SQL = """
SELECT m.match_id, m.match_order, s.year AS season, m.match_date, m.venue_id,
       m.outcome_type, m.winner_id, m.scheduled_overs, m.balls_per_over,
       m.competition_id, year(m.match_date)::INTEGER AS year
FROM matches m JOIN seasons s USING (season_id)
ORDER BY m.match_order
"""

# A chase's target, where Cricsheet omits it (some T20Is), is the first-innings
# total plus one: the rule when no rain rule applied.
TARGET_SQL = """
coalesce(i.target_runs,
         CASE WHEN i.innings_no = 2 AND NOT i.is_super_over
              THEN (SELECT f.runs + 1 FROM innings f
                    WHERE f.match_id = i.match_id AND f.innings_no = 1) END)
"""


def max_balls_sql() -> str:
    """The balls an innings could last: its revised allocation (a rain-shortened
    chase), else the scheduled overs, never more than the models' format allows
    (Cricsheet records a few T20Is as 50-over matches). A Test innings has no limit."""
    if model_phases().overs is None:
        return "NULL::INTEGER"
    return f"""
    least(coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over),
          {model_phases().limit} * m.balls_per_over)
    """


def innings_sql() -> str:
    return f"""
    SELECT i.match_id, i.innings_no, i.batting_team_id, i.bowling_team_id, i.is_super_over,
           {TARGET_SQL} AS target_runs,
           {max_balls_sql()} AS max_balls
    FROM innings i JOIN matches m USING (match_id)
    ORDER BY m.match_order, i.innings_no
    """


DELIVERIES_SQL = """
WITH outs AS (
    SELECT match_id, innings_no, seq_no,
           list(player_out_id ORDER BY wicket_no) FILTER (WHERE is_dismissal) AS out_ids,
           count(*) FILTER (WHERE bowler_credited) AS bowler_wickets
    FROM wickets GROUP BY ALL
)
SELECT d.match_id, d.innings_no, d.seq_no, d.over_no, d.legal_ball_no, d.is_legal,
       d.batter_id, d.non_striker_id, d.bowler_id,
       d.runs_batter, d.runs_total, d.extras_wides, d.extras_noballs,
       d.team_runs, d.team_wickets,
       coalesce(o.out_ids, []::VARCHAR[]) AS out_ids,
       coalesce(o.bowler_wickets, 0)::INTEGER AS bowler_wickets
FROM deliveries d
JOIN matches m USING (match_id)
LEFT JOIN outs o USING (match_id, innings_no, seq_no)
ORDER BY m.match_order, d.innings_no, d.seq_no
"""

FORMATS_SQL = """
SELECT DISTINCT c.format
FROM matches m JOIN competitions c ON c.competition_id = m.competition_id
"""

SQUADS_SQL = """
SELECT match_id, team_season_id, player_id, selection
FROM match_players ORDER BY match_id, team_season_id, list_position
"""

SUBSTITUTIONS_SQL = """
SELECT match_id, innings_no, seq_no, team_season_id, player_in_id, player_out_id
FROM substitutions
WHERE kind = 'match' AND player_in_id IS NOT NULL
ORDER BY match_id, innings_no, seq_no, sub_no
"""


def check_formats(con: duckdb.DuckDBPyConnection) -> None:
    """Refuse a database whose matches are not in the models' format."""
    check_model_format(f for (f,) in con.execute(FORMATS_SQL).fetchall())


@dataclass(frozen=True)
class Inputs:
    matches: pd.DataFrame
    innings: pd.DataFrame
    deliveries: pd.DataFrame
    squads: pd.DataFrame
    substitutions: pd.DataFrame
    data_version: str

    def only(self, competitions: set[str] | frozenset[str]) -> Inputs:
        """The matches of some competitions (of a pooled copy)."""
        kept = self.matches[self.matches["competition_id"].isin(competitions)]
        ids = set(kept["match_id"])
        return replace(
            self,
            matches=kept,
            innings=self.innings[self.innings["match_id"].isin(ids)],
            deliveries=self.deliveries[self.deliveries["match_id"].isin(ids)],
            squads=self.squads[self.squads["match_id"].isin(ids)],
            substitutions=self.substitutions[self.substitutions["match_id"].isin(ids)],
        )

    def up_to(self, match_order: int) -> Inputs:
        """History as it stood after ``match_order`` (later matches removed)."""
        kept = self.matches[self.matches["match_order"] <= match_order]
        ids = set(kept["match_id"])
        return replace(
            self,
            matches=kept,
            innings=self.innings[self.innings["match_id"].isin(ids)],
            deliveries=self.deliveries[self.deliveries["match_id"].isin(ids)],
            squads=self.squads[self.squads["match_id"].isin(ids)],
            substitutions=self.substitutions[self.substitutions["match_id"].isin(ids)],
        )


def load_inputs(database: Path) -> Inputs:
    """Read from a warehouse or serving database (both carry these tables)."""
    con = duckdb.connect(str(database), read_only=True)
    try:
        check_formats(con)
        version = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
        return Inputs(
            matches=con.execute(MATCHES_SQL).df(),
            innings=con.execute(innings_sql()).df(),
            deliveries=con.execute(DELIVERIES_SQL).df(),
            squads=con.execute(SQUADS_SQL).df(),
            substitutions=con.execute(SUBSTITUTIONS_SQL).df(),
            data_version=str(version[0]) if version else "unknown",
        )
    finally:
        con.close()
