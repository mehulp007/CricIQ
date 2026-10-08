"""Series and tournaments (criciq_pipelines.events): grouping, rounds, tables and checks."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pytest

from criciq_pipelines.events import (
    Match,
    check_events,
    group_events,
    is_knockout,
    missing_matches,
    rounds,
    season_label,
    slug,
    standings,
)
from criciq_pipelines.reference import (
    Edition,
    EventResult,
    EventsConfig,
    Tournament,
    load_events,
)

WORLD_CUP = Tournament(
    id="cricket-world-cup",
    name="Men's Cricket World Cup",
    competition="ODI",
    names=["ICC World Cup", "World Cup"],
    editions={2007: Edition(ungrouped="Super Eight")},
)
CONFIG = EventsConfig(tournaments=[WORLD_CUP])


def match(
    match_id: int,
    day: str,
    a: str,
    b: str,
    winner: str | None,
    *,
    event: str | None = "England tour of India",
    stage: str = "League",
    group: str | None = None,
    number: int | None = None,
    outcome: str | None = None,
) -> Match:
    date = dt.date.fromisoformat(day)
    return Match(
        match_id=match_id,
        date=date,
        end_date=date,
        number=number,
        stage=stage,
        outcome=outcome or ("win" if winner else "no_result"),
        teams=(a, b),
        winner=winner,
        event_name=event,
        group=group,
    )


def test_matches_of_one_event_weeks_apart_are_separate_series() -> None:
    matches = [
        match(1, "2021-02-05", "IND", "ENG", "ENG", number=1),
        match(2, "2021-02-13", "IND", "ENG", "IND", number=2),
        # The same tour name three years later is another series.
        match(3, "2024-01-25", "IND", "ENG", "ENG", number=1),
    ]
    events = group_events(matches, "TEST", CONFIG)
    assert [len(e.matches) for e in events] == [2, 1]
    assert all(e.kind == "series" for e in events)


def test_a_tournament_joins_every_name_it_had() -> None:
    matches = [
        match(1, "2019-05-30", "ENG", "SA", "ENG", event="World Cup"),
        match(2, "2019-05-31", "WI", "PAK", "WI", event="ICC World Cup"),
    ]
    (event,) = group_events(matches, "ODI", CONFIG)
    assert event.tournament is WORLD_CUP
    assert event.kind == "tournament"


def test_unnamed_matches_group_by_their_two_sides() -> None:
    matches = [
        match(1, "2010-03-01", "NED", "SCO", "SCO", event=None),
        match(2, "2010-03-03", "SCO", "NED", "NED", event=None),
        match(3, "2010-03-04", "KEN", "SCO", "KEN", event=None),
    ]
    events = group_events(matches, "ODI", CONFIG)
    assert sorted(len(e.matches) for e in events) == [1, 2]
    assert all(e.key[0] == "pair" for e in events)


def test_rounds_name_groups_stages_and_unlabelled_leagues() -> None:
    matches = [
        match(1, "2007-03-13", "AUS", "SCO", "AUS", event="ICC World Cup", group="A"),
        match(2, "2007-03-14", "SA", "NED", "SA", event="ICC World Cup", group="A"),
        match(3, "2007-03-27", "AUS", "WI", "AUS", event="ICC World Cup"),
        match(4, "2007-03-28", "WI", "SL", "SL", event="ICC World Cup"),
        match(5, "2007-04-25", "AUS", "SA", "AUS", event="ICC World Cup", stage="Semi Final"),
        match(6, "2007-04-28", "AUS", "SL", "AUS", event="ICC World Cup", stage="Final"),
    ]
    (event,) = group_events(matches, "ODI", CONFIG)
    found = rounds(event)
    assert found[1] == ("Group A", 0)
    # The edition names its matches outside the groups.
    assert found[3][0] == "Super Eight"
    assert found[5] == ("Semi Final", 2)
    assert found[6] == ("Final", 3)


def test_unlabelled_groups_become_pools_of_sides_that_met() -> None:
    matches = [
        match(1, "2004-09-10", "ENG", "ZIM", "ENG", event="ICC World Cup"),
        match(2, "2004-09-11", "AUS", "USA", "AUS", event="ICC World Cup"),
        match(3, "2004-09-12", "ENG", "SL", "ENG", event="ICC World Cup"),
    ]
    (event,) = group_events(matches, "ODI", CONFIG)
    found = rounds(event)
    assert found[1][0] == found[3][0] == "Pool 1"
    assert found[2][0] == "Pool 2"


def test_standings_count_points_and_ties() -> None:
    matches = [
        match(1, "2023-01-01", "A", "B", "A", event="Tri-series"),
        match(2, "2023-01-02", "B", "C", None, event="Tri-series", outcome="tie"),
        match(3, "2023-01-03", "A", "C", None, event="Tri-series"),
    ]
    (event,) = group_events(matches, "ODI", CONFIG)
    rows = {r.franchise_id: r for r in standings(event, rounds(event), {})}
    assert (rows["A"].won, rows["A"].no_result, rows["A"].points) == (1, 1, 3)
    assert (rows["B"].lost, rows["B"].tied, rows["B"].points) == (1, 1, 1)
    assert rows["C"].points == 2
    assert rows["A"].nrr is None


def test_missing_matches_follow_a_series_numbering_only() -> None:
    series = group_events(
        [
            match(1, "2005-07-21", "ENG", "AUS", "AUS", number=1),
            match(2, "2005-08-04", "ENG", "AUS", "ENG", number=2),
            match(4, "2005-08-25", "ENG", "AUS", "ENG", number=4),
        ],
        "TEST",
        CONFIG,
    )[0]
    assert missing_matches(series) == 1
    # A long league numbers its matches across rounds: no gap is implied.
    league = group_events([match(9, "2017-01-01", "HK", "PNG", "PNG", number=49)], "ODI", CONFIG)
    assert missing_matches(league[0]) == 0


def test_names_and_labels() -> None:
    assert slug("2023 Men's Cricket World Cup") == "2023-mens-cricket-world-cup"
    assert season_label(dt.date(2020, 12, 17), dt.date(2021, 1, 19)) == "2020/21"
    assert season_label(dt.date(2005, 7, 21), dt.date(2005, 9, 12)) == "2005"
    assert is_knockout("Semi Final")
    assert is_knockout("3rd Place Play-Off")
    assert not is_knockout("Super Sixes")
    assert not is_knockout("League")


def test_results_name_a_tournament_or_a_series() -> None:
    with pytest.raises(ValueError, match="either a tournament or a series"):
        EventResult(competition="ODI", year=2023)
    with pytest.raises(ValueError, match="needs a champion"):
        EventResult(competition="ODI", tournament="cricket-world-cup", year=2023)
    assert {r.competition for r in load_events().results} == {"ODI", "T20I", "TEST"}


def test_the_fixture_tests_have_series(fixture_scored_serving_db: Path) -> None:
    con = duckdb.connect(
        str(fixture_scored_serving_db.with_name("serving-test.duckdb")), read_only=True
    )
    try:
        found = con.execute(
            "SELECT event_id, kind, matches, teams FROM events ORDER BY start_date"
        ).fetchall()
        rounds_of = con.execute("SELECT count(*) FROM event_matches").fetchone()
        # Known results the fixtures cannot cover are not checked, and do not fail.
        checks = check_events(con, "TEST", load_events())
    finally:
        con.close()
    assert ("2005-australia-tour-of-england-and-scotland", "series", 1, ["AUS", "ENG"]) in found
    # Two Tests three weeks apart across the new year are one series.
    assert ("2020-21-india-tour-of-australia", "series", 2, ["AUS", "IND"]) in found
    assert rounds_of == (4,)
    assert all(c.passed for c in checks)
    assert not any(c.covered for c in checks)


def test_the_ipl_has_no_series(fixture_serving_db: Path) -> None:
    con = duckdb.connect(str(fixture_serving_db), read_only=True)
    try:
        tables = {t for (t,) in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert "events" not in tables
