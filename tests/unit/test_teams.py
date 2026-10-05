import pytest

from criciq_core.teams import FORM_PRIOR, form_probability, log5


def test_form_is_shrunk_toward_even() -> None:
    assert form_probability(0, 0) == 0.5
    assert 0.5 < form_probability(14, 14) < 0.6
    assert form_probability(14, 14) == pytest.approx((14 + FORM_PRIOR / 2) / (14 + FORM_PRIOR))
    assert form_probability(3, 14) < 0.5


def test_log5() -> None:
    assert log5(0.6, 0.6) == pytest.approx(0.5)
    assert log5(0.7, 0.5) == pytest.approx(0.7)
    assert log5(0.6, 0.4) == pytest.approx(1 - log5(0.4, 0.6))
    assert log5(0.0, 0.0) == 0.5
