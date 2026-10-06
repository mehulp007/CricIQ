"""The incremental sync on the fixture matches: add, correct, quarantine, withdraw.

Each test starts from a full build of the fixtures with a few matches held back,
then syncs a feed built from fixture files (``fetch`` stands in for Cricsheet).
"""

from __future__ import annotations

import datetime as dt
import io
import json
import shutil
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq
import pytest

from criciq_core import paths
from criciq_pipelines import pipeline, sync
from criciq_pipelines.extract import SCHEMAS, extract_archive
from criciq_pipelines.raw import PEOPLE, store_snapshot
from tests.conftest import MATCHES_DIR, PEOPLE_CSV, load_match

ALL = sorted(int(p.stem) for p in MATCHES_DIR.glob("*.json"))
HELD = (1473511, 1420222)  # an IPL final and an ODI, kept back for the sync to bring
SOURCE_ERROR = 1229824  # a T20I the build always sets aside (a player on both sides)
IPL_MATCH = 1370352  # an IPL match in the initial build
T20I_MATCH = 1481295  # a T20I in the initial build (not a golden scorecard)


def _file(match_id: int) -> bytes:
    return (MATCHES_DIR / f"{match_id}.json").read_bytes()


def _zip(path: Path, files: dict[int, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for match_id, content in sorted(files.items()):
            zf.writestr(f"{match_id}.json", content)
    return path


def _changed(match_id: int, change: Callable[[dict[str, Any]], None]) -> bytes:
    doc = load_match(match_id)
    change(doc)
    return json.dumps(doc).encode()


def _fetch(feed: Path) -> sync.Fetch:
    """Cricsheet stand-in: every feed or archive is ``feed``; the register is the fixture's."""

    def fetch(name: str, directory: Path) -> Path:
        target = directory / name
        shutil.copyfile(PEOPLE_CSV if name == PEOPLE else feed, target)
        return target

    return fetch


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A full build of every fixture match except HELD, with its ingest log."""
    monkeypatch.setenv("CRICIQ_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("CRICIQ_COMPETITIONS", raising=False)
    archive = _zip(tmp_path / "ipl_json.zip", {m: _file(m) for m in ALL if m not in HELD})
    snapshot = store_snapshot([archive], PEOPLE_CSV)
    pipeline.run_extract(snapshot)
    pipeline.run_build(snapshot)
    assert pipeline.run_validate(require_all_golden=False).passed
    first = sync.record_snapshot(snapshot, warehouse=paths.cricket_warehouse_path())
    assert first.kind == "initial"
    pipeline.run_export()
    return tmp_path


def _sync(archive: Path, **kwargs: Any) -> sync.SyncResult:
    return sync.sync(fetch=_fetch(archive), score=False, require_all_golden=False, **kwargs)


def _query(path: Path, sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


def _ingest(sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    return _query(sync.ingest_path(), sql, params)


def test_a_sync_adds_new_matches_and_equals_a_full_build(built: Path) -> None:
    feed = _zip(built / "feed.zip", {m: _file(m) for m in (*HELD, IPL_MATCH)})
    result = _sync(feed, feed=sync.WEEK_FEED)
    assert (result.status, result.new, result.corrected, result.unchanged) == ("updated", 2, 0, 1)
    assert result.quarantined == []
    assert result.by_competition == {
        "IPL": {"new": 1, "corrected": 0, "withdrawn": 0, "quarantined": 0},
        "ODI": {"new": 1, "corrected": 0, "withdrawn": 0, "quarantined": 0},
    }
    warehouse = paths.cricket_warehouse_path()
    assert {m for (m,) in _query(warehouse, "SELECT match_id FROM matches")} >= set(HELD)

    # The interim tables equal a full extract of every fixture match.
    full = extract_archive(
        _zip(built / "all.zip", {m: _file(m) for m in ALL}), built / "full-interim"
    )
    state = pipeline.current_state()
    assert state.version == result.data_version
    for name in SCHEMAS:
        synced = pq.read_table(state.interim / f"{name}.parquet")
        expected = pq.read_table(built / "full-interim" / f"{name}.parquet")
        assert synced.equals(expected), name
        assert synced.num_rows == full[name]

    # The serving database now records the update the API reports.
    rows = _query(
        paths.serving_path(),
        "SELECT kind, competition_id, new_matches FROM data_updates ORDER BY run_id DESC",
    )
    assert rows[0] == ("sync", "IPL", 1)
    assert ("initial", "IPL", 13) in rows

    again = _sync(feed, feed=sync.WEEK_FEED)
    assert (again.status, again.new, again.unchanged) == ("up_to_date", 0, 3)
    assert _ingest("SELECT count(*) FROM sync_runs") == [(3,)]


def test_a_sync_applies_a_correction(built: Path) -> None:
    corrected = _changed(IPL_MATCH, lambda d: d["info"]["toss"].update(decision="bat"))
    before = _query(
        paths.cricket_warehouse_path(),
        "SELECT toss_decision FROM matches WHERE match_id = ?",
        [IPL_MATCH],
    )
    assert before != [("bat",)]
    result = _sync(_zip(built / "feed.zip", {IPL_MATCH: corrected}), feed=sync.WEEK_FEED)
    assert (result.status, result.new, result.corrected) == ("updated", 0, 1)
    after = _query(
        paths.cricket_warehouse_path(),
        "SELECT toss_decision FROM matches WHERE match_id = ?",
        [IPL_MATCH],
    )
    assert after == [("bat",)]
    assert _ingest(
        "SELECT status, source LIKE 'feeds/%' FROM ingest_log WHERE match_id = ?", [IPL_MATCH]
    ) == [("active", True)]


def test_a_new_match_that_cannot_be_built_is_quarantined(built: Path) -> None:
    # An IPL match at a ground the curated config does not know: the IPL is strict.
    unknown = _changed(HELD[0], lambda d: d["info"].update(venue="Nowhere Stadium"))
    feed = _zip(built / "feed.zip", {HELD[0]: unknown, HELD[1]: _file(HELD[1])})
    result = _sync(feed, feed=sync.WEEK_FEED)
    assert (result.status, result.new) == ("updated", 1)
    (q,) = result.quarantined
    assert (q.match_id, q.competition_id, q.kept_previous) == (HELD[0], "IPL", False)
    assert "Nowhere Stadium" in q.reason
    ids = {m for (m,) in _query(paths.cricket_warehouse_path(), "SELECT match_id FROM matches")}
    assert HELD[1] in ids
    assert HELD[0] not in ids
    assert _ingest("SELECT status FROM ingest_log WHERE match_id = ?", [HELD[0]]) == [
        ("quarantined",)
    ]
    # The same file again stays quarantined without a rebuild.
    again = _sync(feed, feed=sync.WEEK_FEED)
    assert again.status == "up_to_date"


def test_a_correction_that_cannot_be_built_keeps_the_previous_version(built: Path) -> None:
    def venue() -> list[tuple[Any, ...]]:
        return _query(
            paths.cricket_warehouse_path(),
            "SELECT venue_id FROM matches WHERE match_id = ?",
            [IPL_MATCH],
        )

    before = venue()
    broken = _changed(IPL_MATCH, lambda d: d["info"].update(venue="Nowhere Stadium"))
    result = _sync(_zip(built / "feed.zip", {IPL_MATCH: broken}), feed=sync.WEEK_FEED)
    (q,) = result.quarantined
    assert q.kept_previous
    assert result.corrected == 0
    assert venue() == before
    status, detail = _ingest(
        "SELECT status, detail FROM ingest_log WHERE match_id = ?", [IPL_MATCH]
    )[0]
    assert status == "active"
    assert detail.startswith("correction quarantined")


def test_a_full_check_finds_withdrawn_matches(built: Path) -> None:
    everything_but_one = {m: _file(m) for m in ALL if m not in HELD and m != T20I_MATCH}
    result = _sync(_zip(built / "all.zip", everything_but_one), feed=sync.FULL)
    assert (result.kind, result.status, result.withdrawn) == ("full", "updated", 1)
    ids = {m for (m,) in _query(paths.cricket_warehouse_path(), "SELECT match_id FROM matches")}
    assert T20I_MATCH not in ids
    assert _ingest("SELECT status FROM ingest_log WHERE match_id = ?", [T20I_MATCH]) == [
        ("withdrawn",)
    ]


def test_a_failed_sync_changes_nothing(built: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = pipeline.current_state().version

    def broken_export(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("export failed")

    monkeypatch.setattr(sync, "export_serving", broken_export)
    feed = _zip(built / "feed.zip", {HELD[1]: _file(HELD[1])})
    with pytest.raises(RuntimeError, match="export failed"):
        _sync(feed, feed=sync.WEEK_FEED)
    assert pipeline.current_state().version == version
    assert _ingest("SELECT count(*) FROM ingest_log WHERE match_id = ?", [HELD[1]]) == [(0,)]
    assert _ingest("SELECT status FROM sync_runs ORDER BY run_id DESC LIMIT 1") == [("failed",)]
    assert not list(paths.interim_dir().glob(".sync-*"))


def test_status_reports_runs_and_quarantine(built: Path) -> None:
    unknown = _changed(HELD[0], lambda d: d["info"].update(venue="Nowhere Stadium"))
    _sync(_zip(built / "feed.zip", {HELD[0]: unknown}), feed=sync.WEEK_FEED)
    report = sync.status()
    assert report.data_version == pipeline.current_state().version
    assert report.counts == {"active": len(ALL) - len(HELD) - 1, "quarantined": 2}
    assert {q["match_id"] for q in report.quarantined} == {HELD[0], SOURCE_ERROR}
    assert report.runs[0]["kind"] == "sync"


@pytest.mark.parametrize(
    ("days", "feed"),
    [
        (None, sync.FULL),
        (1, sync.WEEK_FEED),
        (6, sync.WEEK_FEED),
        (7, sync.MONTH_FEED),
        (28, sync.MONTH_FEED),
        (29, sync.FULL),
    ],
)
def test_the_feed_reaches_back_to_the_last_sync(days: int | None, feed: str) -> None:
    now = dt.datetime(2027, 4, 1, 12)
    last = None if days is None else now - dt.timedelta(days=days)
    assert sync.choose_feed(last, now) == feed


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_downloads_retry_dropped_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies: list[Exception | bytes] = [
        urllib.error.URLError(ConnectionResetError(10054, "forcibly closed")),
        b"zip bytes",
    ]

    def urlopen(request: object, timeout: float) -> _Response:
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _Response(reply)

    waits: list[float] = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    path = sync.download(sync.WEEK_FEED, tmp_path, sleep=waits.append)
    assert path.read_bytes() == b"zip bytes"
    assert waits == [sync.RETRY_DELAYS_SECONDS[0]]
    assert not list(tmp_path.glob("*.part"))


def test_downloads_give_up_after_the_last_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def urlopen(request: object, timeout: float) -> _Response:
        raise urllib.error.URLError("down")

    waits: list[float] = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(sync.SyncError, match="could not download"):
        sync.download(sync.WEEK_FEED, tmp_path, sleep=waits.append)
    assert waits == list(sync.RETRY_DELAYS_SECONDS)


def test_downloads_do_not_retry_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def urlopen(request: object, timeout: float) -> _Response:
        raise urllib.error.HTTPError("https://x", 404, "Not Found", Message(), None)

    waits: list[float] = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(sync.SyncError, match="404"):
        sync.download("nonexistent.zip", tmp_path, sleep=waits.append)
    assert waits == []
