from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.schemas.series import SeriesDetail, SeriesPage, SeriesRecord
from criciq_api.services import series as service

router = APIRouter(prefix="/series", tags=["series"])

DB = Annotated[Database, Depends(get_db)]
TeamId = Annotated[str, Query(min_length=2, max_length=8, description="Team id, e.g. IND")]


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=404, detail="series and tournaments are kept for Tests, ODIs and T20Is"
    )


@router.get("")
def list_series(
    db: DB,
    kind: Literal["series", "tournament"] | None = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    team: Annotated[str | None, Query(max_length=8, description="Team id, e.g. IND")] = None,
    major: Annotated[
        bool | None, Query(description="Only the major tournaments (true) or the rest (false).")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> SeriesPage:
    """Series and tournaments, newest first."""
    try:
        return service.list_series(
            db,
            kind=kind,
            year=year,
            team=team.upper() if team else None,
            major=major,
            page=page,
            page_size=page_size,
        )
    except service.SeriesDataMissingError:
        raise _unavailable() from None


@router.get("/h2h")
def read_series_record(db: DB, a: TeamId, b: TeamId) -> SeriesRecord:
    """Two sides' series against each other."""
    if a.upper() == b.upper():
        raise HTTPException(status_code=422, detail="pick two different sides")
    try:
        return service.get_series_record(db, a.upper(), b.upper())
    except service.SeriesDataMissingError:
        raise _unavailable() from None


@router.get("/{event_id}")
def read_series(db: DB, event_id: str) -> SeriesDetail:
    """A series or tournament: its matches, tables, knockouts and top performers."""
    try:
        return service.get_series(db, event_id)
    except service.SeriesDataMissingError:
        raise _unavailable() from None
    except service.SeriesNotFoundError:
        raise HTTPException(status_code=404, detail=f"series {event_id} not found") from None
