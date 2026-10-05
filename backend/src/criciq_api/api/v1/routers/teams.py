from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from criciq_api.db import Database, get_db
from criciq_api.schemas.teams import Standings, TeamHeadToHead, TeamProfile, TeamsOverview
from criciq_api.services import players as player_service
from criciq_api.services import teams as service

router = APIRouter(prefix="/teams", tags=["teams"])

DB = Annotated[Database, Depends(get_db)]
FirstSeason = Annotated[
    int | None, Query(alias="from", ge=2008, le=2100, description="First season (inclusive).")
]
LastSeason = Annotated[
    int | None, Query(alias="to", ge=2008, le=2100, description="Last season (inclusive).")
]
FranchiseId = Annotated[str, Query(min_length=2, max_length=8, description="Franchise id, e.g. MI")]


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="team analytics are not available in this build")


@router.get("")
def read_overview(db: DB) -> TeamsOverview:
    """Every franchise's record and titles, champions by season and league-wide trends."""
    try:
        return service.get_overview(db)
    except service.TeamDataMissingError:
        raise _unavailable() from None


@router.get("/standings/{season}")
def read_standings(db: DB, season: Annotated[int, Path(ge=2008, le=2100)]) -> Standings:
    """The league table for a season (points, net run rate, finish) and its playoffs."""
    try:
        return service.get_standings(db, season)
    except service.TeamDataMissingError:
        raise _unavailable() from None
    except service.SeasonNotFoundError:
        raise HTTPException(status_code=404, detail=f"season {season} not found") from None


@router.get("/h2h")
def read_head_to_head(
    db: DB, a: FranchiseId, b: FranchiseId, first: FirstSeason = None, last: LastSeason = None
) -> TeamHeadToHead:
    """Head-to-head record of two franchises, against what their form predicts."""
    try:
        return service.get_head_to_head(db, a, b, first, last)
    except service.TeamDataMissingError:
        raise _unavailable() from None
    except service.TeamNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"team {error} not found") from None
    except (service.SameTeamError, player_service.InvalidWindowError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/{franchise_id}")
def read_team(
    db: DB, franchise_id: str, first: FirstSeason = None, last: LastSeason = None
) -> TeamProfile:
    """A franchise's seasons, results by situation, phase profile, players and swings."""
    try:
        return service.get_profile(db, franchise_id, first, last)
    except service.TeamDataMissingError:
        raise _unavailable() from None
    except service.TeamNotFoundError:
        raise HTTPException(status_code=404, detail=f"team {franchise_id} not found") from None
    except player_service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
