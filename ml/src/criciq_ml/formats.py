"""Where each model group's models live.

A model group (``criciq_core.groups``) is a set of competitions with models of
their own: ``config/models/<group>/`` holds their training configuration and
``models/<group>/`` their versions (the IPL's keep v1's places, ``models/<model>/``
with ``CURRENT.IPL``). The code reads the current group
(:func:`use_group`) to find them.

Outside any group, the folders are the format's (``use_format``): the pooled T20
models of V2-3 in ``config/models/`` and ``models/``, the ODIs' in ``odi/``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from criciq_core import paths
from criciq_core.groups import ModelGroup, group
from criciq_core.phases import MODEL_FORMAT, model_format, use_format

_GROUP: ContextVar[ModelGroup | None] = ContextVar("criciq_model_group", default=None)
_SERVING: ContextVar[bool] = ContextVar("criciq_model_serving", default=False)


@contextmanager
def use_group(which: ModelGroup | str, *, serving: bool = False) -> Iterator[ModelGroup]:
    """Work with one group's models inside this block (and its format's rules).

    ``serving``: scoring, where a model the group has not trained yet falls back to
    the pooled T20 version (see :mod:`criciq_ml.registry`). Training and reports
    never fall back.
    """
    found = group(which) if isinstance(which, str) else which
    with use_format(found.format):
        token = _GROUP.set(found)
        serving_token = _SERVING.set(serving)
        try:
            yield found
        finally:
            _SERVING.reset(serving_token)
            _GROUP.reset(token)


def current_group() -> ModelGroup | None:
    return _GROUP.get()


def serving() -> bool:
    """Whether models are being looked up for scoring (pooled fallback allowed)."""
    return _SERVING.get()


def folder() -> str | None:
    """The current models' folder (``"leagues"``, ``"odi"``), or None for ``models/``."""
    found = current_group()
    if found is not None:
        return found.models or None
    current = model_format()
    return None if current == MODEL_FORMAT else current.lower()


def _config_folder() -> str | None:
    found = current_group()
    if found is not None:
        return found.config
    current = model_format()
    return None if current == MODEL_FORMAT else current.lower()


def config_path(name: str) -> Path:
    """A model's training configuration for the current group (or format)."""
    base = paths.config_dir() / "models"
    sub = _config_folder()
    return (base if sub is None else base / sub) / f"{name}.yaml"


def models_root() -> Path:
    """The registry of the current group's (or format's) models."""
    sub = folder()
    return paths.models_dir() if sub is None else paths.models_dir() / sub


def legacy_root() -> Path:
    """The pooled T20 models' registry (``models/``), the fallback while scoring."""
    return paths.models_dir()


def default_pointer() -> str | None:
    """The competition whose pointer marks the current group's versions (the IPL's)."""
    found = current_group()
    return None if found is None else found.pointer
