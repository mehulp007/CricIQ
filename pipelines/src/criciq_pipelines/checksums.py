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

# Integers computed from model floats (a percentile, rounded quantiles) may move
# by one on a few rows between machines.
ROUNDED_FROM_FLOATS = frozenset(
    {("wp_predictions", "pressure"), ("score_projections", "quantiles")}
)
DOUBLE_TOLERANCE = 1e-6
FLOAT32_TOLERANCE = 1e-5
MAX_ROUNDING_FLIPS = 0.002  # share of values

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
    for i, (column, kind) in enumerate(zip(columns, kinds, strict=True)):
        old = [row[i] for row in expected]
        new = [row[i] for row in actual]
        if (table, column) in ROUNDED_FROM_FLOATS:
            flips, total = _count_flips(old, new)
            if flips is None or flips > max(2, MAX_ROUNDING_FLIPS * total):
                out.append(f"{table}.{column}: integers differ beyond rounding")
        elif kind == "JSON":
            if not all(
                _close(json.loads(a), json.loads(b), DOUBLE_TOLERANCE)
                for a, b in zip(old, new, strict=True)
            ):
                out.append(f"{table}.{column}: values differ")
        elif kind.startswith(("DOUBLE", "FLOAT")):
            tolerance = FLOAT32_TOLERANCE if kind.startswith("FLOAT") else DOUBLE_TOLERANCE
            bad = [
                k
                for k, (a, b) in enumerate(zip(old, new, strict=True))
                if not _close(a, b, tolerance)
            ]
            if bad:
                gap = max(_gap(old[k], new[k]) for k in bad)
                out.append(
                    f"{table}.{column}: values differ in {len(bad)} of {len(old)} rows "
                    f"(largest gap {gap:.3g}; first: row {expected[bad[0]][:3]} "
                    f"{old[bad[0]]} -> {new[bad[0]]})"
                )
        elif old != new:
            out.append(f"{table}.{column}: rows differ")
    return out


def _gap(a: Any, b: Any) -> float:
    """Largest absolute difference between two numbers or lists of numbers."""
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return max((_gap(x, y) for x, y in zip(a, b, strict=True)), default=0.0)
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(a - b)
    return math.inf


def _close(a: Any, b: Any, tolerance: float) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return a is b
        return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y, tolerance) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tolerance) for k in a)
    return bool(a == b)


def _count_flips(old: list[Any], new: list[Any]) -> tuple[int | None, int]:
    """How many integers moved by exactly one (None if any moved further)."""
    flat_old, flat_new = _flatten(old), _flatten(new)
    if len(flat_old) != len(flat_new):
        return None, len(flat_old)
    flips = 0
    for a, b in zip(flat_old, flat_new, strict=True):
        if a == b:
            continue
        if a is None or b is None or abs(a - b) > 1:
            return None, len(flat_old)
        flips += 1
    return flips, len(flat_old)


def _flatten(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for v in values:
        if isinstance(v, list):
            out.extend(_flatten(v))
        else:
            out.append(v)
    return out
