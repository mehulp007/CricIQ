"""Read-only access to the serving database.

One DuckDB connection is opened at startup; each query runs on its own cursor,
which DuckDB makes safe to use from FastAPI's worker threads.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb
from fastapi import Request

Row = dict[str, Any]


class ServingDataMissingError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise ServingDataMissingError(
                f"serving database not found at {path}; run `criciq-data run` (or `export`)"
            )
        self._con = duckdb.connect(str(path), read_only=True)
        meta = dict(self._con.execute("SELECT key, value FROM meta").fetchall())
        self.data_version: str = meta["data_version"]
        self.tables: frozenset[str] = frozenset(
            name for (name,) in self._con.execute("SHOW TABLES").fetchall()
        )

    def has_table(self, name: str) -> bool:
        return name in self.tables

    def rows(self, sql: str, params: Sequence[Any] = ()) -> list[Row]:
        cursor = self._con.cursor()
        try:
            cursor.execute(sql, list(params))
            columns = [d[0] for d in cursor.description or []]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def row(self, sql: str, params: Sequence[Any] = ()) -> Row | None:
        found = self.rows(sql, params)
        return found[0] if found else None

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        found = self.row(sql, params)
        return None if found is None else next(iter(found.values()))

    def close(self) -> None:
        self._con.close()


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db
