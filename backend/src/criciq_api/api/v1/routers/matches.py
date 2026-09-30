from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.repositories.matches import MatchFilters
from criciq_api.schemas.matches import MatchDetail, MatchPage, Timeline
from criciq_api.services import matches as service

router = APIRouter(prefix="/matches", tags=["matches"])

DB = Annotated[Database, Depends(get_db)]


@router.get("")
def list_matches(
    db: DB,
    season: Annotated[int | None, Query(ge=2008, le=2100)] = None,
    team: Annotated[str | None, Query(max_length=8, description="Franchise id, e.g. MI")] = None,
    venue: Annotated[str | None, Query(max_length=64, description="Venue id")] = None,
    playoffs: Annotated[bool | None, Query(description="Only playoffs (true) or league")] = None,
    sort: Literal["latest", "oldest"] = "latest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> MatchPage:
    """Paginated match summaries, newest first by default."""
    filters = MatchFilters(season=season, team=team, venue=venue, playoffs=playoffs, sort=sort)
    return service.list_matches(db, filters, page, page_size)


@router.get("/{match_id}")
def read_match(db: DB, match_id: int) -> MatchDetail:
    """Match summary with full scorecards for every innings."""
    try:
        return service.get_detail(db, match_id)
    except service.MatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"match {match_id} not found") from None


@router.get("/{match_id}/timeline")
def read_timeline(db: DB, match_id: int) -> Timeline:
    """Every delivery with running state: one payload drives a full client-side replay."""
    try:
        return service.get_timeline(db, match_id)
    except service.MatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"match {match_id} not found") from None
