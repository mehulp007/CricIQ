"""The Records hub: every record in a competition's ball-by-ball data, its leader, and
each record's ranked list with filters."""

from __future__ import annotations

import threading
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import common
from criciq_api.repositories import records as repo
from criciq_api.schemas.common import Coverage, Filters
from criciq_api.schemas.players import TeamTag
from criciq_api.schemas.records import (
    RecordEntry,
    RecordFigure,
    RecordFilters,
    RecordGroup,
    RecordInfo,
    RecordLeader,
    RecordList,
    RecordPlayer,
    RecordsHub,
)
from criciq_core.records import Qualification, default_records_config

GROUPS: tuple[RecordGroup, ...] = (
    "batting",
    "bowling",
    "fielding",
    "seasons",
    "partnerships",
    "teams",
    "ball_by_ball",
)
MAX_LIMIT = 600
HUB_LEADERS = 3

# A record query is a grouped or windowed scan, which DuckDB runs on every core with working
# memory per core, however small the data. A burst of them (a build rendering every
# competition's hub at once) can fill a connection's memory limit, so at most two run at a
# time, and each database's hub is built once while other requests for it wait.
_QUERIES = threading.BoundedSemaphore(2)
_HUB_BUILD = threading.Lock()


def _ranked(
    db: Database,
    record: repo.RecordDef,
    filters: Filters,
    q: Qualification,
    **options: Any,
) -> list[Row]:
    with _QUERIES:
        return repo.ranked(db, record, filters, q, **options)


_QUALIFIES = {
    "batting_innings": "At least {} innings",
    "career_balls_faced": "At least {} balls faced",
    "innings_balls_faced": "At least {} balls faced in the innings",
    "bowling_wickets": "At least {} wickets",
    "career_balls_bowled": "At least {} balls bowled",
    "innings_balls_bowled": "At least {} balls bowled in the innings",
}


class RecordDataMissingError(RuntimeError):
    pass


class RecordNotFoundError(KeyError):
    pass


class InvalidRecordFilterError(ValueError):
    pass


def _qualification(db: Database, matches: int) -> Qualification:
    return default_records_config().qualification(db.match_format, matches)


def _label(record: repo.RecordDef, national: bool) -> str:
    # International "seasons" are calendar years.
    if record.group == "seasons" and national:
        return record.label.replace("in a season", "in a calendar year")
    return record.label


def _info(
    record: repo.RecordDef, q: Qualification, national: bool, match_format: str
) -> RecordInfo:
    qualification = None
    if record.qualification:
        amount: int | None = getattr(q, record.qualification)
        qualification = _QUALIFIES[record.qualification].format(amount) if amount else None
    return RecordInfo(
        key=record.key,
        group=record.group,
        label=_label(record, national),
        level=record.level,
        ascending=record.ascending,
        unit=record.unit,
        description=record.description,
        qualification=qualification,
        model=record.model,
        columns=[c[0] for c in record.columns_for(match_format)],
    )


def _figure(value: Any, digits: int, kind: str) -> str:
    if value is None:
        return "—"
    if kind == "int":
        return f"{int(value):,}"
    if kind == "pct":
        return f"{float(value):.{digits}f}%"
    if kind == "num":
        return f"{float(value):,.{digits}f}"
    return str(value)


def _display(record: repo.RecordDef, r: Row) -> str:
    v = r["value"]
    if record.key == "best-bowling-figures":
        return f"{int(r['x1'])}/{int(r['x2'])}"
    if record.level == "innings" and record.group == "batting":
        runs = f"{int(r['x1'])}{'*' if r['flag'] else ''}"
        if record.key in {"fastest-fifties", "fastest-hundreds"}:
            return f"{int(v)} balls"
        if record.key == "highest-scores":
            return runs
        if record.key == "highest-strike-rate-innings":
            return f"{v:.2f}"
        return f"{int(v)}"
    if record.key == "highest-partnerships":
        return f"{int(v)}{'*' if r['flag'] else ''}"
    if record.group == "teams" and record.level == "innings":
        wickets = int(r["x2"])
        declared = "d" if r["flag"] else ""
        return f"{int(v)}" if wickets >= 10 else f"{int(v)}/{wickets}{declared}"
    if record.key == "biggest-innings-wins":
        return f"Inns & {int(v)} runs"
    if record.key == "biggest-win-probability-swings":
        return f"{v:.1f} pts"
    if record.key == "highest-wpa-in-a-match":
        return f"{v:+.3f}"
    if float(v).is_integer() and not record.ascending:
        return f"{int(v):,}"
    return f"{v:.2f}"


def _tag(r: Row, prefix: str) -> TeamTag | None:
    fid = r[f"{prefix}_id"]
    if fid is None or r[f"{prefix}_name"] is None:
        return None
    return TeamTag(franchise_id=fid, name=r[f"{prefix}_name"], color=r[f"{prefix}_color"])


def _entry(record: repo.RecordDef, r: Row, match_format: str) -> RecordEntry:
    players = [
        RecordPlayer(player_id=r[k], name=r[n], role=role)  # type: ignore[arg-type]
        for (k, n), role in zip(
            (("player_id", "player_name"), ("partner_id", "partner_name")),
            record.roles,
            strict=True,
        )
        if r[k] is not None and r[n] is not None
    ]
    ball = None
    if r["innings_no"] is not None and r["seq_no"] is not None:
        ball = f"{r['innings_no']}.{r['seq_no']}"
    return RecordEntry(
        rank=r["rank"],
        tied=r["tied"],
        value=float(r["value"]),
        display=_display(record, r),
        players=players,
        team=_tag(r, "team"),
        opponent=_tag(r, "opponent"),
        venue=r["venue_name"],
        match_id=r["match_id"],
        date=r["match_date"],
        season=r["season"],
        ball=ball,
        figures=[
            RecordFigure(label=label, value=_figure(r[column], digits, kind))
            for label, column, digits, kind in record.columns_for(match_format)
        ],
    )


def _check(db: Database) -> tuple[Coverage, Qualification, bool]:
    if not repo.has_record_tables(db):
        raise RecordDataMissingError("record tables are missing; run `criciq-data extras`")
    coverage = Coverage(**common.coverage(db))
    national = db.scalar("SELECT team_type FROM competitions LIMIT 1") == "national"
    return coverage, _qualification(db, coverage.matches), national


def get_hub(db: Database) -> RecordsHub:
    if "records:hub" in db.cache:
        cached: RecordsHub = db.cache["records:hub"]
        return cached
    with _HUB_BUILD:
        # Another request may have built it while this one waited.
        if "records:hub" in db.cache:
            built: RecordsHub = db.cache["records:hub"]
            return built
        found = _build_hub(db)
        db.cache["records:hub"] = found
        return found


def _build_hub(db: Database) -> RecordsHub:
    coverage, q, national = _check(db)
    leaders: list[RecordLeader] = []
    for record in repo.RECORDS:
        if not repo.available(db, record):
            continue
        rows = _ranked(db, record, Filters(), q, limit=HUB_LEADERS)
        top = [r for r in rows if r["rank"] == 1]
        if not top:
            continue
        leaders.append(
            RecordLeader(
                record=_info(record, q, national, db.match_format),
                leaders=[_entry(record, r, db.match_format) for r in top],
                tied_count=top[0]["first_count"],
            )
        )
    return RecordsHub(
        coverage=coverage,
        format=db.match_format,  # type: ignore[arg-type]
        groups=[g for g in GROUPS if any(lead.record.group == g for lead in leaders)],
        records=leaders,
    )


def get_record(
    db: Database,
    key: str,
    *,
    season_from: int | None = None,
    season_to: int | None = None,
    team: str | None = None,
    opponent: str | None = None,
    venue: str | None = None,
    wicket: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> RecordList:
    record = repo.BY_KEY.get(key)
    if record is None or not repo.available(db, record):
        raise RecordNotFoundError(key)
    if season_from is not None and season_to is not None and season_from > season_to:
        raise InvalidRecordFilterError("the first season is after the last")
    if wicket is not None and "wicket" not in record.extra_filters:
        raise InvalidRecordFilterError("only partnerships can be filtered by wicket")
    limit = min(limit, MAX_LIMIT)
    cache_key = ":".join(
        str(p)
        for p in (
            "records",
            key,
            season_from,
            season_to,
            team,
            opponent,
            venue,
            wicket,
            limit,
            offset,
        )
    )
    if cache_key in db.cache:
        cached: RecordList = db.cache[cache_key]
        return cached
    coverage, q, national = _check(db)
    filters = Filters(
        season_from=season_from, season_to=season_to, team=team, opponent=opponent, venue=venue
    )
    rows = _ranked(db, record, filters, q, wicket=wicket, limit=limit, offset=offset)
    found = RecordList(
        coverage=coverage,
        format=db.match_format,  # type: ignore[arg-type]
        record=_info(record, q, national, db.match_format),
        filters=RecordFilters(
            season_from=season_from,
            season_to=season_to,
            team=team,
            opponent=opponent,
            venue=venue,
            wicket=wicket,
        ),
        total=rows[0]["total"] if rows else 0,
        offset=offset,
        entries=[_entry(record, r, db.match_format) for r in rows],
    )
    db.cache[cache_key] = found
    return found
