"""Content checksums of every table in a DuckDB file, for regression gates.

Each table's rows are rendered as text, sorted and hashed, so a checksum
depends only on content: not on row order, file layout or build time. Doubles
are rounded to 9 decimals first: DuckDB sums them in parallel, in an order that
can change the last bits from run to run. Numbers inside JSON columns are
rounded the same way. The ``meta`` table (build timestamps, versions) is skipped.

Model outputs need more slack than a hash allows: numpy and LightGBM differ in
the last bits between CPUs, which can tip a float32 or a percentile to its
neighbour. Those tables are saved as values (``save_values``) and compared with
tolerances (``value_differences``).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import duckdb

SKIP = frozenset({"meta"})

# Model outputs agree across machines to these tolerances...
DOUBLE_TOLERANCE = 1e-6
FLOAT32_TOLERANCE = 1e-5
# ...except on a few rows, where the operating system's maths library (glibc on
# Linux, the UCRT on Windows) rounds a chase feature's log1p differently and a
# tree split goes the other way. Measured between Windows and Linux: leverage
# moved on 14 of 3,199 balls by at most 0.5%, the pressure percentile by one on
# 4, one ball's explanation split its total differently, and the top pressure
# quantiles by under 0.1%. Up to MACHINE_ROWS_SHARE of a column (at least
# MACHINE_ROWS_MIN values; MACHINE_JSON_SHARE of the numbers in a JSON column)
# may move that much; anything more is a change.
MACHINE_ROWS_SHARE = 0.01
MACHINE_JSON_SHARE = 0.05
MACHINE_ROWS_MIN = 3
MACHINE_RELATIVE = 0.02
MACHINE_ABSOLUTE = 0.002  # leverage is stored to 3 decimals
# Integers computed from model floats (a percentile, rounded quantiles).
ROUNDED_FROM_FLOATS = frozenset(
    {("wp_predictions", "pressure"), ("score_projections", "quantiles")}
)
# Shares of a total, each rounded to SHARE_STEP (a ball's explanation points).
SHARES = frozenset({("wp_predictions", "factors")})
SHARE_STEP = 0.1

TableChecksum = dict[str, object]


def table_checksums(path: Path, skip: Iterable[str] = ()) -> dict[str, TableChecksum]:
    skipped = SKIP | set(skip)
    con = duckdb.connect(str(path), read_only=True)
    try:
        con.create_function("round_json", _round_json, ["VARCHAR"], "VARCHAR")
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall() if r[0] not in skipped]
        out: dict[str, TableChecksum] = {}
        for table in sorted(tables):
            described = con.execute(f'DESCRIBE "{table}"').fetchall()
            columns = [r[0] for r in described]
            values = ", ".join(_rounded(name, kind) for name, kind, *_ in described)
            rows, digest = con.execute(
                f"""
                SELECT count(*), md5(coalesce(string_agg(line, chr(10) ORDER BY line), ''))
                FROM (SELECT CAST(row({values}) AS VARCHAR) AS line FROM "{table}" t)
                """
            ).fetchone()  # type: ignore[misc]
            out[table] = {"rows": rows, "columns": columns, "md5": digest}
        return out
    finally:
        con.close()


def _rounded(column: str, kind: str) -> str:
    quoted = f't."{column}"'
    if kind in ("DOUBLE", "FLOAT"):
        return f"round({quoted}, 9)"
    if kind in ("DOUBLE[]", "FLOAT[]"):
        return f"list_transform({quoted}, x -> round(x, 9))"
    if kind == "JSON":
        return f"round_json({quoted}::VARCHAR)"
    return quoted


def _round_json(text: str | None) -> str | None:
    return None if text is None else json.dumps(_round(json.loads(text)), sort_keys=True)


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 9) + 0.0  # -0.0 and 0.0 alike
    if isinstance(value, list):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def differences(expected: dict[str, TableChecksum], actual: dict[str, TableChecksum]) -> list[str]:
    """Human-readable differences between two checksum sets (empty if identical)."""
    out = []
    for table in sorted(set(expected) | set(actual)):
        if table not in actual:
            out.append(f"{table}: missing")
        elif table not in expected:
            out.append(f"{table}: unexpected new table")
        else:
            for key in ("columns", "rows", "md5"):
                if expected[table][key] != actual[table][key]:
                    out.append(f"{table}: {key} differs")
                    break
    return out


# ---------------------------------------------------------------- values with tolerances


def save_values(path: Path, tables: Iterable[str], out: Path) -> None:
    """Write each table's rows to ``out/<table>.json`` (sorted, full precision)."""
    out.mkdir(parents=True, exist_ok=True)
    for table in tables:
        columns, kinds, rows = _read(path, table)
        payload = {"columns": columns, "kinds": kinds, "rows": rows}
        (out / f"{table}.json").write_text(
            json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
        )


def value_differences(path: Path, tables: Iterable[str], saved: Path) -> list[str]:
    """Differences between the saved values and ``path``, beyond the tolerances."""
    out = []
    for table in tables:
        file = saved / f"{table}.json"
        if not file.exists():
            out.append(f"{table}: no saved values")
            continue
        expected = json.loads(file.read_text("utf-8"))
        columns, kinds, actual = _read(path, table)
        if columns != expected["columns"] or kinds != expected["kinds"]:
            out.append(f"{table}: columns differ")
            continue
        if len(actual) != len(expected["rows"]):
            out.append(f"{table}: rows differ ({len(expected['rows'])} -> {len(actual)})")
            continue
        out.extend(_compare_rows(table, expected["columns"], kinds, expected["rows"], actual))
    return out


def _read(path: Path, table: str) -> tuple[list[str], list[str], list[list[Any]]]:
    """Columns, their types and every row, ordered by the row's exact columns."""
    con = duckdb.connect(str(path), read_only=True)
    try:
        described = con.execute(f'DESCRIBE "{table}"').fetchall()
        columns = [str(r[0]) for r in described]
        kinds = [str(r[1]) for r in described]
        keys = [f'"{n}"' for n, k in zip(columns, kinds, strict=True) if _is_key(table, n, k)]
        order = ", ".join(keys) or "ALL"
        rows = con.execute(f'SELECT * FROM "{table}" ORDER BY {order}').fetchall()
        return columns, kinds, [[_plain(v) for v in row] for row in rows]
    finally:
        con.close()


def _is_key(table: str, column: str, kind: str) -> bool:
    """Exact columns that identify a row (everything but model numbers)."""
    numeric = kind.startswith(("DOUBLE", "FLOAT")) or kind == "JSON"
    return not numeric and (table, column) not in ROUNDED_FROM_FLOATS


def _plain(value: Any) -> Any:
    """A JSON-safe copy of a DuckDB value."""
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, float):
        # Ten significant digits: far finer than the tolerances, half the file size.
        return None if math.isnan(value) else float(f"{value:.10g}")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _compare_rows(
    table: str, columns: list[str], kinds: list[str], expected: list[Any], actual: list[Any]
) -> list[str]:
    out = []
    allowed = max(MACHINE_ROWS_MIN, math.floor(MACHINE_ROWS_SHARE * len(expected)))
    for i, (column, kind) in enumerate(zip(columns, kinds, strict=True)):
        old = [row[i] for row in expected]
        new = [row[i] for row in actual]
        if _is_key(table, column, kind):
            if old != new:
                out.append(f"{table}.{column}: rows differ")
            continue
        if kind == "JSON":
            old_numbers = _flatten([_numbers(json.loads(v)) for v in old])
            new_numbers = _flatten([_numbers(json.loads(v)) for v in new])
            shapes = [_shape(json.loads(v)) for v in old] == [_shape(json.loads(v)) for v in new]
            budget = max(MACHINE_ROWS_MIN, math.floor(MACHINE_JSON_SHARE * len(old_numbers)))
            problem = None if shapes else "structure differs"
            problem = problem or _judge(old_numbers, new_numbers, DOUBLE_TOLERANCE, budget, False)
        else:
            tight = FLOAT32_TOLERANCE if kind.startswith("FLOAT") else DOUBLE_TOLERANCE
            integers = (table, column) in ROUNDED_FROM_FLOATS
            problem = _judge(old, new, tight, allowed, integers, (table, column) in SHARES)
        if problem:
            out.append(f"{table}.{column}: {problem}")
    return out


def _judge(
    old: list[Any],
    new: list[Any],
    tight: float,
    allowed: int,
    integers: bool,
    shares: bool = False,
) -> str | None:
    """None if ``new`` matches ``old`` up to machine variation, else what is wrong.

    Every value must agree within ``tight``, except that up to ``allowed`` of them
    may move a little: integers by one, numbers by MACHINE_RELATIVE (or
    MACHINE_ABSOLUTE for small ones), and shares may be split differently as long
    as their total is unchanged.
    """
    moved = [k for k, (a, b) in enumerate(zip(old, new, strict=True)) if not _close(a, b, tight)]
    if not moved:
        return None
    gap = max(_gap(old[k], new[k]) for k in moved)
    first = moved[0]
    detail = (
        f"{len(moved)} of {len(old)} differ "
        f"(largest gap {gap:.3g}; first {old[first]} -> {new[first]})"
    )
    if len(moved) > allowed:
        return f"values differ: {detail}"
    for k in moved:
        a, b = old[k], new[k]
        if integers:
            ok = all(
                x is not None and y is not None and abs(x - y) <= 1
                for x, y in zip(_flatten([a]), _flatten([b]), strict=True)
            )
        elif shares:
            ok = (
                isinstance(a, list)
                and isinstance(b, list)
                and len(a) == len(b)
                and abs(sum(a) - sum(b)) <= SHARE_STEP / 2 * len(a) + FLOAT32_TOLERANCE
            )
        else:
            ok = _close(a, b, MACHINE_RELATIVE, MACHINE_ABSOLUTE)
        if not ok:
            return f"values differ beyond machine variation: {detail}"
    return None


def _gap(a: Any, b: Any) -> float:
    """Largest absolute difference between two numbers or lists of numbers."""
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return max((_gap(x, y) for x, y in zip(a, b, strict=True)), default=0.0)
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(a - b)
    return math.inf


def _close(a: Any, b: Any, tolerance: float, absolute: float | None = None) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            _close(x, y, tolerance, absolute) for x, y in zip(a, b, strict=True)
        )
    if isinstance(a, int | float) and isinstance(b, int | float):
        return math.isclose(
            a, b, rel_tol=tolerance, abs_tol=tolerance if absolute is None else absolute
        )
    return bool(a == b)


def _numbers(value: Any) -> list[Any]:
    """Every number in a JSON value, in document order."""
    if isinstance(value, dict):
        return _flatten([_numbers(value[k]) for k in sorted(value)])
    if isinstance(value, list):
        return _flatten([_numbers(v) for v in value])
    return [value] if isinstance(value, int | float) and not isinstance(value, bool) else []


def _shape(value: Any) -> Any:
    """A JSON value with every number replaced, to compare structure and text."""
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(v) for v in value]
    return "#" if isinstance(value, int | float) and not isinstance(value, bool) else value


def _flatten(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for v in values:
        if isinstance(v, list):
            out.extend(_flatten(v))
        else:
            out.append(v)
    return out
