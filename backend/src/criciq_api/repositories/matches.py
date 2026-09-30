"""SQL for matches, scorecards and timelines (serving database)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from criciq_api.db import Database, Row


@dataclass(frozen=True)
class MatchFilters:
    season: int | None = None
    team: str | None = None
    venue: str | None = None
    playoffs: bool | None = None
    sort: Literal["latest", "oldest"] = "latest"


def list_matches(
    db: Database, filters: MatchFilters, *, limit: int, offset: int
) -> tuple[list[Row], int]:
    clauses: list[str] = []
    params: list[object] = []
    if filters.season is not None:
        clauses.append("season = ?")
        params.append(filters.season)
    if filters.team is not None:
        clauses.append("(team_a_short = ? OR team_b_short = ?)")
        params.extend([filters.team, filters.team])
    if filters.venue is not None:
        clauses.append("venue_id = ?")
        params.append(filters.venue)
    if filters.playoffs is not None:
        clauses.append("is_playoff = ?")
        params.append(filters.playoffs)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    direction = "DESC" if filters.sort == "latest" else "ASC"
    total = int(db.scalar(f"SELECT count(*) FROM match_summaries {where}", params))
    rows = db.rows(
        f"SELECT * FROM match_summaries {where} ORDER BY match_order {direction} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return rows, total


def get_summary(db: Database, match_id: int) -> Row | None:
    return db.row("SELECT * FROM match_summaries WHERE match_id = ?", [match_id])


def get_team_refs(db: Database, match_id: int) -> list[Row]:
    return db.rows(
        """
        SELECT t.team_season_id, f.franchise_id, t.display_name AS name, f.primary_color AS color
        FROM matches m
        JOIN team_seasons t ON t.team_season_id IN (m.team1_id, m.team2_id)
        JOIN franchises f USING (franchise_id)
        WHERE m.match_id = ?
        """,
        [match_id],
    )


def get_innings(db: Database, match_id: int) -> list[Row]:
    return db.rows(
        """
        SELECT i.*,
               CASE WHEN i.is_super_over THEN m.balls_per_over
                    WHEN i.target_balls IS NOT NULL THEN i.target_balls
                    ELSE m.scheduled_overs * m.balls_per_over END AS max_balls,
               e.byes, e.legbyes, e.wides, e.noballs, e.penalty
        FROM innings i JOIN matches m USING (match_id)
        LEFT JOIN (
            SELECT innings_no, sum(extras_byes) AS byes, sum(extras_legbyes) AS legbyes,
                   sum(extras_wides) AS wides, sum(extras_noballs) AS noballs,
                   sum(extras_penalty) AS penalty
            FROM deliveries WHERE match_id = ? GROUP BY innings_no
        ) e USING (innings_no)
        WHERE i.match_id = ? ORDER BY i.innings_no
        """,
        [match_id, match_id],
    )


def get_batting(db: Database, match_id: int) -> list[Row]:
    """One row per batter who came to the crease, in batting order."""
    return db.rows(
        """
        WITH arrivals AS (
            -- Order of arrival: striker before non-striker on the first ball.
            SELECT innings_no, player_id, min(seq_no * 2 + priority) AS arrival
            FROM (SELECT innings_no, seq_no, batter_id AS player_id, 0 AS priority
                  FROM deliveries WHERE match_id = ?
                  UNION ALL
                  SELECT innings_no, seq_no, non_striker_id, 1
                  FROM deliveries WHERE match_id = ?)
            GROUP BY ALL
        ),
        batting AS (
            SELECT innings_no, batter_id AS player_id, sum(runs_batter) AS runs,
                   count(*) FILTER (WHERE extras_wides = 0) AS balls,
                   sum(is_four::INT) AS fours, sum(is_six::INT) AS sixes
            FROM deliveries WHERE match_id = ? GROUP BY ALL
        ),
        outs AS (
            -- A retired-hurt batter may return and be dismissed later: keep the last event.
            SELECT innings_no, player_out_id AS player_id,
                   arg_max(kind, seq_no) AS kind,
                   arg_max(bowler_id, seq_no) AS bowler_id,
                   arg_max(fielder_ids, seq_no) AS fielder_ids,
                   arg_max(fielder_is_substitute, seq_no) AS fielder_is_substitute,
                   arg_max(is_dismissal, seq_no) AS is_dismissal
            FROM wickets WHERE match_id = ? GROUP BY ALL
        )
        SELECT a.innings_no, a.player_id, p.name,
               coalesce(b.runs, 0) AS runs, coalesce(b.balls, 0) AS balls,
               coalesce(b.fours, 0) AS fours, coalesce(b.sixes, 0) AS sixes,
               o.kind, bw.name AS bowler_name,
               o.fielder_ids,
               o.fielder_is_substitute, coalesce(o.is_dismissal, false) AS is_out
        FROM arrivals a
        JOIN players p ON p.player_id = a.player_id
        LEFT JOIN batting b ON b.innings_no = a.innings_no AND b.player_id = a.player_id
        LEFT JOIN outs o ON o.innings_no = a.innings_no AND o.player_id = a.player_id
        LEFT JOIN players bw ON bw.player_id = o.bowler_id
        ORDER BY a.innings_no, a.arrival
        """,
        [match_id, match_id, match_id, match_id],
    )


def get_squads(db: Database, match_id: int) -> list[Row]:
    return db.rows(
        """
        SELECT mp.team_season_id, mp.player_id, p.name, mp.list_position
        FROM match_players mp JOIN players p USING (player_id)
        WHERE mp.match_id = ? ORDER BY mp.team_season_id, mp.list_position
        """,
        [match_id],
    )


def get_bowling(db: Database, match_id: int) -> list[Row]:
    """Bowling figures per innings, in order of first over bowled.

    Runs conceded exclude byes, leg-byes and penalties, per scoring convention.
    """
    return db.rows(
        """
        WITH d AS (
            SELECT innings_no, seq_no, over_no, bowler_id, is_legal,
                   runs_batter + extras_wides + extras_noballs AS conceded,
                   extras_wides > 0 AS is_wide, extras_noballs > 0 AS is_noball
            FROM deliveries WHERE match_id = ?
        ),
        overs AS (
            SELECT innings_no, bowler_id, over_no,
                   count(*) FILTER (WHERE is_legal) AS legal, sum(conceded) AS conceded
            FROM d GROUP BY ALL
        ),
        wkts AS (
            SELECT innings_no, bowler_id, count(*) AS wickets
            FROM wickets WHERE match_id = ? AND bowler_credited GROUP BY ALL
        )
        SELECT d.innings_no, d.bowler_id AS player_id, p.name,
               count(*) FILTER (WHERE d.is_legal) AS legal_balls,
               sum(d.conceded) AS runs,
               coalesce(any_value(w.wickets), 0) AS wickets,
               count(*) FILTER (WHERE d.is_wide) AS wides,
               count(*) FILTER (WHERE d.is_noball) AS noballs,
               (SELECT count(*) FROM overs o
                WHERE o.innings_no = d.innings_no AND o.bowler_id = d.bowler_id
                  AND o.legal >= 6 AND o.conceded = 0) AS maidens,
               min(d.seq_no) AS first_ball
        FROM d
        JOIN players p ON p.player_id = d.bowler_id
        LEFT JOIN wkts w ON w.innings_no = d.innings_no AND w.bowler_id = d.bowler_id
        GROUP BY d.innings_no, d.bowler_id, p.name
        ORDER BY d.innings_no, first_ball
        """,
        [match_id, match_id],
    )


def get_fall_of_wickets(db: Database, match_id: int) -> list[Row]:
    return db.rows(
        """
        SELECT d.innings_no, d.team_wickets AS wicket, d.team_runs AS runs,
               d.legal_ball_no, w.player_out_id AS player_id, p.name
        FROM wickets w
        JOIN deliveries d USING (match_id, innings_no, seq_no)
        JOIN players p ON p.player_id = w.player_out_id
        WHERE w.match_id = ? AND w.is_dismissal
        ORDER BY d.innings_no, d.seq_no
        """,
        [match_id],
    )


def get_deliveries(db: Database, match_id: int) -> list[Row]:
    return db.rows(
        """
        SELECT d.*, w.player_out_id, w.kind AS wicket_kind, w.bowler_credited,
               w.is_dismissal, w.fielder_ids
        FROM deliveries d
        LEFT JOIN wickets w USING (match_id, innings_no, seq_no)
        WHERE d.match_id = ?
        ORDER BY d.innings_no, d.seq_no
        """,
        [match_id],
    )


def get_substitutions(db: Database, match_id: int) -> list[Row]:
    return db.rows(
        """
        SELECT innings_no, seq_no, team_season_id, player_in_id, player_out_id, reason
        FROM substitutions WHERE match_id = ? AND kind = 'match'
        ORDER BY innings_no, seq_no, sub_no
        """,
        [match_id],
    )


def get_model(db: Database, name: str) -> Row | None:
    """A model behind stored predictions, with its `info` decoded (None if never scored)."""
    if not db.has_table("models"):
        return None
    row = db.row("SELECT * FROM models WHERE name = ?", [name])
    if row is None:
        return None
    info = row.pop("info")
    return {**row, **(json.loads(info) if isinstance(info, str) else info)}


def get_score_projections(db: Database, match_id: int) -> list[Row]:
    """First-innings total quantiles after every ball; seq_no 0 = before the first ball."""
    if not db.has_table("score_projections"):
        return []
    return db.rows(
        "SELECT seq_no, quantiles FROM score_projections WHERE match_id = ? ORDER BY seq_no",
        [match_id],
    )


def get_win_probabilities(db: Database, match_id: int) -> list[Row]:
    """Side-batting-first win probability after every ball; seq_no 0 = before the innings."""
    if not db.has_table("wp_predictions"):
        return []
    return db.rows(
        """
        SELECT innings_no, seq_no, wp_team_a, factors
        FROM wp_predictions WHERE match_id = ? ORDER BY innings_no, seq_no
        """,
        [match_id],
    )


def get_match_people(db: Database, match_id: int) -> list[Row]:
    """Everyone referenced by a match: squads, substitute fielders, replacements."""
    return db.rows(
        """
        SELECT p.player_id, p.name, p.full_name FROM players p
        WHERE p.player_id IN (
            SELECT player_id FROM match_players WHERE match_id = ?
            UNION SELECT unnest(fielder_ids) FROM wickets WHERE match_id = ?
            UNION SELECT player_in_id FROM substitutions WHERE match_id = ?
            UNION SELECT player_out_id FROM substitutions WHERE match_id = ?
        )
        """,
        [match_id, match_id, match_id, match_id],
    )
