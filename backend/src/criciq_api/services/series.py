"""Series and tournaments: lists, a series' or tournament's page, and two sides' series.

A series' result counts its wins ("England won 2-1, 2 drawn", with an en dash); a tournament's names
the winner of its final. An event whose last match is within ``RECENT_DAYS`` of the
data's date (the day of its last download or sync) may not be over (Cricsheet does not
say how many matches are scheduled), so its score reads "so far".
"""

from __future__ import annotations

import datetime as dt
from itertools import groupby

from criciq_api.db import Database, Row
from criciq_api.repositories import series as repo
from criciq_api.schemas.series import (
    DecisivePlayer,
    SeriesBatter,
    SeriesBowler,
    SeriesDetail,
    SeriesMatch,
    SeriesPage,
    SeriesRecord,
    SeriesRef,
    SeriesRound,
    SeriesStanding,
    SeriesSummary,
    SeriesTeam,
)
from criciq_api.services.matches import summary_from_row

RECENT_DAYS = 14
# Scores read "2-1" with an en dash.
DASH = "\u2013"


class SeriesDataMissingError(RuntimeError):
    pass


class SeriesNotFoundError(LookupError):
    pass


def _require(db: Database) -> None:
    if not repo.has_events(db):
        raise SeriesDataMissingError


def _team(db: Database, franchise_id: str, wins: int = 0) -> SeriesTeam:
    found = repo.teams(db).get(franchise_id)
    return SeriesTeam(
        franchise_id=franchise_id,
        name=found["name"] if found else franchise_id,
        color=found["color"] if found else "#7A7A7A",
        wins=wins,
    )


def _extras(row: Row) -> str:
    parts = []
    if row["drawn"]:
        parts.append(f"{row['drawn']} drawn")
    if row["tied"]:
        parts.append(f"{row['tied']} tied")
    if row["no_result"]:
        parts.append(f"{row['no_result']} without a result")
    missing = row.get("missing") or 0
    if missing:
        parts.append(f"{missing} not in the data")
    return f", {', '.join(parts)}" if parts else ""


def result_text(
    row: Row, teams: list[SeriesTeam], recent: bool, only_result: str | None = None
) -> str:
    """The series' score or the tournament's winner, in words."""
    champion, runner_up = row.get("champion"), row.get("runner_up")
    if row["kind"] == "tournament" or row["tournament_id"] is not None:
        if champion is not None and runner_up is not None:
            return f"{champion.name} beat {runner_up.name} in the final"
        if row["kind"] == "series" and only_result is not None:
            return only_result
        return "Under way: no final in the data yet" if recent else "No final in the data"
    if row["matches"] == 1 and only_result is not None:
        return only_result
    a, b = teams[0], teams[1]
    if recent:
        if a.wins == b.wins:
            return f"Level at {a.wins}{DASH}{b.wins} so far{_extras(row)}"
        return f"{a.name} lead {a.wins}{DASH}{b.wins} so far{_extras(row)}"
    if a.wins > b.wins:
        return f"{a.name} won {a.wins}{DASH}{b.wins}{_extras(row)}"
    if a.wins == 0 and row["no_result"] == row["matches"]:
        return "No result"
    return f"Series drawn {a.wins}{DASH}{b.wins}{_extras(row)}"


def _summary(
    db: Database, row: Row, latest: dt.date | None, only_result: str | None = None
) -> SeriesSummary:
    teams = sorted(
        (_team(db, t, w) for t, w in zip(row["teams"], row["wins"], strict=True)),
        key=lambda t: (-t.wins, t.name),
    )
    recent = latest is not None and (latest - row["end_date"]).days <= RECENT_DAYS
    champion = _team(db, row["champion_id"]) if row["champion_id"] else None
    runner_up = _team(db, row["runner_up_id"]) if row["runner_up_id"] else None
    words = result_text(
        {**row, "champion": champion, "runner_up": runner_up}, teams, recent, only_result
    )
    return SeriesSummary(
        event_id=row["event_id"],
        name=row["name"],
        season=row["season"],
        kind=row["kind"],
        tournament_id=row["tournament_id"],
        named=row["named"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        matches=row["matches"],
        missing=row["missing"],
        teams=teams,
        drawn=row["drawn"],
        tied=row["tied"],
        no_result=row["no_result"],
        champion=champion,
        runner_up=runner_up,
        recent=recent,
        result_text=words,
    )


def _only_results(db: Database, rows: list[Row]) -> dict[str, str]:
    """The result of each one-match event, by event id."""
    ids = [r["event_id"] for r in rows if r["matches"] == 1]
    if not ids:
        return {}
    marks = ", ".join("?" for _ in ids)
    return {
        r["event_id"]: r["result_text"]
        for r in db.rows(
            f"""
            SELECT x.event_id, s.result_text FROM event_matches x
            JOIN match_summaries s USING (match_id) WHERE x.event_id IN ({marks})
            """,
            ids,
        )
    }


def _latest(db: Database) -> dt.date | None:
    """The data's date: the day of the download or sync its version names
    ("2026-10-06.ac28ace1"), else its latest match."""
    try:
        return dt.date.fromisoformat(db.data_version[:10])
    except ValueError:
        found = repo.latest_date(db)
        return found if isinstance(found, dt.date) else None


def list_series(
    db: Database,
    *,
    kind: str | None = None,
    year: int | None = None,
    team: str | None = None,
    major: bool | None = None,
    page: int = 1,
    page_size: int = 30,
) -> SeriesPage:
    _require(db)
    rows, total = repo.list_events(
        db,
        kind=kind,
        year=year,
        team=team,
        major=major,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    latest = _latest(db)
    only = _only_results(db, rows)
    return SeriesPage(
        items=[_summary(db, r, latest, only.get(r["event_id"])) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        years=repo.years(db),
    )


def _standing(db: Database, row: Row) -> SeriesStanding:
    return SeriesStanding(
        position=row["position"],
        team=_team(db, row["franchise_id"]),
        played=row["played"],
        won=row["won"],
        lost=row["lost"],
        tied=row["tied"],
        no_result=row["no_result"],
        points=row["points"],
        nrr=row["nrr"],
    )


def get_series(db: Database, event_id: str) -> SeriesDetail:
    _require(db)
    row = repo.get_event(db, event_id)
    if row is None:
        raise SeriesNotFoundError(event_id)
    matches = repo.event_matches(db, event_id)
    only = matches[0]["result_text"] if row["matches"] == 1 and matches else None
    summary = _summary(db, row, _latest(db), only)
    lows = repo.winner_lows(db, event_id, draws=db.match_format == "Test")
    entries = [
        SeriesMatch(
            summary=summary_from_row(m), round=m["round"], winner_low=lows.get(m["match_id"])
        )
        for m in matches
    ]
    rounds: list[SeriesRound] = []
    if row["kind"] == "tournament":
        tables = {
            name: [_standing(db, s) for s in rows]
            for name, rows in groupby(repo.standings(db, event_id), key=lambda s: s["round"])
        }
        # Rounds in order, each knockout stage by its first match.
        first: dict[str, int] = {}
        for m in matches:
            if m["round"] is not None:
                first[m["round"]] = min(first.get(m["round"], m["match_order"]), m["match_order"])
        ordered = sorted(
            (m for m in matches if m["round"] is not None),
            key=lambda m: (m["round_order"], first[m["round"]], m["round"], m["match_order"]),
        )
        for (_, name), found in groupby(ordered, key=lambda m: (m["round_order"], m["round"])):
            games = list(found)
            rounds.append(
                SeriesRound(
                    name=name,
                    knockout=bool(games[0]["knockout"]),
                    standings=tables.get(name, []),
                    matches=[summary_from_row(m) for m in games],
                )
            )
    return SeriesDetail(
        summary=summary,
        matches=entries,
        rounds=rounds,
        batters=[SeriesBatter(**b) for b in repo.batters(db, event_id)],
        bowlers=[SeriesBowler(**b) for b in repo.bowlers(db, event_id)],
        decisive=[
            DecisivePlayer(**{**d, "added": round(float(d["added"]), 3)})
            for d in repo.decisive(db, event_id)
        ],
    )


def series_ref(db: Database, match_id: int) -> SeriesRef | None:
    found = repo.event_of_match(db, match_id)
    return SeriesRef(**found) if found else None


def get_series_record(db: Database, a: str, b: str) -> SeriesRecord:
    """The two sides' series against each other, newest first; the record counts
    finished series of two or more matches."""
    _require(db)
    rows, _ = repo.list_events(db, kind="series", year=None, team=a, major=None, opponent=b)
    latest = _latest(db)
    only = _only_results(db, rows)
    items = [_summary(db, r, latest, only.get(r["event_id"])) for r in rows]
    a_won = b_won = drawn = 0
    for s in items:
        if s.recent or s.matches < 2 or s.tournament_id is not None:
            continue
        wins = {t.franchise_id: t.wins for t in s.teams}
        if wins.get(a, 0) > wins.get(b, 0):
            a_won += 1
        elif wins.get(b, 0) > wins.get(a, 0):
            b_won += 1
        else:
            drawn += 1
    return SeriesRecord(
        played=a_won + b_won + drawn, a_won=a_won, b_won=b_won, drawn=drawn, series=items
    )
