"""How a match summary words its result (criciq_pipelines.export.MATCH_SUMMARIES_SQL)."""

from __future__ import annotations

import duckdb
import pytest

from criciq_pipelines.export import MATCH_SUMMARIES_SQL

SCHEMA = """
CREATE TABLE seasons (season_id VARCHAR, year INTEGER);
CREATE TABLE venues (venue_id VARCHAR, name VARCHAR, city VARCHAR);
CREATE TABLE franchises (franchise_id VARCHAR, primary_color VARCHAR);
CREATE TABLE team_seasons (team_season_id VARCHAR, display_name VARCHAR, franchise_id VARCHAR);
CREATE TABLE players (player_id VARCHAR, name VARCHAR, full_name VARCHAR);
CREATE TABLE matches (
    match_id BIGINT, match_order INTEGER, season_id VARCHAR, match_date DATE,
    match_number INTEGER, stage VARCHAR, is_playoff BOOLEAN, venue_id VARCHAR,
    team1_id VARCHAR, team2_id VARCHAR, toss_winner_id VARCHAR, toss_decision VARCHAR,
    outcome_type VARCHAR, winner_id VARCHAR, win_by_runs INTEGER, win_by_wickets INTEGER,
    win_method VARCHAR, decided_by_super_over BOOLEAN, player_of_match_ids VARCHAR[]
);
CREATE TABLE innings (
    match_id BIGINT, innings_no INTEGER, batting_team_id VARCHAR, runs INTEGER,
    wickets INTEGER, legal_balls INTEGER, target_runs INTEGER, target_balls INTEGER,
    is_super_over BOOLEAN
);
INSERT INTO seasons VALUES ('S', 2007);
INSERT INTO venues VALUES ('V', 'Ground', 'City');
INSERT INTO franchises VALUES ('IND', '#000000'), ('PAK', '#111111');
INSERT INTO team_seasons VALUES ('A', 'India', 'IND'), ('B', 'Pakistan', 'PAK');
"""


@pytest.mark.parametrize(
    ("winner", "super_over", "method", "expected"),
    [
        ("A", True, None, "Match tied (India won the super over)"),
        # Before super overs, ties were settled by a bowl-out.
        ("A", False, None, "Match tied (India won the bowl-out)"),
        (None, False, None, "Match tied"),
        (None, False, "D/L", "Match tied (D/L)"),
    ],
)
def test_ties_are_worded_by_how_they_were_settled(
    winner: str | None, super_over: bool, method: str | None, expected: str
) -> None:
    con = duckdb.connect()
    con.execute(SCHEMA)
    con.execute(
        """
        INSERT INTO matches VALUES (1, 1, 'S', DATE '2007-09-14', 1, 'League', false, 'V',
            'A', 'B', 'A', 'bat', 'tie', ?, NULL, NULL, ?, ?, [])
        """,
        [winner, method, super_over],
    )
    con.execute(
        "INSERT INTO innings VALUES (1, 1, 'A', 141, 9, 120, NULL, NULL, false),"
        " (1, 2, 'B', 141, 7, 120, 142, 120, false)"
    )
    con.execute(MATCH_SUMMARIES_SQL)
    assert con.execute("SELECT result_text FROM match_summaries").fetchone() == (expected,)


@pytest.mark.parametrize(
    ("super_overs", "expected"),
    [
        ([(3, "A", 11), (4, "B", 9)], "Match tied (India won the super over)"),
        # A tied super over settled on boundaries (the 2019 World Cup final).
        (
            [(3, "B", 15), (4, "A", 15)],
            "Match tied (India won on boundaries after a tied super over)",
        ),
        # A second super over after a tied first one decides it.
        (
            [(3, "A", 6), (4, "B", 6), (5, "B", 11), (6, "A", 12)],
            "Match tied (India won the super over)",
        ),
    ],
)
def test_a_super_over_tie_is_worded_by_how_it_ended(
    super_overs: list[tuple[int, str, int]], expected: str
) -> None:
    con = duckdb.connect()
    con.execute(SCHEMA)
    con.execute(
        """
        INSERT INTO matches VALUES (1, 1, 'S', DATE '2019-07-14', 1, 'Final', true, 'V',
            'A', 'B', 'A', 'bat', 'tie', 'A', NULL, NULL, NULL, true, [])
        """
    )
    con.execute(
        "INSERT INTO innings VALUES (1, 1, 'A', 241, 8, 300, NULL, NULL, false),"
        " (1, 2, 'B', 241, 10, 300, 242, 300, false)"
    )
    for innings_no, team, runs in super_overs:
        con.execute(
            "INSERT INTO innings VALUES (1, ?, ?, ?, 0, 6, NULL, NULL, true)",
            [innings_no, team, runs],
        )
    con.execute(MATCH_SUMMARIES_SQL)
    assert con.execute("SELECT result_text FROM match_summaries").fetchone() == (expected,)
