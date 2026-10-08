"""The API, /api/v2: everything the site shows, for any competition it serves.

``/api/v2/{competition}/...`` (``ipl``, ``bbl``, ``psl``, ``cpl``, ``sa20``,
``t20i``, ``odi``, ``test``) reads that competition's serving database
(``criciq_api.db.get_db``); the Player Lab routes read the players database, which
also has ``t20`` (every T20 competition together) and players' careers across
competitions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from criciq_api.api.v2.routers import chase, matches, matchups, meta, players, simulation, teams


def _competition(competition: players.Competition) -> str:
    """Declares (and validates) the ``{competition}`` every route below shares."""
    return competition


api_router = APIRouter(prefix="/api/v2")
api_router.include_router(players.router)

competition_router = APIRouter(prefix="/{competition}", dependencies=[Depends(_competition)])
for module in (meta, matches, matchups, teams, simulation, chase):
    competition_router.include_router(module.router)
api_router.include_router(competition_router)
