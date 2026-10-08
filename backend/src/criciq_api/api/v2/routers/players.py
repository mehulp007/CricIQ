"""Player Lab for any competition, and all T20 cricket together.

Directory, profiles, splits and similar players from the players database:
``{competition}`` is ipl, bbl, psl, cpl, sa20, t20i, odi, test or t20 (every T20
competition). Par is always the player's own competition's: a PSL strike rate is
judged against the PSL. Ratings use each competition's own shrinkage constants,
and win probability added comes from the model serving that competition.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from criciq_api.db import Database
from criciq_api.repositories.players import PlayerFilters, PlayerSort, RoleFilter
from criciq_api.schemas.competitions import CareerRatings, CompetitionList, PlayerCareers
from criciq_api.schemas.players import PlayerPage, PlayerProfile, PlayerSplits, SimilarPlayers
from criciq_api.services import competitions as competitions_service
from criciq_api.services import players as service

router = APIRouter(tags=["competitions"])


def get_players_db(request: Request) -> Database:
    db: Database | None = request.app.state.players_db
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="the players database has not been built; run `criciq-data export-players`",
        )
    return db


PlayersDB = Annotated[Database, Depends(get_players_db)]
Competition = Annotated[
    str,
    Path(
        pattern=r"^[a-z0-9]{2,8}$",
        description="ipl, bbl, psl, cpl, sa20, t20i, odi, test, or t20 for all T20 cricket.",
    ),
]
FirstSeason = Annotated[
    int | None, Query(alias="from", ge=2000, le=2100, description="First season (inclusive).")
]
LastSeason = Annotated[
    int | None, Query(alias="to", ge=2000, le=2100, description="Last season (inclusive).")
]


def _scoped(db: Database, competition: str) -> Database:
    try:
        return competitions_service.scoped(db, competition)
    except competitions_service.CompetitionNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"competition {competition} not found"
        ) from None


def _not_found(player_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"player {player_id} not found")


@router.get("/competitions")
def list_competitions(db: PlayersDB) -> CompetitionList:
    """The competitions with Player Lab data, with their season labels."""
    return competitions_service.list_competitions(db)


@router.get("/players/{player_id}")
def read_careers(db: PlayersDB, player_id: str) -> PlayerCareers:
    """A player's headline numbers in every competition, with all T20 cricket together
    after the T20 competitions."""
    try:
        return competitions_service.get_careers(db, player_id)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None


@router.get("/players/{player_id}/ratings")
def read_career_ratings(db: PlayersDB, player_id: str) -> CareerRatings:
    """A player's headline CricIQ Ratings in every competition, each among that
    competition's own players."""
    try:
        return competitions_service.get_career_ratings(db, player_id)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None


@router.get("/{competition}/players")
def list_players(
    db: PlayersDB,
    competition: Competition,
    q: Annotated[str | None, Query(max_length=64, description="Name search")] = None,
    role: RoleFilter | None = None,
    season: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    team: Annotated[str | None, Query(max_length=8, description="Team id, e.g. MI or IND")] = None,
    sort: PlayerSort = "matches",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PlayerPage:
    """Player directory of one competition; season and team filters scope the numbers."""
    filters = PlayerFilters(
        tokens=service.search_tokens(q),
        role=role,
        season=season,
        team=team.upper() if team else None,
        sort=sort,
    )
    return service.list_players(_scoped(db, competition), filters, page, page_size)


@router.get("/{competition}/players/{player_id}")
def read_player(
    db: PlayersDB,
    competition: Competition,
    player_id: str,
    first: FirstSeason = None,
    last: LastSeason = None,
) -> PlayerProfile:
    """Profile in one competition: batting and bowling against par, seasons, phases, form."""
    try:
        return service.get_profile(_scoped(db, competition), player_id, first, last)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None
    except service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/{competition}/players/{player_id}/splits")
def read_splits(
    db: PlayersDB,
    competition: Competition,
    player_id: str,
    first: FirstSeason = None,
    last: LastSeason = None,
) -> PlayerSplits:
    """Batting and bowling in one competition by phase, opponent type, position and more."""
    try:
        return service.get_splits(_scoped(db, competition), player_id, first, last)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None
    except service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/{competition}/players/{player_id}/similar")
def read_similar(
    db: PlayersDB,
    competition: Competition,
    player_id: str,
    first: FirstSeason = None,
    last: LastSeason = None,
) -> SimilarPlayers:
    """Players of one competition with the most similar batting and bowling styles."""
    try:
        return service.get_similar(_scoped(db, competition), player_id, first, last)
    except service.PlayerNotFoundError:
        raise _not_found(player_id) from None
    except service.InvalidWindowError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
