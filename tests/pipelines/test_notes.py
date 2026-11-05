"""Daily notes: one per day matches ended, every figure in them from the data."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest

from criciq_pipelines import notes
from criciq_pipelines.notes import build_notes, ordinal, plural, possessive

IPL_FINAL = 1473511  # the 2025 final, RCB v PBKS
COMPETITIONS = ("IPL", "T20I", "ODI", "TEST")


def _servings(folder: Path) -> dict[str, Path]:
    return {
        c: folder / ("serving.duckdb" if c == "IPL" else f"serving-{c.lower()}.duckdb")
        for c in COMPETITIONS
    }


@pytest.fixture(scope="module")
def built(fixture_scored_serving_db: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("notes") / "notes.duckdb"
    build_notes(
        _servings(fixture_scored_serving_db.parent),
        out,
        built=dt.datetime(2026, 1, 1, 12, 0),
    )
    return out


@pytest.fixture(scope="module")
def con(built: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(built), read_only=True)
    yield connection
    connection.close()


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[Any]:
    return con.execute(sql, params or []).fetchall()


def _serving(competition_id: str, fixture_scored_serving_db: Path) -> duckdb.DuckDBPyConnection:
    path = _servings(fixture_scored_serving_db.parent)[competition_id.upper()]
    return duckdb.connect(str(path), read_only=True)


def test_one_note_for_every_day_a_match_ended(
    con: duckdb.DuckDBPyConnection, fixture_scored_serving_db: Path
) -> None:
    expected: dict[dt.date, int] = {}
    for competition in COMPETITIONS:
        serving = _serving(competition, fixture_scored_serving_db)
        for (day,) in serving.execute(
            "SELECT coalesce(end_date, match_date) FROM matches"
        ).fetchall():
            expected[day] = expected.get(day, 0) + 1
        serving.close()
    found = dict(_rows(con, "SELECT date, match_count FROM notes"))
    assert found == expected
    # Every match has its result, and every note's items are numbered from 1.
    assert _rows(con, "SELECT count(*) FROM note_items WHERE kind = 'result'") == [
        (sum(expected.values()),)
    ]
    gaps = _rows(
        con,
        "SELECT date FROM note_items GROUP BY date HAVING max(position) <> count(*) "
        "OR min(position) <> 1",
    )
    assert gaps == []
    assert _rows(con, "SELECT DISTINCT slug = strftime(date, '%Y-%m-%d') FROM notes") == [(True,)]


def test_the_ipl_final_reads_as_written(con: duckdb.DuckDBPyConnection) -> None:
    (headline, summary, competitions) = _rows(
        con, "SELECT headline, summary, competitions FROM notes WHERE date = '2025-06-03'"
    )[0]
    assert headline == (
        "Royal Challengers Bengaluru beat Punjab Kings by 6 runs in the IPL 2025 final"
    )
    assert summary.startswith(headline + ".")
    assert competitions == ["ipl"]
    items = _rows(
        con,
        "SELECT kind, title, body, why_it_matters, links FROM note_items "
        "WHERE match_id = ? ORDER BY position",
        [IPL_FINAL],
    )
    kind, title, body, why, links = items[0]
    assert kind == "result"
    assert title == f"{headline}."
    assert body == (
        "Royal Challengers Bengaluru 190/9 (20 overs); Punjab Kings 184/7 (20 overs). "
        "Best figures: Shashank Singh 61* (30), Arshdeep Singh 3/40. "
        "Player of the match: Krunal Pandya."
    )
    assert why == "The final: it decided the IPL 2025 title."
    assert json.loads(links)[0] == {
        "label": "Scorecard and replay",
        "href": f"/ipl/matches/{IPL_FINAL}",
    }
    kinds = [k for k, *_ in items]
    assert kinds[:3] == ["result", "turning_point", "match_winner"]
    turning = items[1]
    assert re.fullmatch(
        r"Turning point: .+ at \d+\.\d moved .+ from \d+% to \d+% \(model estimate\)\.", turning[1]
    )
    assert json.loads(turning[4])[0]["href"].startswith(f"/ipl/matches/{IPL_FINAL}?ball=2.")


def test_every_figure_comes_from_the_tables(
    con: duckdb.DuckDBPyConnection, fixture_scored_serving_db: Path
) -> None:
    """Parse the figures out of each note's sentences and check each one at its source."""
    checked = 0
    for competition in COMPETITIONS:
        serving = _serving(competition, fixture_scored_serving_db)
        site = competition.lower()
        names = dict(
            serving.execute("SELECT player_id, coalesce(full_name, name) FROM players").fetchall()
        )
        for match_id, kind, title, body in _rows(
            con,
            "SELECT match_id, kind, title, body FROM note_items WHERE competition_id = ?",
            [site],
        ):
            if kind == "result":
                totals = serving.execute(
                    "SELECT runs, wickets FROM innings WHERE match_id = ? AND NOT is_super_over "
                    "ORDER BY innings_no",
                    [match_id],
                ).fetchall()
                # Totals are grouped by side ("England 407 and 182; Australia 308 and 279").
                line = body.split(" Best figures")[0]
                written = re.findall(
                    r"(?<= )(\d+)(?:/(\d+))?(?=(?: \([\d.]+ overs\))?(?:;| and |\.$))", line
                )
                assert sorted((int(r), int(w) if w else 10) for r, w in written) == sorted(
                    (r, min(w, 10)) for r, w in totals
                ), (match_id, body)
                best = re.search(r"Best figures: (.+?) (\d+)(\*?) \((\d+)\)", body)
                if best:
                    runs, out, balls = serving.execute(
                        "SELECT runs, is_out, balls FROM player_batting_innings WHERE match_id = ? "
                        "ORDER BY runs DESC, balls, player_id LIMIT 1",
                        [match_id],
                    ).fetchone() or (None, None, None)
                    assert (int(best[2]), best[3] == "", int(best[4])) == (runs, out, balls)
                checked += 1
            elif kind == "turning_point":
                before, after = map(int, re.findall(r"(\d+)% to (\d+)%", title)[0])
                swing = serving.execute(
                    "SELECT wp_before, wp_after FROM match_swings WHERE match_id = ?", [match_id]
                ).fetchone()
                assert swing is not None
                assert (before, after) == (round(100 * swing[0]), round(100 * swing[1]))
                checked += 1
            elif kind == "match_winner":
                points = int(re.findall(r"\+(\d+) points", title)[0])
                top = serving.execute(
                    "SELECT player_id, sum(wpa) FROM player_wpa WHERE match_id = ? "
                    "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 1",
                    [match_id],
                ).fetchone()
                assert top is not None
                assert title.startswith(f"Match-winner: {names[top[0]]},")
                assert points == round(100 * top[1])
                checked += 1
            elif kind == "milestone" and "runs" in title:
                name, threshold = re.fullmatch(r"(.+) passed ([\d,]+) .+ runs\.", title).groups()  # type: ignore[union-attr]
                total = int(re.findall(r": ([\d,]+) runs", body)[0].replace(",", ""))
                player = next(p for p, n in names.items() if n == name)
                order = serving.execute(
                    "SELECT match_order FROM matches WHERE match_id = ?", [match_id]
                ).fetchone()
                assert order is not None
                career = serving.execute(
                    "SELECT sum(b.runs) FROM player_batting_innings b JOIN matches m "
                    "USING (match_id) WHERE b.player_id = ? AND m.match_order <= ?",
                    [player, order[0]],
                ).fetchone()
                assert career is not None
                assert total == career[0] >= int(threshold.replace(",", ""))
                checked += 1
        serving.close()
    assert checked > 30


def test_league_tables_and_series_scores(con: duckdb.DuckDBPyConnection) -> None:
    standings = [t for (t,) in _rows(con, "SELECT title FROM note_items WHERE kind = 'standings'")]
    assert standings
    for title in standings:
        assert re.fullmatch(
            r"(Table: .+ \d+(st|nd|rd|th) \(\d+ wins? from \d+\).*"
            r"|.+ (lead|won|took|drew|are level at) .*\d+" + notes.DASH + r"\d+.*)\.",
            title,
        ), title


def test_records_rank_against_earlier_matches_only(
    con: duckdb.DuckDBPyConnection, fixture_scored_serving_db: Path
) -> None:
    """The fixture data is too small for a record to count (fewer than MIN_HISTORY matches)."""
    assert _rows(con, "SELECT count(*) FROM note_items WHERE kind = 'record'") == [(0,)]
    # With every match counting, a total ranks among the totals made before it.
    source = notes.Source("IPL", fixture_scored_serving_db)
    serving = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    try:
        original = notes.MIN_HISTORY
        notes.MIN_HISTORY = 0
        try:
            matches, _ = notes.collect(serving, source)
        finally:
            notes.MIN_HISTORY = original
        records = [i for m in matches for i in m.items if i.kind == "record"]
        assert records
        first = matches[0]
        new = [i for i in first.items if i.kind == "record"]
        # The very first match's entries are each the best so far.
        assert new
        assert all(" is the highest " in i.title or " are the best " in i.title for i in new)
    finally:
        serving.close()


def test_the_build_is_deterministic(built: Path, fixture_scored_serving_db: Path) -> None:
    again = built.with_name("again.duckdb")
    build_notes(
        _servings(fixture_scored_serving_db.parent), again, built=dt.datetime(2026, 1, 1, 12, 0)
    )
    a = duckdb.connect(str(built), read_only=True)
    b = duckdb.connect(str(again), read_only=True)
    try:
        for table in notes.NOTE_TABLES:
            sql = f"SELECT * FROM {table} ORDER BY ALL"
            assert a.execute(sql).fetchall() == b.execute(sql).fetchall(), table
    finally:
        a.close()
        b.close()


def test_only_mens_competitions(
    con: duckdb.DuckDBPyConnection, fixture_scored_serving_db: Path
) -> None:
    for competition in COMPETITIONS:
        serving = _serving(competition, fixture_scored_serving_db)
        assert serving.execute("SELECT DISTINCT gender FROM competitions").fetchall() == [("male",)]
        serving.close()
    found = {c for (cs,) in _rows(con, "SELECT competitions FROM notes") for c in cs}
    assert found <= {c.lower() for c in COMPETITIONS}


def test_without_scores_there_are_no_model_items(fixture_serving_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "notes.duckdb"
    counts = build_notes({"IPL": fixture_serving_db}, out)
    assert counts["notes"] > 0
    con = duckdb.connect(str(out), read_only=True)
    try:
        kinds = {k for (k,) in con.execute("SELECT DISTINCT kind FROM note_items").fetchall()}
        assert "result" in kinds
        assert not kinds & {"turning_point", "match_winner"}
        assert con.execute("SELECT value FROM meta WHERE key = 'method'").fetchone() == (
            notes.METHOD,
        )
    finally:
        con.close()


def test_a_missing_database_is_skipped(fixture_serving_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "notes.duckdb"
    counts = build_notes({"IPL": fixture_serving_db, "BBL": tmp_path / "missing.duckdb"}, out)
    assert counts["notes"] > 0


def test_added_on_comes_from_the_ingest_log(fixture_serving_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "notes.duckdb"
    seen = dt.datetime(2025, 6, 4, 9, 30)
    build_notes(
        {"IPL": fixture_serving_db}, out, added={IPL_FINAL: seen}, built=dt.datetime(2026, 1, 1)
    )
    con = duckdb.connect(str(out), read_only=True)
    try:
        rows = dict(con.execute("SELECT date, added_on FROM notes").fetchall())
    finally:
        con.close()
    assert rows[dt.date(2025, 6, 3)] == seen
    assert set(rows.values()) == {seen, dt.datetime(2026, 1, 1)}


def test_words() -> None:
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "111th",
    ]  # fmt: skip
    assert plural(1, "run") == "1 run"
    assert plural(2_000, "wicket") == "2,000 wickets"
    assert possessive("Punjab Kings") == "Punjab Kings'"
    assert possessive("Virat Kohli") == "Virat Kohli's"
