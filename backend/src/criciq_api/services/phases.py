"""Phase Analysis: how a competition's innings are built, powerplay to death (or, in
Tests, new ball to second new ball), with the results, toss, leaders and grounds."""

from __future__ import annotations

from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import common
from criciq_api.repositories import phases as repo
from criciq_api.schemas.common import Coverage, Filters
from criciq_api.schemas.phases import (
    BattingLeader,
    BowlingLeader,
    GroundPhase,
    GroundPhases,
    OverPoint,
    PhaseAnalysis,
    PhaseFilters,
    PhaseLeaders,
    PhaseSummary,
    ResultSplit,
    SideRecord,
    TossDecision,
)
from criciq_api.schemas.players import TeamTag
from criciq_core import stats
from criciq_core.phases import default_phase_config

# Balls a player needs in a phase to lead it, by format: about two seasons' worth of
# death overs for a T20 specialist. Small datasets (the test fixtures) take everyone.
MIN_BALLS = {"T20": 60, "ODI": 120, "Test": 300}
SMALL_DATA_MATCHES = 50
LEADERS = 15
GROUNDS = 15
# Tests: the over chart groups ten overs to a point, up to the 150th over.
TEST_BLOCK = 10
TEST_MAX_OVER = 150
DASH = chr(0x2013)  # an en dash, as in a Test's "1 to 10" overs label


class PhaseDataMissingError(RuntimeError):
    pass


class InvalidPhaseFilterError(ValueError):
    pass


def default_min_balls(match_format: str, matches: int) -> int:
    return MIN_BALLS[match_format] if matches >= SMALL_DATA_MATCHES else 1


def _team(row: Row) -> TeamTag | None:
    if row["team_id"] is None or row["team_name"] is None:
        return None
    return TeamTag(franchise_id=row["team_id"], name=row["team_name"], color=row["team_color"])


def _side(matches: int, won: int, drawn: int) -> SideRecord:
    return SideRecord(matches=matches, won=won, drawn=drawn, win_pct=stats.percent(won, matches))


def _batting(rows: list[Row]) -> list[BattingLeader]:
    ranked = stats.ranks(rows, lambda r: r["runs"])
    return [
        BattingLeader(
            rank=rank,
            tied=tied,
            player_id=r["player_id"],
            name=r["name"],
            team=_team(r),
            innings=r["innings"],
            balls=r["balls"],
            runs=r["runs"],
            outs=r["outs"],
            strike_rate=stats.strike_rate(r["runs"], r["balls"]),
            average=stats.batting_average(r["runs"], r["outs"]),
            boundary_pct=stats.percent(r["boundaries"], r["balls"]),
            dot_pct=stats.percent(r["dots"], r["balls"]),
        )
        for r, (rank, tied) in zip(rows, ranked, strict=True)
    ]


def _bowling(rows: list[Row]) -> list[BowlingLeader]:
    ranked = stats.ranks(rows, lambda r: r["wickets"])
    return [
        BowlingLeader(
            rank=rank,
            tied=tied,
            player_id=r["player_id"],
            name=r["name"],
            team=_team(r),
            innings=r["innings"],
            balls=r["balls"],
            runs=r["runs"],
            wickets=r["wickets"],
            economy=stats.economy(r["runs"], r["balls"]),
            strike_rate=stats.bowling_strike_rate(r["balls"], r["wickets"]),
            average=stats.bowling_average(r["runs"], r["wickets"]),
            dot_pct=stats.percent(r["dots"], r["balls"]),
            boundary_pct=stats.percent(r["boundaries"], r["balls"]),
        )
        for r, (rank, tied) in zip(rows, ranked, strict=True)
    ]


def _by_phase(rows: list[Row]) -> dict[str, list[Row]]:
    found: dict[str, list[Row]] = {}
    for row in rows:
        found.setdefault(row["phase"], []).append(row)
    return found


def get_phases(
    db: Database,
    *,
    season_from: int | None = None,
    season_to: int | None = None,
    team: str | None = None,
    venue: str | None = None,
    innings: int | None = None,
    min_balls: int | None = None,
) -> PhaseAnalysis:
    if not repo.has_phase_tables(db):
        raise PhaseDataMissingError("phase tables are missing; run `criciq-data extras`")
    match_format = db.match_format
    limited = match_format != "Test"
    if innings is not None and limited and innings > 2:
        raise InvalidPhaseFilterError("limited-overs matches have two innings")
    if season_from is not None and season_to is not None and season_from > season_to:
        raise InvalidPhaseFilterError("the first season is after the last")

    key = f"phases:{season_from}:{season_to}:{team}:{venue}:{innings}:{min_balls}"
    if key in db.cache:
        cached: PhaseAnalysis = db.cache[key]
        return cached

    coverage = Coverage(**common.coverage(db))
    balls_needed = min_balls or default_min_balls(match_format, coverage.matches)
    filters = Filters(
        season_from=season_from, season_to=season_to, team=team, venue=venue, innings=innings
    )
    config = default_phase_config().for_format(match_format)

    totals = {r["phase"]: r for r in repo.phase_totals(db, filters)}
    summaries: list[PhaseSummary] = []
    for phase in config.phases:
        t: dict[str, Any] = totals.get(phase.key) or {
            k: 0 for k in ("innings", "runs", "balls", "wickets", "fours", "sixes", "dots")
        }
        summaries.append(
            PhaseSummary(
                key=phase.key,
                label=phase.label,
                first_over=phase.first_over,
                last_over=phase.last_over,
                innings=t["innings"],
                runs=t["runs"],
                balls=t["balls"],
                wickets=t["wickets"],
                fours=t["fours"],
                sixes=t["sixes"],
                dots=t["dots"],
                run_rate=stats.run_rate(t["runs"], t["balls"]),
                runs_per_innings=stats.per(t["runs"], t["innings"]),
                wickets_per_innings=stats.per(t["wickets"], t["innings"]),
                boundary_pct=stats.percent(t["fours"] + t["sixes"], t["balls"]),
                dot_pct=stats.percent(t["dots"], t["balls"]),
                balls_per_wicket=stats.balls_per_wicket(t["balls"], t["wickets"]),
            )
        )

    block = 1 if limited else TEST_BLOCK
    max_over = config.overs if limited else TEST_MAX_OVER
    overs = [
        OverPoint(
            first_over=r["first_over"],
            last_over=r["first_over"] + block - 1,
            label=str(r["first_over"])
            if block == 1
            else f"{r['first_over']}{DASH}{r['first_over'] + block - 1}",
            phase=r["phase"],
            innings=r["innings"],
            runs=r["runs"],
            balls=r["balls"],
            wickets=r["wickets"],
            run_rate=stats.run_rate(r["runs"], r["balls"]),
            wickets_per_over=stats.ratio(r["wickets"], r["balls"], 6),
        )
        for r in repo.over_totals(db, filters, block, max_over)
    ]

    split = repo.result_split(db, filters)
    results = ResultSplit(
        matches=split["matches"],
        batting_first=_side(split["first_matches"], split["first_won"], split["first_drawn"]),
        chasing=_side(split["second_matches"], split["second_won"], split["second_drawn"]),
        first_innings_average=stats.per(split["first_innings_average"], 1),
        average_total_defended=stats.per(split["defended"], 1) if limited else None,
    )
    toss = [
        TossDecision(
            decision=r["decision"],
            matches=r["matches"],
            toss_winner_won=r["toss_winner_won"],
            win_pct=stats.percent(r["toss_winner_won"], r["matches"]),
        )
        for r in repo.toss(db, filters)
    ]

    batters = _by_phase(repo.batting_leaders(db, filters, balls_needed, LEADERS))
    bowlers = _by_phase(repo.bowling_leaders(db, filters, balls_needed, LEADERS))
    leaders = [
        PhaseLeaders(
            phase=p.key,
            batters=_batting(batters.get(p.key, [])),
            bowlers=_bowling(bowlers.get(p.key, [])),
        )
        for p in config.phases
    ]

    by_ground: dict[str, GroundPhases] = {}
    for r in repo.grounds(db, filters, GROUNDS):
        ground = by_ground.setdefault(
            r["venue_id"],
            GroundPhases(
                venue_id=r["venue_id"],
                name=r["name"],
                city=r["city"],
                matches=r["matches"],
                phases=[],
            ),
        )
        ground.phases.append(
            GroundPhase(
                phase=r["phase"], balls=r["balls"], run_rate=stats.run_rate(r["runs"], r["balls"])
            )
        )
    order = {p.key: i for i, p in enumerate(config.phases)}
    for ground in by_ground.values():
        ground.phases.sort(key=lambda g: order.get(g.phase, len(order)))

    found = PhaseAnalysis(
        coverage=coverage,
        format=match_format,  # type: ignore[arg-type]
        filters=PhaseFilters(
            season_from=season_from,
            season_to=season_to,
            team=team,
            venue=venue,
            innings=innings,
            min_balls=balls_needed,
        ),
        phases=summaries,
        over_block=block,
        overs=overs,
        results=results,
        toss=toss,
        leaders=leaders,
        grounds=list(by_ground.values()),
    )
    db.cache[key] = found
    return found
