"""Tests: the chase calculator (a fourth-innings chase between any two sides)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.schemas.matches import ChaseCalculation, ChaseSides
from criciq_api.services import chase as service

router = APIRouter(prefix="/chase", tags=["chase"])

DB = Annotated[Database, Depends(get_db)]


@router.get("/sides")
def read_sides(db: DB) -> ChaseSides:
    """The Test sides and their ratings after the last Test."""
    try:
        return service.sides(db)
    except service.ChaseUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.get("")
def read_chase(
    db: DB,
    batting: Annotated[str, Query(max_length=8, description="The chasing side, e.g. IND.")],
    fielding: Annotated[str, Query(max_length=8, description="The fielding side.")],
    needed: Annotated[int, Query(ge=1, le=1000, description="Runs needed.")],
    wickets: Annotated[int, Query(ge=1, le=10, description="Wickets in hand.")],
    overs: Annotated[float, Query(ge=0, le=450, description="Overs left.")],
    venue: Literal["home", "away", "neutral"] = "neutral",
) -> ChaseCalculation:
    """The chasing side's chances of winning, drawing and losing a fourth-innings chase."""
    try:
        return service.calculate(db, batting, fielding, venue, needed, wickets, overs)
    except service.ChaseUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
