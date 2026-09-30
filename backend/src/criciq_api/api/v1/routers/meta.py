from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from criciq_api.db import Database, get_db
from criciq_api.schemas.meta import Meta
from criciq_api.services.meta import get_meta

router = APIRouter(tags=["meta"])


@router.get("/meta")
def read_meta(db: Annotated[Database, Depends(get_db)]) -> Meta:
    """Dataset version and the seasons, franchises and venues available for filtering."""
    return get_meta(db)
