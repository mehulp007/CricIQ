import math

import pytest

from criciq_core.cricket import (
    legal_balls_from_overs,
    overs_notation,
    required_run_rate,
    run_rate,
)


@pytest.mark.parametrize(
    ("balls", "expected"),
    [(0, "0.0"), (5, "0.5"), (6, "1.0"), (99, "16.3"), (120, "20.0")],
)
def test_overs_notation(balls: int, expected: str) -> None:
    assert overs_notation(balls) == expected


@pytest.mark.parametrize("balls", [0, 1, 6, 57, 99, 119, 120])
def test_overs_round_trip(balls: int) -> None:
    assert legal_balls_from_overs(overs_notation(balls)) == balls


def test_overs_notation_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        overs_notation(-1)


@pytest.mark.parametrize("bad", ["16.6", "16.7", "-1.0"])
def test_legal_balls_from_overs_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid overs"):
        legal_balls_from_overs(bad)


def test_legal_balls_from_whole_overs() -> None:
    assert legal_balls_from_overs("20") == 120


def test_run_rate() -> None:
    assert run_rate(146, 99) == pytest.approx(8.848, abs=1e-3)
    assert run_rate(0, 0) is None


def test_required_run_rate() -> None:
    assert required_run_rate(36, 18) == pytest.approx(12.0)
    assert required_run_rate(0, 18) is None
    assert required_run_rate(-4, 18) is None
    assert math.isinf(required_run_rate(5, 0) or 0.0)
