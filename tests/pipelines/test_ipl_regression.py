"""IPL regression gate: the IPL warehouse and scored serving database built
from the fixture matches must not change unless a change is intended.

Pipeline tables are compared by exact checksums. The model outputs are compared
value by value with tolerances, because numpy and LightGBM differ in the last
bits between machines (see ``criciq_pipelines.checksums``).

Regenerate after an intended change with
``CRICIQ_UPDATE_CHECKSUMS=1 uv run pytest tests/pipelines/test_ipl_regression.py``
and review the diff of tests/fixtures/ipl_checksums.json and ipl_model_outputs/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pytest

from criciq_pipelines.checksums import (
    differences,
    save_values,
    table_checksums,
    value_differences,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXPECTED = FIXTURES / "ipl_checksums.json"
MODEL_OUTPUTS = FIXTURES / "ipl_model_outputs"
# Written by `criciq-ml score`.
MODEL_TABLES = (
    "ball_model_terms",
    "matchup_cells",
    "models",
    "player_wpa",
    "score_projections",
    "wp_predictions",
)
UPDATE = bool(os.environ.get("CRICIQ_UPDATE_CHECKSUMS"))


def _check(name: str, db: Path, skip: tuple[str, ...] = ()) -> None:
    actual = table_checksums(db, skip=skip)
    saved = json.loads(EXPECTED.read_text("utf-8")) if EXPECTED.exists() else {}
    if UPDATE:
        saved[name] = actual
        EXPECTED.write_text(
            json.dumps(saved, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        return
    assert name in saved, f"no saved checksums for {name}; regenerate them"
    assert differences(saved[name], actual) == []


def test_ipl_warehouse_unchanged(fixture_warehouse: Path) -> None:
    _check("warehouse", fixture_warehouse)
    if UPDATE:
        pytest.skip("checksums updated")


def test_ipl_serving_unchanged(fixture_scored_serving_db: Path) -> None:
    _check("serving", fixture_scored_serving_db, skip=MODEL_TABLES)
    if UPDATE:
        save_values(fixture_scored_serving_db, MODEL_TABLES, MODEL_OUTPUTS)
        pytest.skip("checksums updated")
    assert value_differences(fixture_scored_serving_db, MODEL_TABLES, MODEL_OUTPUTS) == []


def test_checksums_ignore_last_bit_float_noise(tmp_path: Path) -> None:
    # DuckDB's parallel sums change the last bits, also inside JSON columns.
    def build(name: str, x: float, info: str) -> Path:
        db = tmp_path / name
        con = duckdb.connect(str(db))
        con.execute("CREATE TABLE t (x DOUBLE, info JSON)")
        con.execute("INSERT INTO t VALUES (?, ?)", [x, info])
        con.close()
        return db

    a = build("a.duckdb", 0.1 + 0.2, '{"q": [0.30000000000000004, -1e-12], "k": 2}')
    b = build("b.duckdb", 0.3, '{"k": 2, "q": [0.3, 0.0]}')
    c = build("c.duckdb", 0.3, '{"k": 2, "q": [0.31, 0.0]}')
    assert differences(table_checksums(a), table_checksums(b)) == []
    assert differences(table_checksums(a), table_checksums(c)) == ["t: md5 differs"]


def test_model_outputs_allow_machine_noise_only(tmp_path: Path) -> None:
    def build(name: str, rows: list[tuple[int, float, float, int]]) -> Path:
        db = tmp_path / name
        con = duckdb.connect(str(db))
        con.execute(
            "CREATE TABLE wp_predictions "
            "(seq_no INTEGER, wp_team_a DOUBLE, momentum FLOAT, pressure UTINYINT)"
        )
        con.executemany("INSERT INTO wp_predictions VALUES (?, ?, ?, ?)", rows)
        con.close()
        return db

    base = [(i, i / 1000, i / 7, i % 100) for i in range(1000)]
    saved = tmp_path / "saved"
    save_values(build("base.duckdb", base), ["wp_predictions"], saved)

    def diff(rows: list[tuple[int, float, float, int]]) -> list[str]:
        return value_differences(
            build(f"{len(list(tmp_path.iterdir()))}.duckdb", rows), ["wp_predictions"], saved
        )

    noisy = [(s, wp + 1e-12, m * (1 + 1e-7), p) for s, wp, m, p in base]
    noisy[10] = (10, noisy[10][1], noisy[10][2], 11)  # a percentile tipped by one
    assert diff(noisy) == []

    moved = list(base)
    moved[500] = (500, 0.6, base[500][2], base[500][3])
    (only,) = diff(moved)
    assert only.startswith("wp_predictions.wp_team_a: values differ beyond machine variation")

    shifted = [(s, wp, m, (p + 1) % 256) for s, wp, m, p in base]  # every percentile moved
    (only,) = diff(shifted)
    assert only.startswith("wp_predictions.pressure: values differ: 1000 of 1000")

    jumped = list(base)
    jumped[3] = (3, base[3][1], base[3][2], base[3][3] + 5)
    (only,) = diff(jumped)
    assert only.startswith("wp_predictions.pressure: values differ beyond machine variation")

    # Measured between Windows and Linux: a few leverage-like values move by under 1%.
    os_maths = list(base)
    for k in (40, 103, 110):
        s, wp, m, p = base[k]
        os_maths[k] = (s, wp * 1.005, m, p)
    assert diff(os_maths) == []


def test_explanations_may_resplit_a_total_on_a_few_balls(tmp_path: Path) -> None:
    def build(name: str, rows: list[tuple[int, list[float]]]) -> Path:
        db = tmp_path / name
        con = duckdb.connect(str(db))
        con.execute("CREATE TABLE wp_predictions (seq_no INTEGER, factors FLOAT[])")
        con.executemany("INSERT INTO wp_predictions VALUES (?, ?)", rows)
        con.close()
        return db

    base = [(i, [-33.5, 0.2, 0.3]) for i in range(1000)]
    saved = tmp_path / "saved"
    save_values(build("base.duckdb", base), ["wp_predictions"], saved)

    def diff(name: str, rows: list[tuple[int, list[float]]]) -> list[str]:
        return value_differences(build(name, rows), ["wp_predictions"], saved)

    # Seen on CI: one ball split the same -33.0 points differently.
    resplit = list(base)
    resplit[46] = (46, [-33.9, 0.6, 0.3])
    assert diff("resplit.duckdb", resplit) == []

    moved_total = list(base)
    moved_total[46] = (46, [-30.0, 0.2, 0.3])
    (only,) = diff("total.duckdb", moved_total)
    assert only.startswith("wp_predictions.factors: values differ beyond machine variation")

    many = [(i, [-33.9, 0.6, 0.3]) for i in range(1000)]
    (only,) = diff("many.duckdb", many)
    assert only.startswith("wp_predictions.factors: values differ: 1000 of 1000")
