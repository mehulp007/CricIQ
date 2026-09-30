from __future__ import annotations

from fastapi import APIRouter

from criciq_api import __version__
from criciq_api.schemas.meta import Meta

router = APIRouter(tags=["meta"])


@router.get("/meta")
def get_meta() -> Meta:
    return Meta(api_version="v1", app_version=__version__, data_version=None, model_versions={})
