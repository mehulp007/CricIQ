from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from criciq_api.db import Database
from criciq_api.schemas.notes import Note, NoteDates, NoteList
from criciq_api.services import notes as service

router = APIRouter(prefix="/notes", tags=["notes"])


def get_notes_db(request: Request) -> Database | None:
    """The notes database, or None until a build or sync has written one."""
    found: Database | None = request.app.state.notes.get()
    return found


NotesDB = Annotated[Database | None, Depends(get_notes_db)]


@router.get("")
def read_notes(
    db: NotesDB,
    limit: Annotated[int, Query(ge=1, le=100, description="Notes to return.")] = 20,
    before: Annotated[
        dt.date | None, Query(description="Only notes before this date (the next page).")
    ] = None,
    competition: Annotated[
        str | None,
        Query(pattern=r"^[a-z0-9]{2,8}$", description="Only days with this competition's matches."),
    ] = None,
) -> NoteList:
    """The latest daily notes, newest first: one for every day matches ended, written
    automatically from the data."""
    return service.list_notes(db, limit=limit, before=before, competition=competition)


@router.get("/dates")
def read_note_dates(db: NotesDB) -> NoteDates:
    """Every day with a note, newest first."""
    return service.note_dates(db)


@router.get("/{date}")
def read_note(db: NotesDB, date: dt.date) -> Note:
    """One day's note in full: its items, the day's standout figures and the notes around it."""
    found = service.get_note(db, date)
    if found is None:
        raise HTTPException(status_code=404, detail=f"no note for {date}")
    return found
