from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from criciq_api.db import Database, get_db
from criciq_api.schemas.studio import StudioOptions, StudioResult, StudioSpec
from criciq_api.services import studio as service

router = APIRouter(prefix="/studio", tags=["studio"])

DB = Annotated[Database, Depends(get_db)]


@router.get("/options")
def read_options(db: DB) -> StudioOptions:
    """What Chart Studio's pickers offer: datasets with their measures, groupings and
    filters, and the competition's teams, grounds, seasons and phases."""
    return service.get_options(db)


@router.post("/query")
def run_query(db: DB, spec: StudioSpec) -> StudioResult:
    """Run a chart's spec: its figures per group (and per series, with a split), ranked,
    with the query that computed them."""
    try:
        return service.run_spec(db, spec)
    except service.InvalidSpecError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except service.StudioDataMissingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except service.StudioTimeoutError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
