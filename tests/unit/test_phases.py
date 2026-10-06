from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from criciq_core.phases import (
    MODEL_FORMAT,
    check_model_format,
    default_phase_config,
    load_phase_config,
    model_phases,
)


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
    with pytest.raises(KeyError, match="Hundred"):
        default_phase_config().for_format("Hundred")


def test_odi_phases() -> None:
    odi = default_phase_config().for_format("ODI")
    assert odi.overs == 50
    assert odi.phase_for_over_index(9).key == "powerplay"
    assert odi.phase_for_over_index(10).key == "middle"
    assert odi.phase_for_over_index(49).key == "death"


def test_test_phases_are_open_ended() -> None:
    test = default_phase_config().for_format("Test")
    assert test.overs is None
    assert test.phase_for_over_index(0).key == "new_ball"
    assert test.phase_for_over_index(79).key == "middle"
    assert test.phase_for_over_index(80).key == "second_new_ball"
    assert test.phase_for_over_index(400).key == "second_new_ball"
    assert test.sql_case("o") == (
        "CASE WHEN o + 1 <= 20 THEN 'new_ball' WHEN o + 1 <= 80 THEN 'middle' "
        "ELSE 'second_new_ball' END"
    )


def test_unlimited_format_needs_one_open_phase(tmp_path: Path) -> None:
    bad = tmp_path / "phases.yaml"
    bad.write_text(
        """
formats:
  X:
    phases:
      - {key: a, label: A, first_over: 1}
      - {key: b, label: B, first_over: 5}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="open phase"):
        load_phase_config(bad)


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


def test_sql_case_agrees_with_python() -> None:
    t20 = default_phase_config().for_format("T20")
    case = t20.sql_case("o")
    con = duckdb.connect()
    rows = con.execute(f"SELECT o, {case} FROM range(0, 20) t(o) ORDER BY o").fetchall()
    assert all(t20.phase_for_over_index(o).key == key for o, key in rows)
    # Overs beyond the format (umpire miscounts) fall in the last phase.
    assert con.execute(f"SELECT {case} FROM (SELECT 21 AS o)").fetchone() == ("death",)


@pytest.mark.parametrize(
    ("fmt", "over_index", "phase"),
    [
        ("T20", 6, "middle"),
        ("T20", 15, "death"),
        ("ODI", 6, "powerplay"),
        ("ODI", 15, "middle"),
        ("ODI", 45, "death"),
        ("Test", 15, "new_ball"),
        ("Test", 45, "middle"),
        ("Test", 150, "second_new_ball"),
    ],
)
def test_sql_case_follows_each_rows_format(fmt: str, over_index: int, phase: str) -> None:
    case = default_phase_config().sql_case("o", "f")
    row = duckdb.connect().execute(f"SELECT {case} FROM (SELECT ? AS f, ? AS o)", [fmt, over_index])
    assert row.fetchone() == (phase,)


def test_models_use_t20_phases() -> None:
    assert MODEL_FORMAT == "T20"
    assert model_phases() == default_phase_config().for_format("T20")


def test_check_model_format_refuses_other_formats() -> None:
    check_model_format(["T20", "T20"])
    check_model_format([])
    with pytest.raises(ValueError, match="ODI, Test"):
        check_model_format(["T20", "Test", "ODI"])
