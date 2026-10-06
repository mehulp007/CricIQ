"""Read-only access to the serving database.

One DuckDB connection is opened at startup; each query runs on its own cursor,
which DuckDB makes safe to use from FastAPI's worker threads.

A data sync that finishes while the API is running cannot replace the open file
on Windows, so it leaves the new database beside it as ``serving.duckdb.next``
(``criciq_core.publish``). ``refresh`` swaps that in between queries: it waits
for queries in flight, closes the connection, moves the file into place, reopens
and drops every cached object built from the old data.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
from fastapi import Request

from criciq_core.publish import pending

Row = dict[str, Any]

# How often requests look for a newly published database.
REFRESH_INTERVAL_SECONDS = 2.0


class ServingDataMissingError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Condition()
        self._readers = 0
        self._swapping = False
        self._checked = 0.0
        self._promote_pending()
        self._open()

    def _promote_pending(self) -> None:
        """Before opening: a database published while the API was down takes over."""
        waiting = pending(self.path)
        if waiting.exists():
            os.replace(waiting, self.path)

    def _open(self) -> None:
        if not self.path.exists():
            raise ServingDataMissingError(
                f"serving database not found at {self.path}; run `criciq-data run` (or `export`)"
            )
        self._con = duckdb.connect(str(self.path), read_only=True)
        meta = dict(self._con.execute("SELECT key, value FROM meta").fetchall())
        self.data_version: str = meta["data_version"]
        # The serving database holds one competition; its format (T20, ODI or Test)
        # decides the innings phases.
        found = self._con.execute(
            "SELECT format FROM competitions WHERE competition_id = ?", [meta["competition_id"]]
        ).fetchone()
        if found is None:
            competition = meta["competition_id"]
            raise ServingDataMissingError(f"no competition {competition!r} in {self.path}")
        self.match_format: str = found[0]
        self.tables: frozenset[str] = frozenset(
            name for (name,) in self._con.execute("SHOW TABLES").fetchall()
        )
        # Small derived objects built once per dataset (e.g. model terms).
        self.cache: dict[str, Any] = {}

    def has_table(self, name: str) -> bool:
        return name in self.tables

    @contextmanager
    def _reading(self) -> Iterator[duckdb.DuckDBPyConnection]:
        with self._lock:
            while self._swapping:
                self._lock.wait()
            self._readers += 1
            con = self._con
        try:
            yield con
        finally:
            with self._lock:
                self._readers -= 1
                self._lock.notify_all()

    def rows(self, sql: str, params: Sequence[Any] = ()) -> list[Row]:
        with self._reading() as con:
            cursor = con.cursor()
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

    def refresh(self, *, force: bool = False) -> bool:
        """Swap in a newly published database, if one waits; True if it did.

        Checks at most every REFRESH_INTERVAL_SECONDS unless ``force``.
        """
        now = time.monotonic()
        if not force and now - self._checked < REFRESH_INTERVAL_SECONDS:
            return False
        self._checked = now
        waiting = pending(self.path)
        if not waiting.exists():
            return False
        with self._lock:
            if self._swapping:
                return False
            self._swapping = True
            while self._readers:
                self._lock.wait()
        try:
            self._con.close()
            try:
                os.replace(waiting, self.path)
            finally:
                self._open()
        finally:
            with self._lock:
                self._swapping = False
                self._lock.notify_all()
        return True

    def close(self) -> None:
        self._con.close()


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db
