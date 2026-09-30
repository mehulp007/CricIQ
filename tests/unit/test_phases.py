from pathlib import Path

import pytest
from pydantic import ValidationError

from criciq_core.phases import default_phase_config, load_phase_config


def test_repo_config_loads_t20() -> None:
    t20 = default_phase_config().for_format("T20")
    assert t20.overs == 20
    assert [p.key for p in t20.phases] == ["powerplay", "middle", "death"]


@pytest.mark.parametrize(
    ("over_index", "phase"),
    [
        (0, "powerplay"),
        (5, "powerplay"),
        (6, "middle"),
        (14, "middle"),
        (15, "death"),
        (19, "death"),
    ],
)
def test_phase_for_over_index(over_index: int, phase: str) -> None:
    t20 = default_phase_config().for_format("T20")
    assert t20.phase_for_over_index(over_index).key == phase


def test_phase_for_over_index_out_of_range() -> None:
    t20 = default_phase_config().for_format("T20")
    with pytest.raises(ValueError, match="outside"):
        t20.phase_for_over_index(20)


def test_unknown_format() -> None:
    with pytest.raises(KeyError, match="ODI"):
        default_phase_config().for_format("ODI")


def test_config_must_cover_every_over(tmp_path: Path) -> None:
    bad = tmp_path / "phases.yaml"
    bad.write_text(
        """
formats:
  T20:
    overs: 20
    phases:
      - {key: powerplay, label: Powerplay, first_over: 1, last_over: 6}
      - {key: death, label: Death, first_over: 16, last_over: 20}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="cover every over"):
        load_phase_config(bad)
