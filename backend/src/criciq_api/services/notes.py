"""Daily notes from ``notes.duckdb`` (``criciq_pipelines.notes``): the latest first, and
each day's note in full. The database is optional; without it there are no notes yet."""

from __future__ import annotations

import datetime as dt
import json

from criciq_api.db import Database, Row
from criciq_api.schemas.notes import (
    Note,
    NoteDates,
    NoteFigure,
    NoteItem,
    NoteLink,
    NoteList,
    NoteSummary,
)

# Shown with every note (and stored with them in the notes database).
METHOD = (
    "Written automatically from CricIQ's ball-by-ball data (Cricsheet). Matches appear here "
    "once Cricsheet publishes them, usually a day or two after play. Win-probability figures "
    "are model estimates."
)
MODEL_KINDS = frozenset({"turning_point", "match_winner"})


def _method(db: Database | None) -> str:
    if db is None:
        return METHOD
    found = db.scalar("SELECT value FROM meta WHERE key = 'method'")
    return str(found) if found else METHOD


def _summary(r: Row) -> NoteSummary:
    return NoteSummary(
        date=r["date"],
        slug=r["slug"],
        headline=r["headline"],
        summary=r["summary"],
        competitions=list(r["competitions"]),
        match_count=r["match_count"],
        added_on=r["added_on"],
    )


def list_notes(
    db: Database | None,
    *,
    limit: int = 20,
    before: dt.date | None = None,
    competition: str | None = None,
) -> NoteList:
    """The latest notes (optionally before a date, or with a competition's matches)."""
    if db is None:
        return NoteList(
            notes=[], next_before=None, competition=competition, data_version=None, method=METHOD
        )
    key = f"notes:{limit}:{before}:{competition}"
    if key in db.cache:
        cached: NoteList = db.cache[key]
        return cached
    clauses: list[str] = ["TRUE"]
    params: list[object] = []
    if before is not None:
        clauses.append("n.date < ?")
        params.append(before)
    if competition is not None:
        clauses.append("list_contains(n.competitions, ?)")
        params.append(competition)
    # A competition's own list leads with its own news: its first item and its results.
    headline = "n.headline"
    summary = "n.summary"
    if competition is not None:
        headline = """(SELECT rtrim(i.title, '.') FROM note_items i
                        WHERE i.date = n.date AND i.competition_id = ?
                        ORDER BY i.position LIMIT 1)"""
        summary = """(SELECT string_agg(i.title, ' ' ORDER BY i.position) FROM (
                          SELECT title, position FROM note_items i
                          WHERE i.date = n.date AND i.competition_id = ? AND i.kind = 'result'
                          ORDER BY position LIMIT 3) i)"""
        params = [competition, competition, *params]
    rows = db.rows(
        f"""
        SELECT n.date, n.slug, {headline} AS headline, {summary} AS summary, n.competitions,
               n.match_count, n.added_on
        FROM notes n
        WHERE {" AND ".join(clauses)}
        ORDER BY n.date DESC
        LIMIT ?
        """,
        [*params, limit + 1],
    )
    more = len(rows) > limit
    rows = rows[:limit]
    found = NoteList(
        notes=[_summary(r) for r in rows],
        next_before=rows[-1]["date"] if more and rows else None,
        competition=competition,
        data_version=db.data_version,
        method=_method(db),
    )
    db.cache[key] = found
    return found


def note_dates(db: Database | None) -> NoteDates:
    if db is None:
        return NoteDates(dates=[])
    rows = db.rows("SELECT date FROM notes ORDER BY date DESC")
    return NoteDates(dates=[r["date"] for r in rows])


def get_note(db: Database | None, date: dt.date) -> Note | None:
    if db is None:
        return None
    key = f"note:{date}"
    if key in db.cache:
        cached: Note = db.cache[key]
        return cached
    found = db.row("SELECT * FROM notes WHERE date = ?", [date])
    if found is None:
        return None
    items = db.rows("SELECT * FROM note_items WHERE date = ? ORDER BY position", [date])
    figures = db.rows("SELECT * FROM note_figures WHERE date = ? ORDER BY position", [date])
    around = db.row(
        """
        SELECT (SELECT max(date) FROM notes WHERE date < ?) AS previous,
               (SELECT min(date) FROM notes WHERE date > ?) AS next
        """,
        [date, date],
    )
    assert around is not None
    note = Note(
        **_summary(found).model_dump(),
        items=[
            NoteItem(
                position=i["position"],
                kind=i["kind"],
                competition=i["competition_id"],
                match_id=i["match_id"],
                title=i["title"],
                body=i["body"],
                why_it_matters=i["why_it_matters"],
                links=[NoteLink(**link) for link in json.loads(i["links"])],
                model=i["kind"] in MODEL_KINDS,
            )
            for i in items
        ],
        figures=[
            NoteFigure(
                position=f["position"],
                competition=f["competition_id"],
                match_id=f["match_id"],
                player_id=f["player_id"],
                name=f["name"],
                team=f["team"],
                kind=f["kind"],
                figure=f["figure"],
                career_before=f["career_before"],
                career_after=f["career_after"],
                unit=f["unit"],
            )
            for f in figures
        ],
        previous=around["previous"],
        next=around["next"],
        data_version=found["data_version"],
        method=_method(db),
    )
    db.cache[key] = note
    return note
