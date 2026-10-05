"""IPL regression gate: the IPL warehouse and scored serving database built
from the fixture matches must not change unless a change is intended.

Regenerate after an intended change with
``CRICIQ_UPDATE_CHECKSUMS=1 uv run pytest tests/pipelines/test_ipl_regression.py``
and review the diff of tests/fixtures/ipl_checksums.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from criciq_pipelines.checksums import differences, table_checksums

EXPECTED = Path(__file__).resolve().parents[1] / "fixtures" / "ipl_checksums.json"


def _check(name: str, db: Path) -> None:
    actual = table_checksums(db)
    saved = json.loads(EXPECTED.read_text("utf-8")) if EXPECTED.exists() else {}
    if os.environ.get("CRICIQ_UPDATE_CHECKSUMS"):
        saved[name] = actual
        EXPECTED.write_text(
            json.dumps(saved, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        pytest.skip("checksums updated")
    assert name in saved, f"no saved checksums for {name}; regenerate them"
    assert differences(saved[name], actual) == []


def test_ipl_warehouse_unchanged(fixture_warehouse: Path) -> None:
    _check("warehouse", fixture_warehouse)


def test_ipl_serving_unchanged(fixture_scored_serving_db: Path) -> None:
    _check("serving", fixture_scored_serving_db)
