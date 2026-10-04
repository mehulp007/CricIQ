from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.repositories.players import PlayerFilters, PlayerSort, RoleFilter
from criciq_api.schemas.players import PlayerPage, PlayerProfile, PlayerSplits, SimilarPlayers
from criciq_api.services import players as service

router = APIRouter(prefix="/players", tags=["players"])

DB = Annotated[Database, Depends(get_db)]
FirstSeason = Annotated[
    int | None, Query(alias="from", ge=2008, le=2100, description="First season (inclusive).")
]
LastSeason = Annotated[
    int | None, Query(alias="to", ge=2008, le=2100, description="Last season (inclusive).")
]


@router.get("")
def list_players(
    db: DB,
    q: Annotated[str | None, Query(max_length=64, description="Name search")] = None,
    role: RoleFilter | None = None,
    season: Annotated[int | None, Query(ge=2008, le=2100)] = None,
    team: Annotated[str | None, Query(max_length=8, description="Franchise id, e.g. MI")] = None,
    sort: PlayerSort = "matches",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PlayerPage:
    """Player directory with headline numbers; season and team filters scope the numbers."""
    filters = PlayerFilters(
        tokens=service.search_tokens(q),
        role=role,
        season=season,
        team=team.upper() if team else None,
        sort=sort,
    )
    return service.list_players(db, filters, page, page_size)


def _not_found(player_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"player {player_id} not found")


@router.get("/{player_id}")
def read_player(
    db: DB, player_id: str, first: FirstSeason = None, last: LastSeason = None
) -> PlayerProfile:
    """Profile: batting and bowling against par, seasons, phases, ratings and recent form."""
    try:
        return service.get_profile(db, player_id, first, last)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None
    except service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/{player_id}/splits")
def read_splits(
    db: DB, player_id: str, first: FirstSeason = None, last: LastSeason = None
) -> PlayerSplits:
    """Batting and bowling split by phase, opponent type, position, venue, opposition and more."""
    try:
        return service.get_splits(db, player_id, first, last)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None
    except service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/{player_id}/similar")
def read_similar(
    db: DB, player_id: str, first: FirstSeason = None, last: LastSeason = None
) -> SimilarPlayers:
    """Players with the most similar batting and bowling styles in the same seasons."""
    try:
        return service.get_similar(db, player_id, first, last)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None
    except service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
