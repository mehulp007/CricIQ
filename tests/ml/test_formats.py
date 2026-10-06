from pathlib import Path

import pytest

from criciq_ml.ball_outcome import load_balls
from criciq_ml.data import load_inputs


def test_models_read_the_t20_scope(fixture_warehouse: Path) -> None:
    assert len(load_inputs(fixture_warehouse).matches) > 0


def test_models_refuse_a_database_with_other_formats(fixture_full_warehouse: Path) -> None:
    # The full warehouse holds ODIs and Tests: the T20 models must not read them.
    with pytest.raises(ValueError, match="ODI, Test"):
        load_inputs(fixture_full_warehouse)
    with pytest.raises(ValueError, match="ODI, Test"):
        load_balls(fixture_full_warehouse)
