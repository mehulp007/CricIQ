from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.schemas.phases import PhaseAnalysis
from criciq_api.services import phases as service

router = APIRouter(prefix="/phases", tags=["phases"])

DB = Annotated[Database, Depends(get_db)]


@router.get("")
def read_phases(
    db: DB,
    first: Annotated[
        int | None, Query(alias="from", ge=2000, le=2100, description="First season (inclusive).")
    ] = None,
    last: Annotated[
        int | None, Query(alias="to", ge=2000, le=2100, description="Last season (inclusive).")
    ] = None,
    team: Annotated[
        str | None, Query(min_length=2, max_length=8, description="Franchise id, e.g. MI.")
    ] = None,
    venue: Annotated[
        str | None, Query(min_length=1, max_length=80, description="Venue id.")
    ] = None,
    innings: Annotated[
        int | None,
        Query(ge=1, le=4, description="1 batting first, 2 chasing (Tests: the innings, 1 to 4)."),
    ] = None,
    min_balls: Annotated[
        int | None, Query(ge=1, le=10_000, description="Balls a phase leader needs.")
    ] = None,
) -> PhaseAnalysis:
    """How innings are built, phase by phase: rates, the over-by-over shape, results by
    who batted first, toss decisions, phase leaders and run rates by ground."""
    try:
        return service.get_phases(
            db,
            season_from=first,
            season_to=last,
            team=team,
            venue=venue,
            innings=innings,
            min_balls=min_balls,
        )
    except service.PhaseDataMissingError:
        raise HTTPException(
            status_code=503, detail="phase analysis is not available in this build"
        ) from None
    except service.InvalidPhaseFilterError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
