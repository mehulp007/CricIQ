from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from criciq_api.db import Database, get_db
from criciq_api.schemas.simulation import (
    SimSeason,
    SimSquad,
    SimulationRequest,
    SimulationResult,
    SimXI,
    StateRequest,
    StateResult,
    XIRequest,
)
from criciq_api.services import simulation as service

router = APIRouter(prefix="/simulate", tags=["simulation"])

DB = Annotated[Database, Depends(get_db)]


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="the simulator is not available in this build")


@router.get("/seasons")
def read_seasons(db: DB) -> list[SimSeason]:
    """Every season, newest first, with the sides that played in it."""
    try:
        return service.seasons(db)
    except service.SimulationUnavailableError:
        raise _unavailable() from None


@router.get("/squad/{season}/{franchise_id}")
def read_squad(db: DB, season: int, franchise_id: str) -> SimSquad:
    """Everyone who played for a side in a season, with its last XI that season."""
    try:
        return service.squad(db, season, franchise_id)
    except service.SimulationUnavailableError:
        raise _unavailable() from None
    except service.UnknownSquadError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.get("/xi/{franchise_id}")
def read_latest_xi(db: DB, franchise_id: str) -> SimXI:
    """A franchise's most recent playing XI, in batting order, with its bowling options."""
    try:
        return service.latest_xi(db, franchise_id)
    except service.SimulationUnavailableError:
        raise _unavailable() from None
    except service.UnknownPlayerError:
        raise HTTPException(status_code=404, detail=f"team {franchise_id} not found") from None


@router.post("/xi")
def order_xi(db: DB, request: XIRequest) -> SimXI:
    """Any players in their usual batting order, with default bowling options."""
    try:
        return service.xi_for_players(db, request.player_ids)
    except service.SimulationUnavailableError:
        raise _unavailable() from None
    except service.UnknownPlayerError as error:
        raise HTTPException(status_code=404, detail=f"player {error} not found") from None


@router.post("/match")
def simulate_match(db: DB, request: SimulationRequest) -> SimulationResult:
    """Up to 10,000 Monte Carlo matches between two XIs (model simulation)."""
    try:
        return service.simulate(db, request)
    except service.SimulationUnavailableError:
        raise _unavailable() from None
    except service.UnknownPlayerError as error:
        raise HTTPException(status_code=404, detail=f"player {error} not found") from None
    except service.InvalidSideError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except service.UnknownSquadError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.post("/state")
def simulate_state(db: DB, request: StateRequest) -> StateResult:
    """What if a replay position were different: the rest of the match simulated from
    the real and the edited score (model simulation)."""
    try:
        return service.what_if(db, request)
    except service.SimulationUnavailableError:
        raise _unavailable() from None
    except service.StateNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
