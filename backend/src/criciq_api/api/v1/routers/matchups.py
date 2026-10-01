from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.repositories.matchups import MatchupSort
from criciq_api.schemas.matchups import (
    MatchupDetail,
    MatchupList,
    NextBallRequest,
    NextBallResponse,
    Phase,
)
from criciq_api.services import matchups as service
from criciq_api.services.players import InvalidWindowError

router = APIRouter(tags=["matchups"])

DB = Annotated[Database, Depends(get_db)]
FirstSeason = Annotated[
    int | None, Query(alias="from", ge=2008, le=2100, description="First season (inclusive).")
]
LastSeason = Annotated[
    int | None, Query(alias="to", ge=2008, le=2100, description="Last season (inclusive).")
]
PlayerId = Annotated[str | None, Query(max_length=32)]


def _errors(error: Exception) -> HTTPException:
    if isinstance(error, service.PlayerNotFoundError):
        return HTTPException(status_code=404, detail=f"player {error} not found")
    if isinstance(error, service.MatchupUnavailableError):
        return HTTPException(status_code=503, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("/matchups")
def list_matchups(
    db: DB,
    batter: PlayerId = None,
    bowler: PlayerId = None,
    first: FirstSeason = None,
    last: LastSeason = None,
    min_balls: Annotated[int, Query(ge=1, le=500)] = 12,
    sort: MatchupSort = "balls",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> MatchupList:
    """Batter-bowler pairs with raw, expected and shrunk strike rates.

    Filter by batter (the bowlers they faced) or by bowler (the batters they
    bowled to). ``batter_edge`` and ``bowler_edge`` rank by the matchup effect
    beyond each player's overall record.
    """
    try:
        return service.list_matchups(
            db,
            batter_id=batter,
            bowler_id=bowler,
            first=first,
            last=last,
            min_balls=min_balls,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except (service.MatchupUnavailableError, InvalidWindowError) as error:
        raise _errors(error) from None


@router.get("/matchups/{batter_id}/{bowler_id}")
def read_matchup(
    db: DB,
    batter_id: str,
    bowler_id: str,
    first: FirstSeason = None,
    last: LastSeason = None,
    phase: Phase | None = None,
) -> MatchupDetail:
    """Head-to-head record, the empirical-Bayes estimate and next-ball odds for a pair."""
    try:
        return service.get_matchup(db, batter_id, bowler_id, first, last, phase)
    except (
        service.PlayerNotFoundError,
        service.MatchupUnavailableError,
        InvalidWindowError,
    ) as error:
        raise _errors(error) from None


@router.post("/predict/next-ball")
def predict_next_ball(db: DB, request: NextBallRequest) -> NextBallResponse:
    """Outcome probabilities for the next ball in a given situation (model estimate)."""
    try:
        return service.predict_next_ball(db, request)
    except (service.PlayerNotFoundError, service.MatchupUnavailableError) as error:
        raise _errors(error) from None
