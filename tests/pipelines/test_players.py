"""Player Lab tables: recounted independently from the raw Cricsheet JSON,
checked against known scorecards, and checked for internal consistency."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from tests.conftest import MATCHES_DIR, load_match

CREDITED = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}
NOT_OUT = {"retired hurt", "retired not out"}

Lines = dict[tuple[int, int, str], Counter[str]]


@pytest.fixture(scope="module")
def con(fixture_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_serving_db), read_only=True)
    yield connection
    connection.close()


def _names(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    return dict(con.execute("SELECT player_id, name FROM players").fetchall())


def _recount() -> tuple[Lines, Lines]:
    """Batting and bowling lines per (match, innings, registry name), straight from JSON."""
    batting: Lines = defaultdict(Counter)
    bowling: Lines = defaultdict(Counter)
    for path in sorted(MATCHES_DIR.glob("*.json")):
        match_id = int(path.stem)
        for innings_no, innings in enumerate(load_match(match_id).get("innings", []), start=1):
            if innings.get("super_over"):
                continue
            for over in innings["overs"]:
                for d in over["deliveries"]:
                    extras = d.get("extras", {})
                    runs = d["runs"]["batter"]
                    bat = batting[(match_id, innings_no, d["batter"])]
                    batting[(match_id, innings_no, d["non_striker"])].update()  # at the crease
                    bowl = bowling[(match_id, innings_no, d["bowler"])]
                    if "wides" not in extras:
                        bat["balls"] += 1
                    bat["runs"] += runs
                    boundary = runs in (4, 6) and not d["runs"].get("non_boundary")
                    bat["fours"] += int(boundary and runs == 4)
                    bat["sixes"] += int(boundary and runs == 6)
                    bowl["runs"] += runs + extras.get("wides", 0) + extras.get("noballs", 0)
                    if "wides" not in extras and "noballs" not in extras:
                        bowl["balls"] += 1
                    for wicket in d.get("wickets", []):
                        if wicket["kind"] not in NOT_OUT:
                            batting[(match_id, innings_no, wicket["player_out"])]["outs"] += 1
                        if wicket["kind"] in CREDITED:
                            bowl["wickets"] += 1
    return batting, bowling


def test_batting_innings_match_an_independent_recount(con: duckdb.DuckDBPyConnection) -> None:
    names = _names(con)
    rows = con.execute(
        "SELECT match_id, innings_no, player_id, runs, balls, fours, sixes, is_out "
        "FROM player_batting_innings"
    ).fetchall()
    ours = {
        (m, i, names[p]): {"runs": r, "balls": b, "fours": f, "sixes": s, "outs": int(o)}
        for m, i, p, r, b, f, s, o in rows
    }
    expected, _ = _recount()
    assert set(ours) == set(expected)
    for key, line in expected.items():
        assert ours[key] == {k: line[k] for k in ("runs", "balls", "fours", "sixes", "outs")}, key


def test_bowling_innings_match_an_independent_recount(con: duckdb.DuckDBPyConnection) -> None:
    names = _names(con)
    rows = con.execute(
        "SELECT match_id, innings_no, player_id, balls, runs, wickets FROM player_bowling_innings"
    ).fetchall()
    ours = {(m, i, names[p]): {"balls": b, "runs": r, "wickets": w} for m, i, p, b, r, w in rows}
    _, expected = _recount()
    assert set(ours) == set(expected)
    for key, line in expected.items():
        assert ours[key] == {k: line[k] for k in ("balls", "runs", "wickets")}, key


@pytest.mark.parametrize(
    ("match_id", "name", "line"),
    [
        # 2008 opener: McCullum 158* off 73 balls with 10 fours and 13 sixes, opening.
        (335982, "BB McCullum", (158, 73, 10, 13, False, 2)),
        # 2019 final: Pollard 41* off 25, batting at No. 6 after Krunal Pandya.
        (1181768, "KA Pollard", (41, 25, 3, 3, False, 6)),
    ],
)
def test_known_batting_lines(
    con: duckdb.DuckDBPyConnection, match_id: int, name: str, line: tuple[object, ...]
) -> None:
    row = con.execute(
        """
        SELECT runs, balls, fours, sixes, is_out, position
        FROM player_batting_innings JOIN players USING (player_id)
        WHERE match_id = ? AND name = ?
        """,
        [match_id, name],
    ).fetchone()
    assert row == line


def test_known_bowling_line(con: duckdb.DuckDBPyConnection) -> None:
    # 2019 final: Bumrah 4-0-14-2.
    row = con.execute(
        """
        SELECT balls, runs, wickets, maidens
        FROM player_bowling_innings JOIN players USING (player_id)
        WHERE match_id = 1181768 AND name = 'JJ Bumrah'
        """
    ).fetchone()
    assert row == (24, 14, 2, 0)


def test_batting_positions_follow_the_order_of_arrival(con: duckdb.DuckDBPyConnection) -> None:
    for match_id, innings_no, positions in con.execute(
        """
        SELECT match_id, innings_no, list(position ORDER BY position)
        FROM player_batting_innings GROUP BY ALL
        """
    ).fetchall():
        assert positions == list(range(1, len(positions) + 1)), (match_id, innings_no)


def test_cells_add_up_to_the_innings_lines(con: duckdb.DuckDBPyConnection) -> None:
    bat = con.execute(
        """
        SELECT (SELECT (sum(runs), sum(balls), sum(fours), sum(sixes), sum(dots),
                        count(*) FILTER (WHERE is_out), round(sum(par_runs), 6))
                FROM player_batting_innings),
               (SELECT (sum(runs), sum(balls), sum(fours), sum(sixes), sum(dots), sum(outs),
                        round(sum(par_runs), 6))
                FROM player_batting_cells)
        """
    ).fetchone()
    assert bat is not None
    assert bat[0] == bat[1]
    bowl = con.execute(
        """
        SELECT (SELECT (sum(runs), sum(balls), sum(wickets), sum(dots), sum(wides))
                FROM player_bowling_innings),
               (SELECT (sum(runs), sum(balls), sum(wickets), sum(dots), sum(wides))
                FROM player_bowling_cells)
        """
    ).fetchone()
    assert bowl is not None
    assert bowl[0] == bowl[1]


def test_par_reproduces_the_league_exactly(con: duckdb.DuckDBPyConnection) -> None:
    """Par is the league rate, so summed over every player it equals what happened."""
    rows = con.execute(
        """
        SELECT season, phase, sum(runs), sum(par_runs), sum(outs), sum(par_outs),
               sum(dots), sum(par_dots)
        FROM player_batting_cells GROUP BY ALL
        """
    ).fetchall()
    assert rows
    for season, phase, runs, par_runs, outs, par_outs, dots, par_dots in rows:
        assert par_runs == pytest.approx(runs), (season, phase)
        assert par_outs == pytest.approx(outs), (season, phase)
        assert par_dots == pytest.approx(dots), (season, phase)
    for runs, par_runs, wickets, par_wickets in con.execute(
        """
        SELECT sum(runs), sum(par_runs), sum(wickets), sum(par_wickets)
        FROM player_bowling_cells GROUP BY season, phase
        """
    ).fetchall():
        assert par_runs == pytest.approx(runs)
        assert par_wickets == pytest.approx(wickets)


def test_super_overs_are_excluded(con: duckdb.DuckDBPyConnection) -> None:
    super_over_balls = con.execute(
        """
        SELECT count(*) FROM deliveries JOIN innings USING (match_id, innings_no)
        WHERE is_super_over
        """
    ).fetchone()
    assert super_over_balls is not None
    assert super_over_balls[0] > 0
    for table in ("player_batting_innings", "player_bowling_innings"):
        counted = con.execute(
            f"""
            SELECT count(*) FROM {table} JOIN innings USING (match_id, innings_no)
            WHERE is_super_over
            """
        ).fetchone()
        assert counted == (0,)


def test_fielding_credits_exclude_substitutes(con: duckdb.DuckDBPyConnection) -> None:
    totals = con.execute(
        "SELECT sum(catches), sum(stumpings), sum(run_outs) FROM player_fielding"
    ).fetchone()
    raw = con.execute(
        """
        SELECT count(*) FILTER (WHERE kind IN ('caught', 'caught and bowled')),
               count(*) FILTER (WHERE kind = 'stumped')
        FROM wickets JOIN innings USING (match_id, innings_no)
        WHERE NOT is_super_over AND NOT coalesce(list_bool_or(fielder_is_substitute), false)
        """
    ).fetchone()
    assert totals is not None
    assert raw is not None
    assert (totals[0], totals[1]) == raw
    assert totals[2] > 0


def test_directory_covers_everyone_who_played(con: duckdb.DuckDBPyConnection) -> None:
    played = con.execute("SELECT count(DISTINCT player_id) FROM match_players").fetchone()
    indexed = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE role IN ('batter', 'bowler', 'all_rounder')) "
        "FROM player_index"
    ).fetchone()
    assert played is not None
    assert indexed == (played[0], played[0])
    dhoni = con.execute(
        "SELECT role, search_key FROM player_index WHERE name = 'MS Dhoni'"
    ).fetchone()
    assert dhoni is not None
    assert dhoni[0] == "batter"
    assert "dhoni" in dhoni[1]


def test_phase_innings_add_up_to_the_innings_lines(con: duckdb.DuckDBPyConnection) -> None:
    """The units CricIQ Ratings are fitted on partition each innings line by phase."""
    for role, outs in (("batting", "count(*) FILTER (WHERE is_out)"), ("bowling", "sum(wickets)")):
        phase_outs = "sum(outs)" if role == "batting" else "sum(wickets)"
        mismatched = con.execute(
            f"""
            WITH lines AS (
                SELECT player_id, match_id, innings_no, sum(runs) AS runs, sum(balls) AS balls,
                       {outs} AS outs, round(sum(par_runs), 6) AS par_runs
                FROM player_{role}_innings GROUP BY ALL
            ),
            phases AS (
                SELECT player_id, match_id, innings_no, sum(runs) AS runs, sum(balls) AS balls,
                       {phase_outs} AS outs, round(sum(par_runs), 6) AS par_runs
                FROM player_{role}_phases GROUP BY ALL
            )
            SELECT count(*) FROM lines FULL OUTER JOIN phases
                USING (player_id, match_id, innings_no)
            -- A batter who reached the crease but never faced or got out has no phase rows.
            WHERE lines.runs IS DISTINCT FROM coalesce(phases.runs, 0)
               OR lines.balls IS DISTINCT FROM coalesce(phases.balls, 0)
               OR lines.outs IS DISTINCT FROM coalesce(phases.outs, 0)
               OR lines.par_runs IS DISTINCT FROM coalesce(phases.par_runs, 0)
               OR lines.runs IS NULL
            """
        ).fetchone()
        assert mismatched == (0,), role
