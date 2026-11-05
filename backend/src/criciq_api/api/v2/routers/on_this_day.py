from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from criciq_api.db import Database, get_db
from criciq_api.schemas.on_this_day import OnThisDay
from criciq_api.services import on_this_day as service

router = APIRouter(prefix="/on-this-day", tags=["on this day"])

DB = Annotated[Database, Depends(get_db)]


@router.get("")
def read_on_this_day(
    db: DB,
    month: Annotated[int, Query(ge=1, le=12)],
    day: Annotated[int, Query(ge=1, le=31)],
) -> OnThisDay:
    """Every match that started on this calendar date in any year, most notable first, with
    its best innings, best bowling and biggest win-probability swing."""
    try:
        return service.get_day(db, month, day)
    except service.InvalidDateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
