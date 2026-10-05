"""The multi-competition warehouse: every league and format in one build."""

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_pipelines.raw import RawSnapshot
from criciq_pipelines.reference import load_competitions
from criciq_pipelines.validation import validate
from criciq_pipelines.warehouse import BuildInputs, build_warehouse


@pytest.fixture(scope="module")
def con(fixture_full_warehouse: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_full_warehouse), read_only=True)
    yield connection
    connection.close()


def _one(con: duckdb.DuckDBPyConnection, sql: str, params: list[object] | None = None) -> tuple:  # type: ignore[type-arg]
    row = con.execute(sql, params or []).fetchone()
    assert row is not None
    return row


def test_matches_join_their_competition(con: duckdb.DuckDBPyConnection) -> None:
    expected = {
        1181768: "IPL",
        1386137: "BBL",
        1211672: "PSL",
        635216: "CPL",
        1343973: "SA20",
        951373: "T20I",
        1144530: "ODI",
        215010: "TEST",
    }
    rows = dict(
        con.execute(
            "SELECT match_id, competition_id FROM matches WHERE match_id IN ?", [list(expected)]
        ).fetchall()
    )
    assert rows == expected
    counts = dict(
        con.execute("SELECT competition_id, count(*) FROM matches GROUP BY ALL").fetchall()
    )
    assert counts["IPL"] == 14
    assert sum(counts.values()) == 30  # 31 fixtures, one quarantined


def test_classification_rules() -> None:
    config = load_competitions()
    women = {"gender": "female", "match_type": "T20", "team_type": "international"}
    county = {"gender": "male", "match_type": "MDM", "team_type": "club"}
    assert config.classify(women) is None
    assert config.classify(county) is None
    league = {"gender": "male", "match_type": "T20", "team_type": "club", "event_name": "SA20"}
    assert config.classify(league).id == "SA20"  # type: ignore[union-attr]


def test_seasons_follow_labels_or_the_calendar(con: duckdb.DuckDBPyConnection) -> None:
    # BBL 2023/24 ended in January 2024: it is BBL 2024.
    assert _one(
        con,
        "SELECT s.season_id, s.cricsheet_label FROM matches m JOIN seasons s USING (season_id) "
        "WHERE m.match_id = 1386137",
    ) == ("BBL-2024", "2023/24")
    # The PSL plays within a calendar year: its November 2020 playoffs, labelled
    # "2020/21" by Cricsheet, belong to PSL 2020; PSL 2021 resumed in June.
    seasons = con.execute(
        "SELECT match_id, season_id FROM matches WHERE match_id IN (1211672, 1247044) "
        "ORDER BY 1"
    ).fetchall()
    assert seasons == [(1211672, "PSL-2020"), (1247044, "PSL-2021")]
    # Internationals use the calendar year of the first day.
    assert _one(con, "SELECT season_id FROM matches WHERE match_id = 1223871") == ("TEST-2021",)


def test_teams_are_identities_across_formats(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        """
        SELECT DISTINCT ts.team_season_id, ts.team_id, t.team_type
        FROM matches m JOIN team_seasons ts ON ts.team_season_id IN (m.team1_id, m.team2_id)
        JOIN teams t USING (team_id)
        WHERE m.match_id IN (1144530, 951373) ORDER BY 1
        """
    ).fetchall()
    assert ("ODI-ENG-2019", "ENG", "national") in rows
    assert ("T20I-ENG-2016", "ENG", "national") in rows
    # A renamed club stays one team: Trinidad & Tobago Red Steel is TKR.
    assert _one(
        con,
        "SELECT ts.team_id, ts.display_name FROM team_seasons ts "
        "WHERE ts.display_name = 'Trinidad & Tobago Red Steel'",
    ) == ("TKR", "Trinidad & Tobago Red Steel")


def test_test_match_results(con: duckdb.DuckDBPyConnection) -> None:
    # Sydney 2021: Australia declared, India batted out a draw.
    outcome, winner, scheduled = _one(
        con, "SELECT outcome_type, winner_id, scheduled_overs FROM matches WHERE match_id = 1223871"
    )
    assert (outcome, winner, scheduled) == ("draw", None, None)
    assert _one(
        con, "SELECT declared FROM innings WHERE match_id = 1223871 AND innings_no = 3"
    ) == (True,)
    # A follow-on: the side batting second bats again and loses by an innings.
    follow_on = con.execute(
        "SELECT innings_no FROM innings WHERE match_id = 1122310 AND follow_on"
    ).fetchall()
    assert follow_on == [(3,)]
    assert _one(con, "SELECT win_by_innings FROM matches WHERE match_id = 1122310") == (1,)
    assert _one(con, "SELECT days FROM matches WHERE match_id = 215010") == (4,)


def test_penalty_runs_count_toward_the_total(con: duckdb.DuckDBPyConnection) -> None:
    runs, penalty, from_balls = _one(
        con,
        """
        SELECT i.runs, i.penalty_runs, (SELECT sum(runs_total) FROM deliveries d
                                        WHERE d.match_id = i.match_id
                                          AND d.innings_no = i.innings_no)
        FROM innings i WHERE i.match_id = 1386128 AND i.penalty_runs > 0
        """,
    )
    assert penalty == 5
    assert runs == from_balls + penalty


def test_ties_settled_by_super_over_or_bowl_out(con: duckdb.DuckDBPyConnection) -> None:
    assert _one(
        con,
        """
        SELECT m.outcome_type, m.decided_by_super_over, ts.team_id FROM matches m
        JOIN team_seasons ts ON ts.team_season_id = m.winner_id WHERE m.match_id = 1144530
        """,
    ) == ("tie", True, "ENG")
    assert _one(
        con,
        """
        SELECT m.outcome_type, m.decided_by_bowl_out, ts.team_id FROM matches m
        JOIN team_seasons ts ON ts.team_season_id = m.winner_id WHERE m.match_id = 287862
        """,
    ) == ("tie", True, "IND")


def test_source_errors_are_quarantined(con: duckdb.DuckDBPyConnection) -> None:
    assert con.execute("SELECT match_id, rule FROM quarantine").fetchall() == [
        (1229824, "player_on_both_sides")
    ]
    assert _one(con, "SELECT count(*) FROM matches WHERE match_id = 1229824") == (0,)


def test_grounds_outside_the_curated_list_get_countries(con: duckdb.DuckDBPyConnection) -> None:
    added = con.execute("SELECT venue_id, country FROM venues WHERE NOT is_curated").fetchall()
    assert added
    assert all(country for _, country in added)
    # International matches at curated grounds map onto them.
    assert _one(
        con,
        "SELECT v.is_curated FROM matches m JOIN venues v USING (venue_id) "
        "WHERE m.match_id = 1343973",
    ) == (True,)


def test_quirks_outside_curated_competitions_are_notes(fixture_full_warehouse: Path) -> None:
    report = validate(fixture_full_warehouse)
    eleven = next(c for c in report.checks if c.id == "eleven_players_per_side")
    assert eleven.passed
    assert eleven.notes.get("T20I", 0) >= 1  # the side of ten
    assert report.passed


def test_a_selection_builds_only_those_competitions(
    fixture_snapshot: RawSnapshot, fixture_interim: Path, tmp_path: Path
) -> None:
    target = tmp_path / "ipl_only.duckdb"
    build_warehouse(
        BuildInputs(fixture_interim, fixture_snapshot.people, "test", competitions=("IPL",)),
        target,
    )
    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute("SELECT DISTINCT competition_id FROM matches").fetchall() == [
            ("IPL",)
        ]
    finally:
        connection.close()


def test_the_ipl_copy_has_the_v1_shape(fixture_warehouse: Path) -> None:
    connection = duckdb.connect(str(fixture_warehouse), read_only=True)
    try:
        tables = {r[0] for r in connection.execute("SHOW TABLES").fetchall()}
        assert "franchises" in tables
        assert "teams" not in tables
        assert connection.execute("SELECT DISTINCT competition_id FROM matches").fetchall() == [
            ("IPL",)
        ]
        columns = [r[0] for r in connection.execute("DESCRIBE matches").fetchall()]
        assert "global_order" not in columns
        assert columns[-1] == "cricsheet_version"
    finally:
        connection.close()
