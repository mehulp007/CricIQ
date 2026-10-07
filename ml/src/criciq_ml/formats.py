"""Where each format's models live.

The T20 models keep their v1 places (``config/models/<model>.yaml``,
``models/<model>/``). Another format's models sit in a folder named after it
(``config/models/odi/``, ``models/odi/``), and the code reads the current format
(``criciq_core.phases.use_format``) to find them.
"""

from __future__ import annotations

from pathlib import Path

from criciq_core import paths
from criciq_core.phases import MODEL_FORMAT, model_format


def folder() -> str | None:
    """The current format's folder (``"odi"``), or None for the T20 models."""
    current = model_format()
    return None if current == MODEL_FORMAT else current.lower()


def _under(base: Path) -> Path:
    sub = folder()
    return base if sub is None else base / sub


def config_path(name: str) -> Path:
    """A model's training configuration in the current format."""
    return _under(paths.config_dir() / "models") / f"{name}.yaml"


def models_root() -> Path:
    """The registry of the current format's models."""
    return _under(paths.models_dir())
