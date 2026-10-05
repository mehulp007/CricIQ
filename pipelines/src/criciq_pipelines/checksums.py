"""Content checksums of every table in a DuckDB file, for regression gates.

Each table's rows are rendered as text, sorted and hashed, so a checksum
depends only on content: not on row order, file layout or build time. The
``meta`` table (build timestamps, versions) is skipped.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

SKIP = frozenset({"meta"})

TableChecksum = dict[str, object]


def table_checksums(path: Path) -> dict[str, TableChecksum]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall() if r[0] not in SKIP]
        out: dict[str, TableChecksum] = {}
        for table in sorted(tables):
            columns = [r[0] for r in con.execute(f'DESCRIBE "{table}"').fetchall()]
            rows, digest = con.execute(
                f"""
                SELECT count(*), md5(coalesce(string_agg(line, chr(10) ORDER BY line), ''))
                FROM (SELECT CAST(t AS VARCHAR) AS line FROM "{table}" t)
                """
            ).fetchone()  # type: ignore[misc]
            out[table] = {"rows": rows, "columns": columns, "md5": digest}
        return out
    finally:
        con.close()


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
