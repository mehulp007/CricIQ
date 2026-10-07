"""Incremental data sync: bring every competition up to date from Cricsheet.

Cricsheet publishes new and corrected matches one to three days after they are
played, in small "recently added" feeds as well as in the full archives. A sync:

1. picks a feed by the time since the last successful sync: the last 7 days'
   additions, else the last 30 days', else the full archives (which also reveal
   matches Cricsheet has withdrawn);
2. keeps the matches of the selected competitions and compares each file's
   SHA-256 with the **ingest log**: new, corrected (a different file for a known
   match), unchanged, or withdrawn;
3. applies only those changes to the interim tables, then rebuilds the
   warehouse, validates it, exports and scores the serving database and exports
   the players database, all into staging files, so nothing current changes until
   everything has worked;
4. sets aside (**quarantines**) a match that cannot be built or fails
   validation, keeping the previous version of a corrected one, and goes on with
   the rest; a failure that no incoming match explains stops the sync instead;
5. records what changed (``sync_runs``, ``data_updates``), which the API and the
   site's freshness badge report.

The ingest log, run history and update record live in ``data/sync/ingest.duckdb``;
the files a sync took in are kept under ``data/raw/feeds/`` (only the matches it
used), so any version of the data can be traced to its sources.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from criciq_core import paths
from criciq_core.publish import publish
from criciq_pipelines import pipeline, raw
from criciq_pipelines.export import export_serving
from criciq_pipelines.extract import SCHEMAS, ExtractError, parse_match
from criciq_pipelines.player_db import export_players
from criciq_pipelines.reference import CompetitionsConfig, load_competitions
from criciq_pipelines.scope import build_scope
from criciq_pipelines.validation import ValidationReport, validate
from criciq_pipelines.warehouse import BuildInputs, WarehouseBuildError, build_warehouse

WEEK_FEED = "recently_added_7_json.zip"
MONTH_FEED = "recently_added_30_json.zip"
FULL = "full"
# A feed covers the days before Cricsheet last updated it, so a sync uses the
# shortest one that safely reaches back to the previous sync.
WEEK_FEED_REACH = dt.timedelta(days=6)
MONTH_FEED_REACH = dt.timedelta(days=28)
MAX_ATTEMPTS = 4

INGEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_log (
    match_id       BIGINT PRIMARY KEY,
    competition_id VARCHAR NOT NULL,
    match_date     DATE NOT NULL,
    sha256         VARCHAR NOT NULL,
    status         VARCHAR NOT NULL CHECK (status IN ('active', 'quarantined', 'withdrawn')),
    source         VARCHAR NOT NULL,  -- archive holding this version, relative to data/raw
    detail         VARCHAR,           -- why a match (or its latest correction) is quarantined
    first_seen     TIMESTAMP NOT NULL,
    updated_at     TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_runs (
    run_id       INTEGER PRIMARY KEY,
    started_at   TIMESTAMP NOT NULL,
    finished_at  TIMESTAMP NOT NULL,
    kind         VARCHAR NOT NULL,    -- initial | sync | full | rebuild
    feed         VARCHAR NOT NULL,
    status       VARCHAR NOT NULL,    -- updated | up_to_date | failed
    data_version VARCHAR,
    checked      INTEGER NOT NULL,
    new          INTEGER NOT NULL,
    corrected    INTEGER NOT NULL,
    withdrawn    INTEGER NOT NULL,
    quarantined  INTEGER NOT NULL,
    seconds      DOUBLE NOT NULL,
    detail       VARCHAR
);
CREATE TABLE IF NOT EXISTS data_updates (
    run_id              INTEGER NOT NULL,
    updated_at          TIMESTAMP NOT NULL,
    kind                VARCHAR NOT NULL,
    competition_id      VARCHAR NOT NULL,
    new_matches         INTEGER NOT NULL,
    corrected_matches   INTEGER NOT NULL,
    withdrawn_matches   INTEGER NOT NULL,
    quarantined_matches INTEGER NOT NULL,
    PRIMARY KEY (run_id, competition_id)
);
"""

Fetch = Callable[[str, Path], Path]
"""Downloads one Cricsheet file (by name) into a directory and returns its path."""

Log = Callable[[str], None]


class SyncError(RuntimeError):
    """A sync that cannot finish; the current data is left as it was."""


@dataclass(frozen=True)
class Incoming:
    """One match file from a feed or an archive."""

    match_id: int
    competition_id: str
    match_date: dt.date
    sha256: str
    content: bytes
    archive: str  # name of the zip it was read from

    def document(self) -> dict[str, Any]:
        doc: dict[str, Any] = json.loads(self.content)
        return doc


@dataclass(frozen=True)
class Quarantined:
    match_id: int
    competition_id: str
    reason: str
    # A failed correction of a match in use: its previous version stays.
    kept_previous: bool = False


@dataclass
class Plan:
    new: list[Incoming] = field(default_factory=list)
    corrected: list[Incoming] = field(default_factory=list)
    withdrawn: list[int] = field(default_factory=list)
    unchanged: int = 0
    still_quarantined: int = 0

    @property
    def incoming(self) -> list[Incoming]:
        return [*self.new, *self.corrected]

    @property
    def empty(self) -> bool:
        return not (self.new or self.corrected or self.withdrawn)


@dataclass
class SyncResult:
    kind: str
    feed: str
    status: str
    checked: int
    new: int = 0
    corrected: int = 0
    withdrawn: int = 0
    unchanged: int = 0
    quarantined: list[Quarantined] = field(default_factory=list)
    data_version: str | None = None
    seconds: float = 0.0
    serving: Path | None = None
    by_competition: dict[str, dict[str, int]] = field(default_factory=dict)


LogEntries = dict[int, tuple[str, str, str, dt.date]]
"""match_id -> (sha256, status, competition_id, match_date)."""


# --------------------------------------------------------------------------- ingest database


def ingest_path() -> Path:
    return paths.sync_dir() / "ingest.duckdb"


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """The ingest database (created on first use unless read-only)."""
    target = ingest_path()
    if read_only:
        if not target.exists():
            raise FileNotFoundError(f"no ingest log at {target}; run `criciq-data run` first")
        return duckdb.connect(str(target), read_only=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(target))
    con.execute(INGEST_SCHEMA)
    return con


def _entries(con: duckdb.DuckDBPyConnection) -> LogEntries:
    return {
        int(m): (str(sha), str(status), str(comp), date)
        for m, sha, status, comp, date in con.execute(
            "SELECT match_id, sha256, status, competition_id, match_date FROM ingest_log"
        ).fetchall()
    }


def last_success(con: duckdb.DuckDBPyConnection) -> dt.datetime | None:
    row = con.execute(
        "SELECT max(started_at) FROM sync_runs WHERE status IN ('updated', 'up_to_date')"
    ).fetchone()
    return row[0] if row else None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)


# --------------------------------------------------------------------------- reading files


def read_archive(
    archive: Path, config: CompetitionsConfig, selected: set[str]
) -> Iterator[Incoming]:
    """The matches of the selected competitions in a Cricsheet zip, in id order."""
    with zipfile.ZipFile(archive) as zf:
        names = sorted(
            (n for n in zf.namelist() if n.endswith(".json") and Path(n).stem.isdigit()),
            key=lambda n: int(Path(n).stem),
        )
        for name in names:
            content = zf.read(name)
            info = json.loads(content)["info"]
            competition = config.classify(
                {
                    "event_name": info.get("event", {}).get("name"),
                    "gender": info.get("gender"),
                    "match_type": info.get("match_type"),
                    "team_type": info.get("team_type"),
                }
            )
            if competition is None or competition.id not in selected:
                continue
            yield Incoming(
                match_id=int(Path(name).stem),
                competition_id=competition.id,
                match_date=dt.date.fromisoformat(info["dates"][0]),
                sha256=hashlib.sha256(content).hexdigest(),
                content=content,
                archive=archive.name,
            )


def choose_feed(last: dt.datetime | None, now: dt.datetime) -> str:
    """The shortest feed that reaches back to the last successful sync."""
    if last is None:
        return FULL
    gap = now - last
    if gap <= WEEK_FEED_REACH:
        return WEEK_FEED
    if gap <= MONTH_FEED_REACH:
        return MONTH_FEED
    return FULL


RETRY_DELAYS_SECONDS = (5.0, 20.0, 60.0)


def download(
    name: str,
    directory: Path,
    timeout: float = 120.0,
    delays: tuple[float, ...] = RETRY_DELAYS_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Fetch one Cricsheet file (a feed, an archive or the register).

    A dropped connection or a server error is retried after each of ``delays``
    (a scheduled sync runs unattended); the file only appears once complete.
    """
    url = raw.PEOPLE_URL if name == raw.PEOPLE else raw.DOWNLOADS + name
    target = directory / name
    partial = directory / f"{name}.part"
    request = urllib.request.Request(url, headers={"User-Agent": raw.USER_AGENT})
    for attempt in range(len(delays) + 1):
        try:
            with (
                urllib.request.urlopen(request, timeout=timeout) as response,
                partial.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
            os.replace(partial, target)
            return target
        except (urllib.error.URLError, OSError) as exc:
            partial.unlink(missing_ok=True)
            client_error = isinstance(exc, urllib.error.HTTPError) and exc.code < 500
            if client_error or attempt == len(delays):
                raise SyncError(f"could not download {url}: {exc}") from exc
            sleep(delays[attempt])
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- planning


def plan_changes(
    entries: LogEntries, incoming: Iterable[Incoming], *, complete_for: set[str] | None = None
) -> Plan:
    """Compare files with the ingest log.

    ``complete_for`` names the competitions whose every match is in ``incoming``
    (a full download): their logged matches missing from it were withdrawn.
    """
    plan = Plan()
    seen: set[int] = set()
    for item in incoming:
        seen.add(item.match_id)
        known = entries.get(item.match_id)
        if known is None or known[1] == "withdrawn":
            plan.new.append(item)
        elif known[0] != item.sha256:
            plan.corrected.append(item)
        elif known[1] == "quarantined":
            plan.still_quarantined += 1
        else:
            plan.unchanged += 1
    if complete_for:
        plan.withdrawn = sorted(
            m
            for m, (_, status, competition, _) in entries.items()
            if status != "withdrawn" and competition in complete_for and m not in seen
        )
    return plan


def content_version(files: dict[int, tuple[str, dt.date]], people: Path) -> str:
    """Latest match date + a hash of every match file in use and the register."""
    digest = hashlib.sha256()
    for match_id in sorted(files):
        digest.update(f"{match_id}:{files[match_id][0]}\n".encode())
    digest.update(raw.file_sha256(people).encode())
    latest = max(date for _, date in files.values())
    return f"{latest.isoformat()}.{digest.hexdigest()[:8]}"


# --------------------------------------------------------------------------- interim


def apply_to_interim(
    base: Path, out: Path, remove: set[int], add: dict[int, dict[str, Any]]
) -> dict[str, int]:
    """Write ``base``'s interim tables to ``out`` without ``remove`` and with ``add``.

    Rows stay in match order (a stable sort), so the result holds the same rows
    as a full extract of the same files.
    """
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in SCHEMAS}
    for match_id in sorted(add):
        for name, table_rows in parse_match(match_id, add[match_id]).items():
            rows[name].extend(table_rows)
    dropped = pa.array(sorted(remove | set(add)), pa.int64())
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, schema in SCHEMAS.items():
        old = pq.read_table(base / f"{name}.parquet", schema=schema)
        kept = old.filter(pc.invert(pc.is_in(old["match_id"], value_set=dropped)))
        table = pa.concat_tables([kept, pa.Table.from_pylist(rows[name], schema=schema)])
        table = table.take(pc.sort_indices(table, sort_keys=[("match_id", "ascending")]))
        pq.write_table(table, out / f"{name}.parquet", compression="zstd")
        counts[name] = table.num_rows
    return counts


# --------------------------------------------------------------------------- the sync


@dataclass
class _Workspace:
    """Staging files beside the current ones; nothing current changes until commit."""

    stamp: str
    interim: Path
    warehouse: Path
    scopes: dict[str, Path]
    serving: Path
    players: Path
    # Serving databases of the other served competitions (pipeline.exported_competitions).
    servings: dict[str, Path]
    report: ValidationReport | None = None

    @classmethod
    def create(cls, stamp: str) -> _Workspace:
        return cls(
            stamp=stamp,
            interim=paths.interim_dir() / f".sync-{stamp}",
            warehouse=_beside(paths.cricket_warehouse_path(), ".sync"),
            scopes={
                c: _beside(paths.warehouse_path(c), ".sync")
                for c in (*pipeline.SCOPED, pipeline.POOLED)
            },
            serving=_beside(paths.serving_path(), ".sync"),
            players=_beside(paths.players_path(), ".sync"),
            servings={
                c: _beside(paths.serving_path(c), ".sync") for c in pipeline.exported_competitions()
            },
        )

    def clean(self) -> None:
        shutil.rmtree(self.interim, ignore_errors=True)
        for path in (
            self.warehouse,
            *self.scopes.values(),
            self.serving,
            self.players,
            *self.servings.values(),
        ):
            path.unlink(missing_ok=True)


def _beside(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def sync(
    *,
    feed: str | None = None,
    fetch: Fetch = download,
    score: bool = True,
    retry_quarantined: bool = False,
    require_all_golden: bool = True,
    now: dt.datetime | None = None,
    log: Log = lambda _: None,
) -> SyncResult:
    """Bring the data up to date; see the module docstring."""
    started = now or _now()
    clock = dt.datetime.now()
    config = load_competitions()
    selected = {c.id for c in pipeline.selected_competitions()}
    con = connect()
    try:
        if con.execute("SELECT count(*) FROM ingest_log").fetchone() == (0,):
            log("  no ingest log yet: recording the current snapshot first")
            record_snapshot(
                raw.latest_snapshot(),
                warehouse=paths.cricket_warehouse_path(),
                con=con,
                now=started,
            )
        state = pipeline.current_state()
        chosen = feed or choose_feed(last_success(con), started)
        kind = "full" if chosen == FULL else "sync"
        with tempfile.TemporaryDirectory(prefix=".sync-", dir=_ensure(paths.raw_dir())) as tmp:
            downloads = Path(tmp)
            log(f"> checking {'the full archives' if chosen == FULL else chosen} ...")
            if chosen == FULL:
                archives = [fetch(a, downloads) for a in pipeline.archives_to_download()]
            else:
                archives = [fetch(chosen, downloads)]
            incoming = {i.match_id: i for a in archives for i in read_archive(a, config, selected)}
            entries = _entries(con)
            plan = plan_changes(
                entries, incoming.values(), complete_for=selected if chosen == FULL else None
            )
            if retry_quarantined:
                plan.corrected.extend(_quarantined_files(con, config, selected, set(incoming)))
            log(
                f"  {len(incoming)} matches checked: {len(plan.new)} new, "
                f"{len(plan.corrected)} corrected, {len(plan.withdrawn)} withdrawn, "
                f"{plan.unchanged} unchanged"
            )
            result = SyncResult(
                kind=kind,
                feed=chosen,
                status="up_to_date",
                checked=len(incoming),
                unchanged=plan.unchanged,
                data_version=state.version,
            )
            if not plan.empty:
                people = fetch(raw.PEOPLE, downloads)
                workspace = _Workspace.create(started.strftime("%Y%m%dT%H%M%S"))
                try:
                    _apply(
                        con,
                        state,
                        plan,
                        entries,
                        people,
                        workspace,
                        result,
                        started,
                        score=score,
                        require_all_golden=require_all_golden,
                        log=log,
                    )
                    _commit(con, plan, result, workspace, people, started, chosen)
                except BaseException as exc:
                    workspace.clean()
                    failed = SyncResult(
                        kind=kind, feed=chosen, status="failed", checked=len(incoming)
                    )
                    failed.seconds = (dt.datetime.now() - clock).total_seconds()
                    _record_run(con, failed, started, detail=str(exc)[:500])
                    raise
        result.seconds = (dt.datetime.now() - clock).total_seconds()
        _record_run(con, result, started)
        _record_updates(con, result, started)
        return result
    finally:
        con.close()


def _quarantined_files(
    con: duckdb.DuckDBPyConnection, config: CompetitionsConfig, selected: set[str], skip: set[int]
) -> list[Incoming]:
    """Quarantined matches, read again from the files they came in (to retry them)."""
    out: list[Incoming] = []
    rows = con.execute(
        "SELECT match_id, source FROM ingest_log WHERE status = 'quarantined' ORDER BY match_id"
    ).fetchall()
    for match_id, source in rows:
        if match_id not in skip:
            archive = paths.raw_dir() / source
            out.extend(i for i in read_archive(archive, config, selected) if i.match_id == match_id)
    return out


def _apply(
    con: duckdb.DuckDBPyConnection,
    state: pipeline.DataState,
    plan: Plan,
    entries: LogEntries,
    people: Path,
    workspace: _Workspace,
    result: SyncResult,
    started: dt.datetime,
    *,
    score: bool,
    require_all_golden: bool,
    log: Log,
) -> None:
    """Build everything in staging, quarantining the incoming matches that fail."""
    attempt = {i.match_id: i for i in plan.incoming}
    quarantined: dict[int, Quarantined] = {}

    def set_aside(match_id: int, reason: str) -> None:
        item = attempt.pop(match_id)
        in_use = entries.get(match_id, ("", ""))[1] == "active"
        quarantined[match_id] = Quarantined(match_id, item.competition_id, reason, in_use)
        log(f"  quarantined {match_id} ({item.competition_id}): {reason}")

    for _ in range(MAX_ATTEMPTS):
        documents: dict[int, dict[str, Any]] = {}
        for match_id, item in list(attempt.items()):
            try:
                documents[match_id] = item.document()
                parse_match(match_id, documents[match_id])
            except (ExtractError, KeyError, ValueError) as exc:
                documents.pop(match_id, None)
                set_aside(match_id, f"unreadable: {exc}")
        version = content_version(_files_in_use(entries, plan, attempt), people)
        shutil.rmtree(workspace.interim, ignore_errors=True)
        log("> applying the changes to the interim tables ...")
        apply_to_interim(state.interim, workspace.interim, set(plan.withdrawn), documents)
        culprits = _build_and_validate(
            workspace, people, version, set(attempt), require_all_golden, log
        )
        if not culprits:
            break
        for match_id, reason in culprits.items():
            set_aside(match_id, reason)
    else:
        raise SyncError(f"the data still fails after {MAX_ATTEMPTS} attempts")

    # Source errors outside curated competitions: the build set these aside itself.
    for match_id, competition_id, reason in _built_quarantine(workspace.warehouse, set(attempt)):
        quarantined[match_id] = Quarantined(match_id, competition_id, reason)
    taken = set(attempt) - set(quarantined)

    result.new = sum(1 for i in plan.new if i.match_id in taken)
    result.corrected = sum(1 for i in plan.corrected if i.match_id in taken)
    result.withdrawn = len(plan.withdrawn)
    result.quarantined = sorted(quarantined.values(), key=lambda q: q.match_id)
    result.data_version = version
    result.status = "updated"
    result.by_competition = _by_competition(plan, taken, result.quarantined, entries)

    scoped = pipeline.scoped_competitions()
    for competition in scoped:
        build_scope(workspace.warehouse, competition, workspace.scopes[competition])
    if pooled := pipeline.pooled_competitions():
        build_scope(workspace.warehouse, pooled, workspace.scopes[pipeline.POOLED])
    if scoped:
        log("> exporting the serving databases ...")
        updates = _updates_with(con, result, started)
        try:
            export_serving(workspace.scopes[scoped[0]], workspace.serving, updates=updates)
            for competition, target in workspace.servings.items():
                pipeline.run_export_competition(
                    competition, target, warehouse=workspace.warehouse, updates=updates
                )
        finally:
            updates.unlink(missing_ok=True)
    players = pipeline.player_competitions()
    if players:
        log("> exporting the players database ...")
        export_players(workspace.warehouse, workspace.players, players)
    if scoped and score:
        log("> scoring every ball with the committed models ...")
        _score(workspace, scoped[0])


def _files_in_use(
    entries: LogEntries, plan: Plan, attempt: dict[int, Incoming]
) -> dict[int, tuple[str, dt.date]]:
    files = {m: (sha, date) for m, (sha, status, _, date) in entries.items() if status == "active"}
    for match_id in plan.withdrawn:
        files.pop(match_id, None)
    for item in attempt.values():
        files[item.match_id] = (item.sha256, item.match_date)
    return files


def _build_and_validate(
    workspace: _Workspace,
    people: Path,
    version: str,
    incoming: set[int],
    require_all_golden: bool,
    log: Log,
) -> dict[int, str]:
    """Build and validate the staging warehouse; the incoming matches at fault, if any."""
    log("> building the warehouse ...")
    try:
        build_warehouse(
            BuildInputs(
                interim_dir=workspace.interim,
                people_csv=people,
                data_version=version,
                attributes_csv=paths.reference_dir() / pipeline.ATTRIBUTES_FILE,
                competitions=tuple(c.id for c in pipeline.selected_competitions()),
            ),
            workspace.warehouse,
        )
    except WarehouseBuildError as exc:
        culprits = exc.match_ids & incoming
        if not culprits:
            raise SyncError(f"the warehouse cannot be built: {exc}") from exc
        return dict.fromkeys(sorted(culprits), f"cannot be built: {str(exc)[:300]}")
    log("> validating ...")
    report = validate(workspace.warehouse, require_all_golden=require_all_golden)
    workspace.report = report
    failing = report.failing_match_ids()
    if not failing:
        return {}
    if failing - incoming:
        raise SyncError(
            "validation fails for data this sync did not bring: "
            + ", ".join(str(m) for m in sorted(failing - incoming)[:5])
        )
    return {m: _reasons(report, m) for m in sorted(failing)}


def _reasons(report: ValidationReport, match_id: int) -> str:
    reasons = [c.id for c in report.checks if match_id in c.match_ids]
    reasons += [
        f"golden scorecard ({'; '.join(g.mismatches)})"
        for g in report.golden
        if g.match_id == match_id and not g.passed
    ]
    return "failed validation: " + ", ".join(reasons)


def _built_quarantine(warehouse: Path, incoming: set[int]) -> list[tuple[int, str, str]]:
    """Incoming matches the build itself set aside (source errors outside curated data)."""
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(
            "SELECT match_id, competition_id, rule || ': ' || detail FROM quarantine"
        ).fetchall()
    finally:
        con.close()
    return [(int(m), str(c), str(r)) for m, c, r in rows if m in incoming]


def _by_competition(
    plan: Plan, taken: set[int], quarantined: list[Quarantined], entries: LogEntries
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}

    def bump(competition: str, key: str) -> None:
        row = counts.setdefault(
            competition, {"new": 0, "corrected": 0, "withdrawn": 0, "quarantined": 0}
        )
        row[key] += 1

    for item in plan.new:
        if item.match_id in taken:
            bump(item.competition_id, "new")
    for item in plan.corrected:
        if item.match_id in taken:
            bump(item.competition_id, "corrected")
    for match_id in plan.withdrawn:
        bump(entries[match_id][2], "withdrawn")
    for q in quarantined:
        bump(q.competition_id, "quarantined")
    return counts


def _updates_with(con: duckdb.DuckDBPyConnection, result: SyncResult, started: dt.datetime) -> Path:
    """A copy of the update record including this sync, for the export to read."""
    copy = paths.sync_dir() / ".updates-export.duckdb"
    copy.unlink(missing_ok=True)
    rows = [list(r) for r in con.execute("SELECT * FROM data_updates").fetchall()]
    rows += _update_rows(_next_run_id(con), result, started)
    out = duckdb.connect(str(copy))
    try:
        out.execute(INGEST_SCHEMA)
        if rows:
            out.executemany("INSERT INTO data_updates VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    finally:
        out.close()
    return copy


def _score(workspace: _Workspace, competition: str) -> None:
    """Score the staging serving and players databases (criciq-ml runs in its own process)."""
    command = shutil.which("criciq-ml")
    if command is None:
        raise SyncError("criciq-ml is not installed; run `uv sync --all-packages`")
    arguments = [
        command,
        "score",
        "--serving",
        str(workspace.serving),
        "--warehouse",
        str(workspace.scopes[competition]),
        "--pooled",
        str(workspace.scopes[pipeline.POOLED]),
    ]
    if workspace.players.exists():
        arguments += ["--players", str(workspace.players)]
    for other, path in workspace.servings.items():
        if path.exists():
            arguments += ["--serving-db", f"{other}={path}"]
    subprocess.run(arguments, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def _commit(
    con: duckdb.DuckDBPyConnection,
    plan: Plan,
    result: SyncResult,
    workspace: _Workspace,
    people: Path,
    started: dt.datetime,
    feed: str,
) -> None:
    """Keep the files this sync took in, swap the staging files in, update the log."""
    assert result.data_version is not None
    store = paths.raw_dir() / "feeds" / workspace.stamp
    store.mkdir(parents=True, exist_ok=True)
    shutil.copy2(people, store / raw.PEOPLE)
    with zipfile.ZipFile(store / "matches.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for item in plan.incoming:
            zf.writestr(f"{item.match_id}.json", item.content)
    manifest = {
        "feed": feed,
        "downloaded_at": started.isoformat(),
        "data_version": result.data_version,
        "matches": sorted(i.match_id for i in plan.incoming),
        "license": "Cricsheet data: Open Data Commons Attribution License (ODC-BY 1.0)",
    }
    (store / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    interim = paths.interim_dir() / result.data_version
    if interim.exists():
        shutil.rmtree(workspace.interim)
    else:
        os.replace(workspace.interim, interim)
    os.replace(workspace.warehouse, paths.cricket_warehouse_path())
    if workspace.report is not None:
        pipeline.save_validation(workspace.report, paths.cricket_warehouse_path())
    for competition, path in workspace.scopes.items():
        if path.exists():
            os.replace(path, paths.warehouse_path(competition))
    if workspace.serving.exists():
        result.serving = publish(workspace.serving, paths.serving_path())
    if workspace.players.exists():
        publish(workspace.players, paths.players_path())
    for competition, path in workspace.servings.items():
        if path.exists():
            publish(path, paths.serving_path(competition))

    source = (store / "matches.zip").relative_to(paths.raw_dir()).as_posix()
    quarantined = {q.match_id: q for q in result.quarantined}
    for item in plan.incoming:
        q = quarantined.get(item.match_id)
        if q is not None and q.kept_previous:
            # A correction that failed: the previous version stays in use.
            con.execute(
                "UPDATE ingest_log SET detail = ?, updated_at = ? WHERE match_id = ?",
                [f"correction quarantined: {q.reason}", started, item.match_id],
            )
        else:
            status = "quarantined" if q else "active"
            _upsert(con, item, status, source, q.reason if q else None, started)
    for match_id in plan.withdrawn:
        con.execute(
            "UPDATE ingest_log SET status = 'withdrawn', updated_at = ? WHERE match_id = ?",
            [started, match_id],
        )
    pipeline.save_state(pipeline.DataState(result.data_version, interim, store / raw.PEOPLE))
    _prune(con, interim)


def _upsert(
    con: duckdb.DuckDBPyConnection,
    item: Incoming,
    status: str,
    source: str,
    detail: str | None,
    when: dt.datetime,
) -> None:
    con.execute(
        """
        INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (match_id) DO UPDATE SET
            competition_id = excluded.competition_id, match_date = excluded.match_date,
            sha256 = excluded.sha256, status = excluded.status, source = excluded.source,
            detail = excluded.detail, updated_at = excluded.updated_at
        """,
        [
            item.match_id,
            item.competition_id,
            item.match_date,
            item.sha256,
            status,
            source,
            detail,
            when,
            when,
        ],
    )


def _prune(con: duckdb.DuckDBPyConnection, current: Path) -> None:
    """Keep the current and previous interim versions, and the feed files a logged
    match still comes from (plus the current register)."""
    versions = sorted(
        (d for d in paths.interim_dir().iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=lambda d: d.stat().st_mtime,
    )
    for old in versions[:-2]:
        if old != current:
            shutil.rmtree(old, ignore_errors=True)
    feeds = paths.raw_dir() / "feeds"
    if not feeds.exists():
        return
    used = {
        str(source).split("/")[1]
        for (source,) in con.execute(
            "SELECT DISTINCT source FROM ingest_log WHERE source LIKE 'feeds/%'"
        ).fetchall()
    }
    keep = pipeline.current_state().people.parent
    for folder in feeds.iterdir():
        if folder.name not in used and folder != keep:
            shutil.rmtree(folder, ignore_errors=True)


def _next_run_id(con: duckdb.DuckDBPyConnection) -> int:
    row = con.execute("SELECT coalesce(max(run_id), 0) + 1 FROM sync_runs").fetchone()
    return int(row[0]) if row else 1


def _record_run(
    con: duckdb.DuckDBPyConnection,
    result: SyncResult,
    started: dt.datetime,
    detail: str | None = None,
) -> None:
    con.execute(
        "INSERT INTO sync_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            _next_run_id(con),
            started,
            _now(),
            result.kind,
            result.feed,
            result.status,
            result.data_version,
            result.checked,
            result.new,
            result.corrected,
            result.withdrawn,
            len(result.quarantined),
            result.seconds,
            detail,
        ],
    )


def _update_rows(run_id: int, result: SyncResult, started: dt.datetime) -> list[list[Any]]:
    return [
        [
            run_id,
            started,
            result.kind,
            competition,
            c["new"],
            c["corrected"],
            c["withdrawn"],
            c["quarantined"],
        ]
        for competition, c in sorted(result.by_competition.items())
    ]


def _record_updates(
    con: duckdb.DuckDBPyConnection, result: SyncResult, started: dt.datetime
) -> None:
    """The update record of the run just recorded."""
    rows = _update_rows(_next_run_id(con) - 1, result, started)
    if rows:
        con.executemany("INSERT INTO data_updates VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)


# --------------------------------------------------------------------------- full rebuilds


def record_snapshot(
    snapshot: raw.RawSnapshot,
    *,
    kind: str = "full",
    warehouse: Path | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
    now: dt.datetime | None = None,
) -> SyncResult:
    """Bring the ingest log in line with a full download that was just built.

    Matches the build set aside (``warehouse``'s quarantine table) are logged as
    quarantined. The first record is ``initial``: everything in it is new, and
    the site does not announce it as an update.
    """
    own = con is None
    con = con or connect()
    started = now or _now()
    clock = dt.datetime.now()
    try:
        config = load_competitions()
        selected = {c.id for c in pipeline.selected_competitions()}
        entries = _entries(con)
        if not entries:
            kind = "initial"
        incoming = {
            i.match_id: i for a in snapshot.archives for i in read_archive(a, config, selected)
        }
        plan = plan_changes(entries, incoming.values(), complete_for=selected)
        held = _held(warehouse)
        for item in plan.incoming:
            reason = held.get(item.match_id)
            source = f"{snapshot.version}/{item.archive}"
            _upsert(con, item, "quarantined" if reason else "active", source, reason, started)
        for match_id in plan.withdrawn:
            con.execute(
                "UPDATE ingest_log SET status = 'withdrawn', updated_at = ? WHERE match_id = ?",
                [started, match_id],
            )
        quarantined = [
            Quarantined(m, incoming[m].competition_id, r) for m, r in held.items() if m in incoming
        ]
        taken = {i.match_id for i in plan.incoming} - set(held)
        result = SyncResult(
            kind=kind,
            feed=FULL,
            status="up_to_date" if plan.empty else "updated",
            checked=len(incoming),
            new=sum(1 for i in plan.new if i.match_id in taken),
            corrected=sum(1 for i in plan.corrected if i.match_id in taken),
            withdrawn=len(plan.withdrawn),
            unchanged=plan.unchanged,
            quarantined=quarantined,
            data_version=snapshot.version,
            by_competition=_by_competition(plan, taken, quarantined, entries),
        )
        result.seconds = (dt.datetime.now() - clock).total_seconds()
        _record_run(con, result, started)
        _record_updates(con, result, started)
        pipeline.save_state(pipeline.DataState.of(snapshot))
        return result
    finally:
        if own:
            con.close()


def _held(warehouse: Path | None) -> dict[int, str]:
    if warehouse is None or not warehouse.exists():
        return {}
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute("SELECT match_id, rule || ': ' || detail FROM quarantine").fetchall()
    finally:
        con.close()
    return {int(m): str(r) for m, r in rows}


# --------------------------------------------------------------------------- status


@dataclass
class Status:
    data_version: str
    runs: list[dict[str, Any]]
    last_update: dict[str, Any] | None
    counts: dict[str, int]
    quarantined: list[dict[str, Any]]


def status(limit: int = 10) -> Status:
    """What ``criciq-data sync-status`` prints."""
    con = connect(read_only=True)
    try:
        runs = _dicts(con, f"SELECT * FROM sync_runs ORDER BY run_id DESC LIMIT {int(limit)}")
        updates = _dicts(
            con, "SELECT * FROM sync_runs WHERE status = 'updated' ORDER BY run_id DESC LIMIT 1"
        )
        counts = con.execute(
            "SELECT status, count(*) FROM ingest_log GROUP BY status ORDER BY status"
        ).fetchall()
        quarantined = _dicts(
            con,
            "SELECT match_id, competition_id, match_date, status, detail FROM ingest_log "
            "WHERE detail IS NOT NULL ORDER BY match_date DESC, match_id",
        )
    finally:
        con.close()
    return Status(
        data_version=pipeline.current_state().version,
        runs=runs,
        last_update=updates[0] if updates else None,
        counts={str(k): int(v) for k, v in counts},
        quarantined=quarantined,
    )


def _dicts(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cursor = con.execute(sql)
    columns = [d[0] for d in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _ensure(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory
