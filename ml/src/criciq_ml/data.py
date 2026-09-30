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

MATCHES_SQL = """
SELECT m.match_id, m.match_order, s.year AS season, m.match_date, m.venue_id,
       m.outcome_type, m.winner_id, m.scheduled_overs, m.balls_per_over
FROM matches m JOIN seasons s USING (season_id)
ORDER BY m.match_order
"""

INNINGS_SQL = """
SELECT i.match_id, i.innings_no, i.batting_team_id, i.bowling_team_id, i.is_super_over,
       i.target_runs,
       coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over) AS max_balls
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


@dataclass(frozen=True)
class Inputs:
    matches: pd.DataFrame
    innings: pd.DataFrame
    deliveries: pd.DataFrame
    squads: pd.DataFrame
    substitutions: pd.DataFrame
    data_version: str

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
        version = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
        return Inputs(
            matches=con.execute(MATCHES_SQL).df(),
            innings=con.execute(INNINGS_SQL).df(),
            deliveries=con.execute(DELIVERIES_SQL).df(),
            squads=con.execute(SQUADS_SQL).df(),
            substitutions=con.execute(SUBSTITUTIONS_SQL).df(),
            data_version=str(version[0]) if version else "unknown",
        )
    finally:
        con.close()
