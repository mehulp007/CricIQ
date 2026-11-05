from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from criciq_api.db import Database, get_db
from criciq_api.schemas.records import RecordList, RecordsHub
from criciq_api.services import records as service

router = APIRouter(prefix="/records", tags=["records"])

DB = Annotated[Database, Depends(get_db)]


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="records are not available in this build")


@router.get("")
def read_records(db: DB) -> RecordsHub:
    """Every record in the competition's ball-by-ball data, with its holder."""
    try:
        return service.get_hub(db)
    except service.RecordDataMissingError:
        raise _unavailable() from None


@router.get("/{key}")
def read_record(
    db: DB,
    key: Annotated[str, Path(min_length=3, max_length=60, pattern=r"^[a-z0-9-]+$")],
    first: Annotated[
        int | None, Query(alias="from", ge=2000, le=2100, description="First season (inclusive).")
    ] = None,
    last: Annotated[
        int | None, Query(alias="to", ge=2000, le=2100, description="Last season (inclusive).")
    ] = None,
    team: Annotated[
        str | None, Query(min_length=2, max_length=8, description="Franchise id, e.g. MI.")
    ] = None,
    opponent: Annotated[
        str | None, Query(min_length=2, max_length=8, description="Opponent franchise id.")
    ] = None,
    venue: Annotated[
        str | None, Query(min_length=1, max_length=80, description="Venue id.")
    ] = None,
    wicket: Annotated[
        int | None, Query(ge=1, le=10, description="Partnerships for one wicket.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIMIT)] = 100,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> RecordList:
    """One record's ranked list (equal values share a rank), with filters."""
    try:
        return service.get_record(
            db,
            key,
            season_from=first,
            season_to=last,
            team=team,
            opponent=opponent,
            venue=venue,
            wicket=wicket,
            limit=limit,
            offset=offset,
        )
    except service.RecordDataMissingError:
        raise _unavailable() from None
    except service.RecordNotFoundError:
        raise HTTPException(status_code=404, detail=f"no record {key!r} here") from None
    except service.InvalidRecordFilterError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
