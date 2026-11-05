"""Tables added to a serving database once it is built, without rebuilding it.

``export_serving`` rebuilds a serving database from scratch, and a fresh one has no
model tables (``wp_predictions``, ``player_wpa``, ...) until ``criciq-ml score`` runs
again for every competition. Each extra here is a set of tables computed from what a
serving database already holds, so it can be added to an existing (scored) database
without either step:

- ``export_serving`` builds the extras that need no scores as its last step;
- the sync builds the ones that need scores after it scores its staging databases;
- ``criciq-data extras`` (re)builds them all in the published databases, in place.

An extra that needs scores is skipped, with a note, in a database that has none.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from criciq_core import paths
from criciq_core.publish import current, publish
from criciq_pipelines.phase_tables import PHASE_TABLES, build_phase_tables

Log = Callable[[str], None]


@dataclass(frozen=True)
class Extra:
    name: str
    # The tables it writes (each replaced if it already exists).
    tables: tuple[str, ...]
    # Writes the tables (what it returns is ignored).
    build: Callable[[duckdb.DuckDBPyConnection], object]
    # Reads the model tables `criciq-ml score` writes.
    needs_scores: bool = False


# Every extra, in build order (a later one may read an earlier one's tables).
EXTRAS: tuple[Extra, ...] = (Extra("phases", PHASE_TABLES, build_phase_tables),)


def has_scores(con: duckdb.DuckDBPyConnection) -> bool:
    """Whether the database has been scored (`criciq-ml score` writes ``wp_predictions``)."""
    found = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'wp_predictions'"
    ).fetchone()
    return bool(found and found[0])


def build_extras(
    con: duckdb.DuckDBPyConnection,
    *,
    only_scored: bool = False,
    extras: Sequence[Extra] = EXTRAS,
    log: Log = lambda _: None,
) -> dict[str, int]:
    """Build the extras in an open serving database; return their tables' row counts.

    ``only_scored`` builds just the extras that need scores (the others are already
    there, from the export).
    """
    scored = has_scores(con)
    counts: dict[str, int] = {}
    for extra in extras:
        if only_scored and not extra.needs_scores:
            continue
        if extra.needs_scores and not scored:
            log(f"  skipped {extra.name}: the database has no model scores yet")
            continue
        for table in extra.tables:
            con.execute(f"DROP TABLE IF EXISTS {table}")
        extra.build(con)
        for table in extra.tables:
            counts[table] = int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # type: ignore[index]
    return counts


def extend_database(
    path: Path,
    *,
    only_scored: bool = False,
    extras: Sequence[Extra] = EXTRAS,
    log: Log = lambda _: None,
) -> dict[str, int]:
    """Build the extras in the database at ``path`` itself (a staging file nobody reads)."""
    con = duckdb.connect(str(path))
    try:
        counts = build_extras(con, only_scored=only_scored, extras=extras, log=log)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return counts


def add_extras(
    target: Path, *, extras: Sequence[Extra] = EXTRAS, log: Log = lambda _: None
) -> dict[str, int]:
    """Rebuild every extra in a published serving database and publish the result.

    Works on a copy of its newest version, so the running API keeps reading the old
    one until it swaps the new one in (``criciq_core.publish``).
    """
    if not extras:
        return {}  # nothing to add: leave the database alone
    staging = target.with_name(target.name + ".extras")
    shutil.copyfile(current(target), staging)
    try:
        counts = extend_database(staging, extras=extras, log=log)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    publish(staging, target)
    return counts


def add_extras_everywhere(
    competitions: Sequence[str],
    *,
    extras: Sequence[Extra] = EXTRAS,
    log: Log = lambda _: None,
) -> dict[str, dict[str, int]]:
    """``add_extras`` for the published serving database of each competition that has one."""
    found: dict[str, dict[str, int]] = {}
    for competition in competitions:
        target = paths.serving_path(competition)
        if not current(target).exists():
            log(f"  {competition}: no serving database yet")
            continue
        found[competition] = add_extras(target, extras=extras, log=log)
    return found
