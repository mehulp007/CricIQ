"""Checks against the full local warehouse. Skipped when it has not been built
(e.g. in CI); run `criciq-data run` locally to exercise them."""

import duckdb
import pytest

from criciq_core import paths
from criciq_core.publish import current
from criciq_pipelines.events import check_events
from criciq_pipelines.reference import load_events
from criciq_pipelines.validation import validate

WAREHOUSE = paths.warehouse_path()
ALL = paths.cricket_warehouse_path()

pytestmark = pytest.mark.skipif(
    not (WAREHOUSE.exists() and ALL.exists()), reason="full warehouse not built"
)


def test_full_warehouse_validates() -> None:
    assert validate(ALL).passed


def test_every_season_since_2008_is_present() -> None:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        years = [r[0] for r in con.execute("SELECT year FROM seasons ORDER BY year").fetchall()]
    finally:
        con.close()
    assert years[0] == 2008
    assert years == list(range(2008, years[-1] + 1))


@pytest.mark.parametrize("competition", ["TEST", "ODI", "T20I"])
def test_every_known_series_and_tournament_result_is_checked(competition: str) -> None:
    """Each known result in config/events.yaml is covered by the full data and reproduced;
    on fixtures they pass uncovered, so only the full data shows none is silently skipped."""
    serving = current(paths.serving_path(competition))
    if not serving.exists():
        pytest.skip(f"{serving.name} not exported")
    con = duckdb.connect(str(serving), read_only=True)
    try:
        checks = check_events(con, competition, load_events())
    finally:
        con.close()
    assert checks
    assert [c.description for c in checks if not c.covered] == []
    assert [c.description for c in checks if not c.passed] == []
