"""On This Day: every match a competition's data has on a calendar date, in any year, with
its standout performance and biggest swing, most notable first."""

from __future__ import annotations

import calendar

from criciq_api.db import Database, Row
from criciq_api.repositories import on_this_day as repo
from criciq_api.schemas.on_this_day import (
    DayEntry,
    DayPerformance,
    DaySwing,
    OnThisDay,
)
from criciq_api.schemas.players import TeamTag
from criciq_core.cricket import overs_notation

# What makes a match stand out (summed): a final, another knockout, a hundred or fifty, a
# five- or four-wicket haul, and a single ball that swung the result.
FINAL = 3
PLAYOFF = 2
HUNDRED = 3
FIFTY = 1
FIVE_FOR = 3
FOUR_FOR = 1
BIG_SWING = 1
BIG_SWING_POINTS = 50.0


class InvalidDateError(ValueError):
    pass


def check_date(month: int, day: int) -> None:
    """A real calendar date in some year (29 February included)."""
    if not 1 <= month <= 12:
        raise InvalidDateError("month must be 1 to 12")
    if not 1 <= day <= calendar.monthrange(2024, month)[1]:  # 2024 is a leap year
        raise InvalidDateError(f"{calendar.month_name[month]} has no day {day}")


def _tag(r: Row, prefix: str) -> TeamTag | None:
    fid, name = r.get(f"{prefix}_id"), r.get(f"{prefix}_name")
    if fid is None or name is None:
        return None
    return TeamTag(franchise_id=fid, name=name, color=r[f"{prefix}_color"])


def _batting(r: Row, teams: dict[str, TeamTag]) -> DayPerformance | None:
    if r["bat_id"] is None or r["bat_name"] is None:
        return None
    against = teams.get(r["bat_against"])
    return DayPerformance(
        kind="batting",
        player_id=r["bat_id"],
        name=r["bat_name"],
        team=teams.get(r["bat_team"]),
        figure=f"{r['bat_runs']}{'' if r['bat_out'] else '*'}",
        detail=f"off {r['bat_balls']} ball{'' if r['bat_balls'] == 1 else 's'}",
        against=against.name if against else None,
    )


def _bowling(r: Row, teams: dict[str, TeamTag]) -> DayPerformance | None:
    if r["bowl_id"] is None or r["bowl_name"] is None:
        return None
    against = teams.get(r["bowl_against"])
    return DayPerformance(
        kind="bowling",
        player_id=r["bowl_id"],
        name=r["bowl_name"],
        team=teams.get(r["bowl_team"]),
        figure=f"{r['bowl_wickets']}/{r['bowl_runs']}",
        detail=f"in {overs_notation(r['bowl_balls'])} overs",
        against=against.name if against else None,
    )


def _swing(r: Row) -> DaySwing | None:
    if r.get("swing") is None:
        return None
    return DaySwing(
        ball=f"{r['swing_innings']}.{r['swing_seq']}",
        team=_tag(r, "swing_team"),
        before=round(100 * r["wp_before"], 1),
        after=round(100 * r["wp_after"], 1),
        swing=round(100 * r["swing"], 1),
    )


def notability(r: Row, swing: DaySwing | None) -> int:
    score = 0
    if r["stage"] == "Final":
        score += FINAL
    elif r["is_playoff"]:
        score += PLAYOFF
    runs = r["bat_runs"] or 0
    score += HUNDRED if runs >= 100 else FIFTY if runs >= 50 else 0
    wickets = r["bowl_wickets"] or 0
    score += FIVE_FOR if wickets >= 5 else FOUR_FOR if wickets >= 4 else 0
    if swing is not None and swing.swing >= BIG_SWING_POINTS:
        score += BIG_SWING
    return score


def _highlight(
    batting: DayPerformance | None, bowling: DayPerformance | None, r: Row
) -> DayPerformance | None:
    """The performance that leads: a hundred, a four-wicket haul, else the better of the two."""
    runs, wickets = r["bat_runs"] or 0, r["bowl_wickets"] or 0
    if batting and runs >= 100:
        return batting
    if bowling and wickets >= 4:
        return bowling
    if batting and runs >= 50:
        return batting
    if bowling and wickets >= 3:
        return bowling
    return batting or bowling


def _entry(r: Row) -> DayEntry:
    a, b = _tag(r, "a"), _tag(r, "b")
    teams = {t.franchise_id: t for t in (a, b) if t is not None}
    batting, bowling, swing = _batting(r, teams), _bowling(r, teams), _swing(r)
    highlight = _highlight(batting, bowling, r)
    if highlight is not None:
        against = f" against {highlight.against}" if highlight.against else ""
        headline = f"{highlight.name}: {highlight.figure}{against}"
    else:
        headline = r["result_text"]
    return DayEntry(
        match_id=r["match_id"],
        date=r["match_date"],
        year=r["match_date"].year,
        season=r["season"],
        stage=r["stage"],
        is_playoff=r["is_playoff"],
        teams=[t for t in (a, b) if t is not None],
        venue=r["venue_name"],
        result=r["result_text"],
        headline=headline,
        highlight=highlight,
        batting=batting,
        bowling=bowling,
        player_of_match=list(r["player_of_match"] or []),
        swing=swing,
        notability=notability(r, swing),
    )


def get_day(db: Database, month: int, day: int) -> OnThisDay:
    check_date(month, day)
    key = f"on-this-day:{month}:{day}"
    if key in db.cache:
        cached: OnThisDay = db.cache[key]
        return cached
    entries = [_entry(r) for r in repo.matches(db, month, day)]
    entries.sort(key=lambda e: (-e.notability, -e.date.toordinal(), e.match_id))
    found = OnThisDay(month=month, day=day, entries=entries)
    db.cache[key] = found
    return found
