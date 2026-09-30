"""Filesystem locations used across CricIQ.

The repository root is inferred from this file's location (workspace/editable
installs). Deployed environments override it with ``CRICIQ_ROOT``.
"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    override = os.environ.get("CRICIQ_ROOT")
    if override:
        return Path(override).resolve()
    # core/src/criciq_core/paths.py -> parents[3] is the repository root
    return Path(__file__).resolve().parents[3]


def config_dir() -> Path:
    return repo_root() / "config"


def reference_dir() -> Path:
    """Curated, version-controlled reference data (e.g. player attributes)."""
    return repo_root() / "reference"


def data_dir() -> Path:
    override = os.environ.get("CRICIQ_DATA_DIR")
    return Path(override).resolve() if override else repo_root() / "data"


def raw_dir() -> Path:
    return data_dir() / "raw"


def interim_dir() -> Path:
    return data_dir() / "interim"


def warehouse_path() -> Path:
    return data_dir() / "warehouse" / "criciq.duckdb"


def exports_dir() -> Path:
    return data_dir() / "exports"


def models_dir() -> Path:
    override = os.environ.get("CRICIQ_MODELS_DIR")
    return Path(override).resolve() if override else repo_root() / "models"
