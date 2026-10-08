"""Assemble Team Analytics responses: overview, league tables, team profiles and head-to-head."""

from __future__ import annotations

import math
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import teams as repo
from criciq_api.schemas.players import SeasonWindow, TeamTag
from criciq_api.schemas.teams import (
    FormerName,
    FranchiseSummary,
    H2HExpectation,
    H2HPlayer,
    H2HRecord,
    H2HScoring,
    H2HSeason,
    H2HSplit,
    LeagueTrends,
    OpponentRecord,
    PhaseLine,
    Rate,
    Record,
    RecordGroup,
    RecordSplit,
    SeasonChampion,
    SeasonTrend,
    StandingRow,
    Standings,
    Swing,
    TeamBatter,
    TeamBowler,
    TeamHeadToHead,
    TeamMargin,
    TeamPhase,
    TeamProfile,
    TeamScoring,
    TeamSeason,
    TeamsOverview,
    TeamTotal,
    VenueRecord,
)
from criciq_api.services.matches import summary_from_row
from criciq_api.services.players import resolve_window
from criciq_core.cricket import overs_notation
from criciq_core.phases import default_phase_config
from criciq_core.teams import form_probability, log5

# Two-sided 90% intervals throughout, as elsewhere in CricIQ.
Z90 = 1.645

SPLIT_GROUPS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("innings", "Batting order", [("bat_first", "Batting first"), ("chasing", "Chasing")]),
    ("toss", "Toss", [("won_toss", "Won the toss"), ("lost_toss", "Lost the toss")]),
    ("venue", "Ground", [("home", "Home"), ("away", "Away"), ("neutral", "Neutral")]),
    ("stage", "Stage", [("league", "League"), ("playoffs", "Playoffs")]),
]


class TeamNotFoundError(LookupError):
    pass


class TeamDataMissingError(LookupError):
    pass


class SeasonNotFoundError(LookupError):
    pass


class SameTeamError(ValueError):
    pass


# --------------------------------------------------------------------------- helpers


def _ratio(
    num: float | None, den: float | None, scale: float = 1.0, digits: int = 2
) -> float | None:
    if num is None or not den:
        return None
    return round(scale * num / den, digits)


def wilson(hits: int, total: int, z: float = Z90) -> tuple[float, float] | None:
    """Wilson score interval for a proportion, in percent."""
    if total <= 0:
        return None
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return round(100 * (centre - half), 1), round(100 * (centre + half), 1)


def _rate(hits: int, total: int) -> Rate:
    interval = wilson(hits, total)
    return Rate(
        hits=hits,
        total=total,
        pct=_ratio(hits, total, 100, 1),
        low=interval[0] if interval else None,
        high=interval[1] if interval else None,
    )


def _record(r: Row | None) -> Record:
    if r is None:
        return Record(played=0, won=0, lost=0, no_result=0, drawn=0, win_pct=None)
    return Record(
        played=r["played"],
        won=r["won"],
        lost=r["lost"],
        no_result=r["no_result"],
        drawn=r.get("drawn") or 0,
        win_pct=_ratio(r["won"], r["won"] + r["lost"] + (r.get("drawn") or 0), 100, 1),
    )


def _require_tables(db: Database) -> None:
    if not repo.has_team_tables(db):
        raise TeamDataMissingError("team tables are missing; re-export the serving database")


def _franchise_rows(db: Database) -> dict[str, Row]:
    cache_key = "team_franchises"
    if cache_key not in db.cache:
        db.cache[cache_key] = {r["franchise_id"]: r for r in repo.franchises(db)}
    rows: dict[str, Row] = db.cache[cache_key]
    return rows


def _tag(franchises: dict[str, Row], franchise_id: str) -> TeamTag:
    f = franchises[franchise_id]
    return TeamTag(franchise_id=franchise_id, name=f["name"], color=f["color"])


def _summary(r: Row) -> FranchiseSummary:
    return FranchiseSummary(
        franchise_id=r["franchise_id"],
        name=r["name"],
        color=r["color"],
        secondary_color=r["secondary_color"],
        is_active=r["is_active"],
        first_season=r["first_season"],
        last_season=r["last_season"],
        seasons=r["seasons"],
        names=[FormerName(**n) for n in r["names"]],
        record=_record(r),
        titles=r["titles"],
        finals=r["finals"],
        playoffs=r["playoffs"],
    )


def _franchise_id(db: Database, franchise_id: str) -> str:
    key = franchise_id.upper()
    if key not in _franchise_rows(db):
        raise TeamNotFoundError(franchise_id)
    return key


# --------------------------------------------------------------------------- overview


def get_overview(db: Database) -> TeamsOverview:
    _require_tables(db)
    franchises = _franchise_rows(db)
    champions = [
        SeasonChampion(
            season=c["season"],
            champion=_tag(franchises, c["champion_id"]),
            runner_up=_tag(franchises, c["runner_up_id"]) if c["runner_up_id"] else None,
            final_match_id=c["final_match_id"],
            result_text=c["result_text"],
        )
        for c in repo.champions(db)
    ]
    rates = repo.league_rates(db)
    trends = [
        SeasonTrend(
            season=t["season"],
            matches=t["decided"],
            chasing_win_pct=_ratio(t["chasing_won"], t["decided"], 100, 1),
            toss_winner_win_pct=_ratio(t["toss_won"], t["tossed"], 100, 1),
            field_first_pct=_ratio(t["fielded"], t["tosses"], 100, 1),
            home_win_pct=_ratio(t["home_won"], t["home_games"], 100, 1)
            if t["home_games"] >= 10
            else None,
            avg_first_innings=None
            if t["avg_first_innings"] is None
            else round(t["avg_first_innings"], 1),
        )
        for t in repo.season_trends(db)
    ]
    return TeamsOverview(
        seasons=repo.seasons(db),
        franchises=[_summary(r) for r in franchises.values()],
        champions=champions,
        league=LeagueTrends(
            chasing=_rate(rates["chasing_won"], rates["decided"]),
            toss=_rate(rates["toss_won"], rates["tosses"]),
            home=_rate(rates["home_won"], rates["home_games"]),
            close=_rate(rates["close"], rates["decided"]),
            seasons=trends,
        ),
    )


def get_standings(db: Database, season: int) -> Standings:
    _require_tables(db)
    rows = repo.standings(db, season)
    if not rows:
        raise SeasonNotFoundError(str(season))
    return Standings(
        season=season,
        rows=[
            StandingRow(
                position=r["position"],
                team=TeamTag(franchise_id=r["franchise_id"], name=r["name"], color=r["color"]),
                team_name=r["team_name"],
                played=r["played"],
                won=r["won"],
                lost=r["lost"],
                no_result=r["no_result"] + r["abandoned"],
                points=r["points"],
                nrr=None if r["nrr"] is None else float(r["nrr"]),
                finish=r["finish"],
                exit_stage=r["exit_stage"],
            )
            for r in rows
        ],
        playoffs=[summary_from_row(r) for r in repo.playoff_summaries(db, season)],
        abandoned=sum(r["abandoned"] for r in rows) // 2,
    )


# --------------------------------------------------------------------------- team profile


def _phase_order(db: Database) -> list[tuple[str, str]]:
    phases = default_phase_config().for_format(db.match_format).phases
    return [(p.key, p.label) for p in sorted(phases, key=lambda p: p.first_over)]


def _phase_line(r: Row | None) -> PhaseLine:
    if r is None:
        return PhaseLine(
            balls=0,
            runs=0,
            wickets=0,
            run_rate=None,
            par_run_rate=None,
            balls_per_wicket=None,
            par_balls_per_wicket=None,
            boundary_pct=None,
            par_boundary_pct=None,
            dot_pct=None,
            par_dot_pct=None,
        )
    return PhaseLine(
        balls=r["balls"],
        runs=r["runs"],
        wickets=r["wickets"],
        run_rate=_ratio(r["runs"], r["balls"], 6),
        par_run_rate=_ratio(r["par_runs"], r["balls"], 6),
        balls_per_wicket=_ratio(r["balls"], r["wickets"], 1, 1),
        par_balls_per_wicket=_ratio(r["balls"], r["par_wickets"], 1, 1),
        boundary_pct=_ratio(r["boundaries"], r["balls"], 100, 1),
        par_boundary_pct=_ratio(r["par_boundaries"], r["balls"], 100, 1),
        dot_pct=_ratio(r["dots"], r["balls"], 100, 1),
        par_dot_pct=_ratio(r["par_dots"], r["balls"], 100, 1),
    )


def _total(franchises: dict[str, Row], r: Row | None) -> TeamTotal | None:
    if r is None:
        return None
    return TeamTotal(
        match_id=r["match_id"],
        season=r["season"],
        date=r["match_date"],
        opponent=_tag(franchises, r["opponent_id"]),
        runs=r["runs"],
        wickets=r["wickets"],
        overs=overs_notation(r["balls"]),
    )


def _margin(franchises: dict[str, Row], r: Row | None) -> TeamMargin | None:
    if r is None:
        return None
    return TeamMargin(
        match_id=r["match_id"],
        season=r["season"],
        date=r["match_date"],
        opponent=_tag(franchises, r["opponent_id"]),
        result_text=r["result_text"],
    )


def situation(r: Row) -> str:
    """The score at a ball, e.g. 'CSK 45/4 after 9.2 overs, needing 120 from 64'."""
    overs = overs_notation(r["legal_ball_no"] or 0)
    text = f"{r['batting_id']} {r['team_runs']}/{r['team_wickets']} after {overs} overs"
    if r["innings_no"] == 2 and r["target_runs"] is not None and r["target_balls"] is not None:
        need = r["target_runs"] - r["team_runs"]
        left = r["target_balls"] - (r["legal_ball_no"] or 0)
        if need > 0 and left > 0:
            text += f", needing {need} from {left}"
    return text


def _swings(
    db: Database, franchises: dict[str, Row], fid: str, w: SeasonWindow, *, comebacks: bool
) -> list[Swing]:
    return [
        Swing(
            match_id=r["match_id"],
            season=r["season"],
            date=r["match_date"],
            opponent=_tag(franchises, r["opponent_id"]),
            result_text=r["result_text"],
            win_probability=round(float(r["wp"]), 4),
            innings_no=r["innings_no"],
            seq_no=r["seq_no"],
            situation=situation(r),
        )
        for r in repo.swings(db, fid, w.first, w.last, comebacks=comebacks)
    ]


def get_profile(
    db: Database, franchise_id: str, first: int | None = None, last: int | None = None
) -> TeamProfile:
    _require_tables(db)
    fid = _franchise_id(db, franchise_id)
    franchises = _franchise_rows(db)
    team = franchises[fid]
    w = resolve_window(db, first, last)
    # A window outside the franchise's seasons is clipped to them.
    w = SeasonWindow(
        first=max(w.first, team["first_season"]), last=min(w.last, team["last_season"])
    )
    if w.first > w.last:
        w = SeasonWindow(first=team["first_season"], last=team["last_season"])

    splits = {(r["grp"], r["key"]): r for r in repo.record_splits(db, fid, w.first, w.last)}
    groups = [
        RecordGroup(
            key=group,
            label=label,
            splits=[
                RecordSplit(key=key, label=name, record=_record(splits[(group, key)]))
                for key, name in options
                if (group, key) in splits
            ],
        )
        for group, label, options in SPLIT_GROUPS
    ]
    phase_rows = {(r["role"], r["phase"]): r for r in repo.phases(db, fid, w.first, w.last)}
    phases = [
        TeamPhase(
            phase=key,
            label=label,
            batting=_phase_line(phase_rows.get(("batting", key))),
            bowling=_phase_line(phase_rows.get(("bowling", key))),
        )
        for key, label in _phase_order(db)
        if ("batting", key) in phase_rows or ("bowling", key) in phase_rows
    ]
    firsts = repo.first_innings(db, fid, w.first, w.last)
    scoring = TeamScoring(
        avg_first_innings=None if firsts["avg_runs"] is None else round(firsts["avg_runs"], 1),
        first_innings=firsts["innings"],
        highest=_total(franchises, repo.extreme_total(db, fid, w.first, w.last, highest=True)),
        lowest=_total(franchises, repo.extreme_total(db, fid, w.first, w.last, highest=False)),
        biggest_win_runs=_margin(franchises, repo.biggest_win(db, fid, w.first, w.last, by="runs")),
        biggest_win_wickets=_margin(
            franchises, repo.biggest_win(db, fid, w.first, w.last, by="wickets")
        ),
    )
    return TeamProfile(
        team=_summary(team),
        window=w,
        seasons=[TeamSeason(**_season_fields(r)) for r in repo.team_seasons(db, fid)],
        record=_record(repo.record(db, fid, w.first, w.last)),
        splits=[g for g in groups if g.splits],
        close=_record(splits.get(("close", "close"))),
        phases=phases,
        scoring=scoring,
        batters=[
            TeamBatter(
                player_id=r["player_id"],
                name=r["name"],
                innings=r["innings"],
                runs=r["runs"],
                balls=r["balls"],
                strike_rate=_ratio(r["runs"], r["balls"], 100),
                average=_ratio(r["runs"], r["outs"]),
            )
            for r in repo.top_batters(db, fid, w.first, w.last)
        ],
        bowlers=[
            TeamBowler(
                player_id=r["player_id"],
                name=r["name"],
                innings=r["innings"],
                wickets=r["wickets"],
                balls=r["balls"],
                economy=_ratio(r["runs"], r["balls"], 6),
                average=_ratio(r["runs"], r["wickets"]),
            )
            for r in repo.top_bowlers(db, fid, w.first, w.last)
        ],
        opponents=[
            OpponentRecord(opponent=_tag(franchises, r["opponent_id"]), record=_record(r))
            for r in repo.opponents(db, fid, w.first, w.last)
        ],
        venues=[
            VenueRecord(venue_id=r["venue_id"], name=r["name"], city=r["city"], record=_record(r))
            for r in repo.venues(db, fid, w.first, w.last)
        ],
        comebacks=_swings(db, franchises, fid, w, comebacks=True),
        collapses=_swings(db, franchises, fid, w, comebacks=False),
    )


def _season_fields(r: Row) -> dict[str, Any]:
    return {
        "season": r["season"],
        "team_name": r["team_name"],
        "position": r["position"],
        "teams": r["teams"],
        "played": r["played"],
        "won": r["won"],
        "lost": r["lost"],
        "no_result": r["no_result"] + r["abandoned"],
        "drawn": r.get("drawn") or 0,
        "points": r["points"],
        # A Test has no net run rate.
        "nrr": None if r["nrr"] is None or r.get("drawn") is not None else float(r["nrr"]),
        "finish": r["finish"],
        "exit_stage": r["exit_stage"],
        "playoff_won": r["playoff_won"],
        "playoff_lost": r["playoff_lost"],
    }


# --------------------------------------------------------------------------- head to head


def _h2h(rows: list[Row]) -> H2HRecord:
    return H2HRecord(
        played=len(rows),
        a_won=sum(1 for r in rows if r["result"] == "won"),
        b_won=sum(1 for r in rows if r["result"] == "lost"),
        no_result=sum(1 for r in rows if r["result"] == "no_result"),
        drawn=sum(1 for r in rows if r["result"] == "drawn"),
        tied=sum(1 for r in rows if r["tied"]),
    )


def expectation(rows: list[Row]) -> H2HExpectation | None:
    """A's expected wins in these meetings from each side's form going into them (log5).

    Form counts only matches before each meeting (criciq_core.teams), so the record
    cannot explain itself.
    """
    decided = [r for r in rows if r["result"] != "no_result"]
    if not decided:
        return None
    probs = [
        log5(
            form_probability(r["form_won"], r["form_decided"]),
            form_probability(r["opponent_form_won"], r["opponent_form_decided"]),
        )
        for r in decided
    ]
    expected = sum(probs)
    spread = Z90 * math.sqrt(sum(p * (1 - p) for p in probs))
    return H2HExpectation(
        decided=len(decided),
        a_won=sum(1 for r in decided if r["result"] == "won"),
        a_expected=round(expected, 1),
        low=round(max(expected - spread, 0.0), 1),
        high=round(min(expected + spread, float(len(decided))), 1),
        seasons_used=len({r["season"] for r in decided}),
    )


def _avg_first_innings(rows: list[Row], *, side_a: bool) -> float | None:
    totals = [
        r["runs_for"] if side_a else r["runs_against"]
        for r in rows
        if r["batted_first"] is side_a
        and r["win_method"] is None
        and (r["runs_for"] if side_a else r["runs_against"]) is not None
    ]
    return round(sum(totals) / len(totals), 1) if totals else None


def _highest(
    franchises: dict[str, Row], rows: list[Row], *, side_a: bool, opponent: str
) -> TeamTotal | None:
    key = "runs_for" if side_a else "runs_against"
    scored = [r for r in rows if r[key] is not None]
    if not scored:
        return None
    best = max(scored, key=lambda r: (r[key], -r["match_order"]))
    return TeamTotal(
        match_id=best["match_id"],
        season=best["season"],
        date=best["match_date"],
        opponent=_tag(franchises, opponent),
        runs=best[key],
        wickets=best["wickets_for" if side_a else "wickets_against"],
        overs=overs_notation(best["balls_for" if side_a else "balls_against"]),
    )


def _h2h_players(
    db: Database, franchises: dict[str, Row], side: str, other: str, w: SeasonWindow
) -> tuple[list[H2HPlayer], list[H2HPlayer]]:
    team = _tag(franchises, side)
    batters = [
        H2HPlayer(
            player_id=r["player_id"],
            name=r["name"],
            team=team,
            innings=r["innings"],
            runs=r["runs"],
            balls=r["balls"],
            strike_rate=_ratio(r["runs"], r["balls"], 100),
        )
        for r in repo.top_batters(db, side, w.first, w.last, opponent=other, limit=3)
    ]
    bowlers = [
        H2HPlayer(
            player_id=r["player_id"],
            name=r["name"],
            team=team,
            innings=r["innings"],
            wickets=r["wickets"],
            balls=r["balls"],
            economy=_ratio(r["runs"], r["balls"], 6),
        )
        for r in repo.top_bowlers(db, side, w.first, w.last, opponent=other, limit=3)
    ]
    return batters, bowlers


def get_head_to_head(
    db: Database, a: str, b: str, first: int | None = None, last: int | None = None
) -> TeamHeadToHead:
    _require_tables(db)
    a, b = _franchise_id(db, a), _franchise_id(db, b)
    if a == b:
        raise SameTeamError("choose two different teams")
    franchises = _franchise_rows(db)
    w = resolve_window(db, first, last)
    rows = repo.meetings(db, a, b, w.first, w.last)

    def subset(label: str, key: str, keep: list[Row]) -> H2HSplit:
        return H2HSplit(key=key, label=label, record=_h2h(keep))

    candidates = [
        subset(f"At {a}'s home", "a_home", [r for r in rows if r["venue_type"] == "home"]),
        subset(f"At {b}'s home", "b_home", [r for r in rows if r["venue_type"] == "away"]),
        subset("Neutral grounds", "neutral", [r for r in rows if r["venue_type"] == "neutral"]),
        subset(f"{a} batting first", "a_first", [r for r in rows if r["batted_first"] is True]),
        subset(f"{b} batting first", "b_first", [r for r in rows if r["batted_first"] is False]),
        subset("Playoffs", "playoffs", [r for r in rows if r["is_playoff"]]),
        subset("Close finishes", "close", [r for r in rows if r["is_close"]]),
    ]
    by_season: dict[int, list[Row]] = {}
    for r in rows:
        by_season.setdefault(r["season"], []).append(r)
    a_bat, a_bowl = _h2h_players(db, franchises, a, b, w)
    b_bat, b_bowl = _h2h_players(db, franchises, b, a, w)
    return TeamHeadToHead(
        a=_tag(franchises, a),
        b=_tag(franchises, b),
        window=w,
        record=_h2h(rows),
        expectation=expectation(rows),
        splits=[s for s in candidates if s.record.played],
        seasons=[H2HSeason(season=s, record=_h2h(rs)) for s, rs in sorted(by_season.items())],
        scoring=H2HScoring(
            a_avg_total=_avg_first_innings(rows, side_a=True),
            b_avg_total=_avg_first_innings(rows, side_a=False),
            a_highest=_highest(franchises, rows, side_a=True, opponent=b),
            b_highest=_highest(franchises, rows, side_a=False, opponent=a),
        ),
        batters=a_bat + b_bat,
        bowlers=a_bowl + b_bowl,
        meetings=[summary_from_row(r) for r in repo.summaries(db, [r["match_id"] for r in rows])],
    )
