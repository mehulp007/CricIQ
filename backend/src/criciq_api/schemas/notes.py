"""Daily notes: a short note for every day matches ended, written from the data."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

NoteKind = Literal["result", "turning_point", "match_winner", "milestone", "record", "standings"]


class NoteSummary(BaseModel):
    date: dt.date
    slug: str = Field(description='The note\'s path segment, "2026-05-31".')
    headline: str
    summary: str = Field(description="The day's two or three main items.")
    competitions: list[str] = Field(description='Site competition ids, "ipl", "t20i".')
    match_count: int
    added_on: dt.datetime = Field(description="When the day's newest match came into the data.")


class NoteList(BaseModel):
    notes: list[NoteSummary]
    next_before: dt.date | None = Field(
        description="Pass as `before` for the next (older) page; none at the end."
    )
    competition: str | None
    data_version: str | None = Field(description="None when no notes have been written yet.")
    method: str


class NoteDates(BaseModel):
    """Every day with a note, newest first (for the sitemap)."""

    dates: list[dt.date]


class NoteLink(BaseModel):
    label: str
    href: str = Field(description='A path on the site, "/ipl/matches/1473511?ball=2.95".')


class NoteItem(BaseModel):
    position: int
    kind: NoteKind
    competition: str
    match_id: int
    title: str
    body: str
    why_it_matters: str = Field(description="Empty when nothing more needs saying.")
    links: list[NoteLink]
    model: bool = Field(description="Its figures are model estimates (win probability).")


class MatchNote(BaseModel):
    """A match's place in the daily notes: the day's note and the match's own items."""

    date: dt.date
    headline: str
    items: list[NoteItem]


class NoteFigure(BaseModel):
    """One of the day's standout performances, with the player's totals before and after."""

    position: int
    competition: str
    match_id: int
    player_id: str
    name: str
    team: str | None
    kind: Literal["batting", "bowling"]
    figure: str = Field(description='"75* (42)", "3/27".')
    career_before: int
    career_after: int
    unit: Literal["runs", "wickets"]


class Note(NoteSummary):
    items: list[NoteItem]
    figures: list[NoteFigure]
    previous: dt.date | None = Field(description="The note before this one.")
    next: dt.date | None = Field(description="The note after this one.")
    data_version: str
    method: str
