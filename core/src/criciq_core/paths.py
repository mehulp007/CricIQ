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


def cricket_warehouse_path() -> Path:
    """The warehouse holding every competition."""
    return data_dir() / "warehouse" / "cricket.duckdb"


def warehouse_path(competition: str = "IPL") -> Path:
    """One competition's warehouse in the v1 shape (see criciq_pipelines.scope)."""
    return data_dir() / "warehouse" / f"{competition.lower()}.duckdb"


def exports_dir() -> Path:
    return data_dir() / "exports"


def serving_path() -> Path:
    """The read-only database the API serves."""
    return exports_dir() / "serving.duckdb"


def players_path() -> Path:
    """Player Lab tables for every T20 competition and all T20 (criciq_pipelines.player_db)."""
    return exports_dir() / "players.duckdb"


def sync_dir() -> Path:
    """The ingest log and the record of every data update (criciq_pipelines.sync)."""
    return data_dir() / "sync"


def models_dir() -> Path:
    override = os.environ.get("CRICIQ_MODELS_DIR")
    return Path(override).resolve() if override else repo_root() / "models"
