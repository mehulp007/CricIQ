"""Content checksums of every table in a DuckDB file, for regression gates.

Each table's rows are rendered as text, sorted and hashed, so a checksum
depends only on content: not on row order, file layout or build time. Doubles
are rounded to 9 decimals first: DuckDB sums them in parallel, in an order that
can change the last bits from run to run, and numpy's results differ in the
last bits between platforms. Numbers inside JSON columns (fitted constants in
the ``models`` registry) are rounded the same way. The ``meta`` table (build
timestamps, versions) is skipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

SKIP = frozenset({"meta"})

TableChecksum = dict[str, object]


def table_checksums(path: Path) -> dict[str, TableChecksum]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        con.create_function("round_json", _round_json, ["VARCHAR"], "VARCHAR")
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall() if r[0] not in SKIP]
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
