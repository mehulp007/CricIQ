"""Read-only access to the serving databases and the players database.

Each competition the site serves has its own serving database (the IPL's is
``serving.duckdb``, the others ``serving-<competition>.duckdb`` beside it), all
with the same tables; ``get_db`` picks the one a request's ``{competition}``
names. One DuckDB connection is opened per database at startup; each query runs
on its own cursor, which DuckDB makes safe to use from FastAPI's worker threads.

The players database (``criciq_pipelines.player_db``) holds several competitions,
each a schema of views named like the serving database's tables. A
``ScopedDatabase`` runs queries with ``search_path`` set to one of them, so the
Player Lab code serves any competition unchanged.

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
from collections import OrderedDict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
from fastapi import HTTPException, Request

from criciq_core.publish import pending

Row = dict[str, Any]

# How often requests look for a newly published database.
REFRESH_INTERVAL_SECONDS = 2.0
# Derived objects kept per database (model terms, simulator engines for points in
# history, ...): the least recently used go first.
CACHE_SIZE = 256


class BoundedCache(OrderedDict[str, Any]):
    """A dict that forgets its least recently used entries beyond ``maxsize``.

    Everything cached is rebuilt on demand, so an evicted entry costs only time.
    """

    def __init__(self, maxsize: int = CACHE_SIZE) -> None:
        super().__init__()
        self.maxsize = maxsize
        self._guard = threading.Lock()

    def __getitem__(self, key: str) -> Any:
        with self._guard:
            value = super().__getitem__(key)
            self.move_to_end(key)
            return value

    def __setitem__(self, key: str, value: Any) -> None:
        with self._guard:
            super().__setitem__(key, value)
            self.move_to_end(key)
            while len(self) > self.maxsize:
                self.popitem(last=False)

    def setdefault(self, key: str, default: Any = None) -> Any:
        # OrderedDict's own setdefault would skip the bound and the recency update.
        if key in self:
            return self[key]
        self[key] = default
        return default


class ServingDataMissingError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path, memory_limit: str | None = None) -> None:
        self.path = path
        # Bounds DuckDB's buffer pool for this database ("384MB"); None keeps DuckDB's default.
        self.memory_limit = memory_limit
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
        if self.memory_limit:
            # Set on the connection, not in its config: other readers of the same file (the
            # tests, the featured export) open it with DuckDB's default config.
            self._con.execute(f"SET memory_limit = '{self.memory_limit}'")
        meta = dict(self._con.execute("SELECT key, value FROM meta").fetchall())
        self.data_version: str = meta["data_version"]
        # The serving database holds one competition; its format (T20, ODI or Test)
        # decides the innings phases. The players database holds several.
        self._format: str | None = None
        self._competition: str | None = meta.get("competition_id")
        # Seasons spanning the new year are named "2023/24", the others by their year.
        self.season_spans_new_year = meta.get("season_spans_new_year") == "true"
        competition = self._competition
        if competition is not None:
            found = self._con.execute(
                "SELECT format FROM competitions WHERE competition_id = ?", [competition]
            ).fetchone()
            if found is None:
                raise ServingDataMissingError(f"no competition {competition!r} in {self.path}")
            self._format = found[0]
        self.tables: frozenset[str] = frozenset(
            name for (name,) in self._con.execute("SHOW TABLES").fetchall()
        )
        # Tables and views of every schema (the players database's scopes).
        schemas: dict[str, set[str]] = {}
        for schema, name in self._con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables"
        ).fetchall():
            schemas.setdefault(schema, set()).add(name)
        self.schemas: dict[str, frozenset[str]] = {k: frozenset(v) for k, v in schemas.items()}
        # Small derived objects built once per dataset (e.g. model terms).
        self.cache: BoundedCache = BoundedCache()

    @property
    def competition_id(self) -> str | None:
        """The competition a serving database holds (None for the players database)."""
        return self._competition

    @property
    def match_format(self) -> str:
        if self._format is None:
            raise ServingDataMissingError(f"{self.path} holds several competitions")
        return self._format

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

    def rows(self, sql: str, params: Sequence[Any] = (), *, schema: str | None = None) -> list[Row]:
        """Rows of ``sql``; unqualified names resolve in ``schema`` first when given."""
        with self._reading() as con:
            cursor = con.cursor()
            try:
                if schema is not None:
                    cursor.execute(f"SET search_path = '{schema},main'")
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


class ScopedDatabase(Database):
    """One scope (schema) of the players database, read like a serving database."""

    def __init__(self, base: Database, schema: str, match_format: str) -> None:
        # Shares the base connection: nothing of Database.__init__ runs here.
        self.base = base
        self.schema = schema
        self.path = base.path
        self.data_version = base.data_version
        self._format = match_format
        self.tables = base.schemas.get(schema, frozenset()) | base.tables

    @property
    def cache(self) -> BoundedCache:  # type: ignore[override]
        # Kept on the base so a swapped-in database starts with empty caches.
        key = f"scope:{self.schema}"
        if key not in self.base.cache:
            self.base.cache[key] = BoundedCache()
        found: BoundedCache = self.base.cache[key]
        return found

    def rows(self, sql: str, params: Sequence[Any] = (), *, schema: str | None = None) -> list[Row]:
        return self.base.rows(sql, params, schema=schema or self.schema)

    def refresh(self, *, force: bool = False) -> bool:
        return self.base.refresh(force=force)

    def close(self) -> None:
        pass


def serving_paths(ipl: Path) -> list[Path]:
    """The IPL's serving database and every other competition's beside it."""
    others = {p.name.split(".duckdb")[0] for p in ipl.parent.glob("serving-*.duckdb*")}
    return [ipl, *(ipl.with_name(f"{name}.duckdb") for name in sorted(others))]


def get_db(request: Request) -> Database:
    """The serving database of the request's ``{competition}`` (404 if none)."""
    competition = str(request.path_params.get("competition", "ipl")).lower()
    found: Database | None = request.app.state.serving.get(competition)
    if found is None:
        raise HTTPException(status_code=404, detail=f"competition {competition} not found")
    return found
