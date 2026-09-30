"""Checks against the full local warehouse. Skipped when it has not been built
(e.g. in CI); run `criciq-data run` locally to exercise them."""

import duckdb
import pytest

from criciq_core import paths
from criciq_pipelines.validation import validate

WAREHOUSE = paths.warehouse_path()

pytestmark = pytest.mark.skipif(not WAREHOUSE.exists(), reason="full warehouse not built")


def test_full_warehouse_validates() -> None:
    assert validate(WAREHOUSE).passed


def test_every_season_since_2008_is_present() -> None:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        years = [r[0] for r in con.execute("SELECT year FROM seasons ORDER BY year").fetchall()]
    finally:
        con.close()
    assert years[0] == 2008
    assert years == list(range(2008, years[-1] + 1))
