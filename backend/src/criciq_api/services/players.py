"""Assemble Player Lab responses: directory, profiles, percentiles and splits."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import players as repo
from criciq_api.schemas.players import (
    BattingInnings,
    BattingSplitGroup,
    BattingSplitRow,
    BattingSummary,
    BestFigures,
    BowlingInnings,
    BowlingSplitGroup,
    BowlingSplitRow,
    BowlingSummary,
    DismissalCount,
    Dismissals,
    FieldingSummary,
    HighScore,
    Percentile,
    PercentileGroup,
    Percentiles,
    PhaseBatting,
    PhaseBowling,
    PhaseSplits,
    PlayerBio,
    PlayerListItem,
    PlayerPage,
    PlayerProfile,
    PlayerSplits,
    RecentInnings,
    SeasonBatting,
    SeasonBowling,
    SeasonLine,
    SeasonWindow,
    TeamStint,
    TeamTag,
)
from criciq_core.cricket import overs_notation
from criciq_core.phases import default_phase_config

RECENT_INNINGS = 20
# Minimum balls in the window to be ranked: overall, and within a phase.
MIN_BALLS = 300
MIN_PHASE_BALLS = 120


class PlayerNotFoundError(LookupError):
    pass


class InvalidWindowError(ValueError):
    pass


# --------------------------------------------------------------------------- rates


def _ratio(
    num: float | None, den: float | None, scale: float = 1.0, digits: int = 2
) -> float | None:
    if num is None or not den:
        return None
    return round(scale * num / den, digits)


def _strike_rate(runs: float | None, balls: float | None) -> float | None:
    return _ratio(runs, balls, 100)


def _economy(runs: float | None, balls: float | None) -> float | None:
    return _ratio(runs, balls, 6)


def _pct(count: float | None, balls: float | None) -> float | None:
    return _ratio(count, balls, 100, 1)


def search_tokens(q: str | None) -> tuple[str, ...]:
    """Lower-case, accent-free search tokens (matching ``player_index.search_key``)."""
    if not q:
        return ()
    plain = unicodedata.normalize("NFKD", q).encode("ascii", "ignore").decode().lower()
    return tuple(t for t in plain.replace(".", " ").split() if t)


def resolve_window(db: Database, first: int | None, last: int | None) -> SeasonWindow:
    low, high = repo.season_bounds(db)
    first = low if first is None else max(first, low)
    last = high if last is None else min(last, high)
    if first > last:
        raise InvalidWindowError(f"season window {first}-{last} is empty")
    return SeasonWindow(first=first, last=last)


def _tag(franchises: dict[str, Row], franchise_id: str) -> TeamTag:
    f = franchises[franchise_id]
    return TeamTag(franchise_id=franchise_id, name=f["name"], color=f["color"])


# --------------------------------------------------------------------------- directory


def list_players(
    db: Database, filters: repo.PlayerFilters, page: int, page_size: int
) -> PlayerPage:
    rows, total = repo.list_players(db, filters, limit=page_size, offset=(page - 1) * page_size)
    items = [
        PlayerListItem(
            player_id=r["player_id"],
            name=r["name"],
            full_name=r["full_name"],
            country=r["country"],
            role=r["role"],
            is_keeper=r["is_keeper"],
            team=TeamTag(franchise_id=r["team_id"], name=r["team_name"], color=r["team_color"])
            if r["team_id"]
            else None,
            first_season=r["first_season"],
            last_season=r["last_season"],
            matches=r["matches"],
            runs=r["runs"],
            batting_average=_ratio(r["runs"], r["outs"]),
            strike_rate=_strike_rate(r["runs"], r["bat_balls"]),
            wickets=r["wickets"],
            economy=_economy(r["conceded"], r["bowl_balls"]),
        )
        for r in rows
    ]
    return PlayerPage(items=items, total=total, page=page, page_size=page_size)


# --------------------------------------------------------------------------- profile


def _bio(db: Database, row: Row) -> PlayerBio:
    teams = [TeamStint(**t) for t in repo.get_teams(db, row["player_id"])]
    return PlayerBio(
        player_id=row["player_id"],
        name=row["name"],
        full_name=row["full_name"],
        country=row["country"],
        date_of_birth=row["date_of_birth"],
        batting_hand=row["batting_hand"],
        bowling_arm=row["bowling_arm"],
        bowling_type=row["bowling_type"],
        bowling_style=row["bowling_style"],
        role=row["role"],
        is_keeper=row["is_keeper"],
        first_season=row["first_season"],
        last_season=row["last_season"],
        matches=row["matches"],
        teams=teams,
    )


def _batting(db: Database, player_id: str, w: SeasonWindow) -> BattingSummary | None:
    r = repo.batting_summary(db, player_id, w.first, w.last)
    if r is None:
        return None
    hs = repo.highest_score(db, player_id, w.first, w.last)
    return BattingSummary(
        matches=r["matches"],
        innings=r["innings"],
        not_outs=r["innings"] - r["outs"],
        runs=r["runs"],
        balls=r["balls"],
        outs=r["outs"],
        average=_ratio(r["runs"], r["outs"]),
        strike_rate=_strike_rate(r["runs"], r["balls"]),
        highest=HighScore(**hs) if hs else None,
        fifties=r["fifties"],
        hundreds=r["hundreds"],
        ducks=r["ducks"],
        fours=r["fours"],
        sixes=r["sixes"],
        dot_pct=_pct(r["dots"], r["balls"]),
        boundary_pct=_pct(r["fours"] + r["sixes"], r["balls"]),
        par_strike_rate=_strike_rate(r["par_runs"], r["balls"]),
        par_average=_ratio(r["par_runs"], r["par_outs"]),
        par_dot_pct=_pct(r["par_dots"], r["balls"]),
        par_boundary_pct=_pct(r["par_boundaries"], r["balls"]),
        runs_above_par=round(r["runs"] - r["par_runs"], 1),
        wpa=None if r["wpa"] is None else round(r["wpa"], 3),
        wpa_innings=r["wpa_innings"],
    )


def _bowling(db: Database, player_id: str, w: SeasonWindow) -> BowlingSummary | None:
    r = repo.bowling_summary(db, player_id, w.first, w.last)
    if r is None:
        return None
    best = repo.best_figures(db, player_id, w.first, w.last)
    return BowlingSummary(
        matches=r["matches"],
        innings=r["innings"],
        balls=r["balls"],
        overs=overs_notation(r["balls"]),
        runs=r["runs"],
        wickets=r["wickets"],
        average=_ratio(r["runs"], r["wickets"]),
        economy=_economy(r["runs"], r["balls"]),
        strike_rate=_ratio(r["balls"], r["wickets"]),
        best=BestFigures(**best) if best else None,
        four_wickets=r["four_wickets"],
        five_wickets=r["five_wickets"],
        maidens=r["maidens"],
        dot_pct=_pct(r["dots"], r["balls"]),
        boundary_pct=_pct(r["fours"] + r["sixes"], r["balls"]),
        wides=r["wides"],
        noballs=r["noballs"],
        par_economy=_economy(r["par_runs"], r["balls"]),
        par_strike_rate=_ratio(r["balls"], r["par_wickets"]),
        par_dot_pct=_pct(r["par_dots"], r["balls"]),
        runs_saved=round(r["par_runs"] - r["runs"], 1),
        wpa=None if r["wpa"] is None else round(r["wpa"], 3),
        wpa_innings=r["wpa_innings"],
    )


def _seasons(db: Database, player_id: str, w: SeasonWindow) -> list[SeasonLine]:
    lines = []
    for r in repo.season_lines(db, player_id, w.first, w.last):
        batting = (
            SeasonBatting(
                innings=r["bat_innings"],
                runs=r["bat_runs"],
                balls=r["bat_balls"],
                outs=r["bat_outs"],
                average=_ratio(r["bat_runs"], r["bat_outs"]),
                strike_rate=_strike_rate(r["bat_runs"], r["bat_balls"]),
                par_strike_rate=_strike_rate(r["bat_par_runs"], r["bat_balls"]),
                highest=r["highest"],
                fifties=r["fifties"],
                hundreds=r["hundreds"],
            )
            if r["bat_innings"]
            else None
        )
        bowling = (
            SeasonBowling(
                innings=r["bowl_innings"],
                balls=r["bowl_balls"],
                runs=r["bowl_runs"],
                wickets=r["wickets"],
                average=_ratio(r["bowl_runs"], r["wickets"]),
                economy=_economy(r["bowl_runs"], r["bowl_balls"]),
                par_economy=_economy(r["bowl_par_runs"], r["bowl_balls"]),
                strike_rate=_ratio(r["bowl_balls"], r["wickets"]),
            )
            if r["bowl_innings"]
            else None
        )
        lines.append(
            SeasonLine(
                season=r["season"],
                teams=r["teams"],
                matches=r["matches"],
                batting=batting,
                bowling=bowling,
            )
        )
    return lines


def _phase_order() -> list[tuple[str, str]]:
    phases = default_phase_config().for_format("T20").phases
    return [(p.key, p.label) for p in sorted(phases, key=lambda p: p.first_over)]


def _phases(db: Database, player_id: str, w: SeasonWindow) -> PhaseSplits:
    bat = {r["key"]: r for r in repo.batting_cells(db, player_id, w.first, w.last, "phase")}
    bowl = {r["key"]: r for r in repo.bowling_cells(db, player_id, w.first, w.last, "phase")}
    bat_total = sum(r["balls"] for r in bat.values())
    bowl_total = sum(r["balls"] for r in bowl.values())
    batting = [
        PhaseBatting(
            phase=key,
            label=label,
            balls=r["balls"],
            runs=r["runs"],
            outs=r["outs"],
            strike_rate=_strike_rate(r["runs"], r["balls"]),
            average=_ratio(r["runs"], r["outs"]),
            dot_pct=_pct(r["dots"], r["balls"]),
            boundary_pct=_pct(r["fours"] + r["sixes"], r["balls"]),
            par_strike_rate=_strike_rate(r["par_runs"], r["balls"]),
            par_dot_pct=_pct(r["par_dots"], r["balls"]),
            par_boundary_pct=_pct(r["par_boundaries"], r["balls"]),
            share=round(r["balls"] / bat_total, 4) if bat_total else 0.0,
        )
        for key, label in _phase_order()
        if (r := bat.get(key)) is not None and (r["balls"] or r["outs"])
    ]
    bowling = [
        PhaseBowling(
            phase=key,
            label=label,
            balls=r["balls"],
            runs=r["runs"],
            wickets=r["wickets"],
            economy=_economy(r["runs"], r["balls"]),
            average=_ratio(r["runs"], r["wickets"]),
            strike_rate=_ratio(r["balls"], r["wickets"]),
            dot_pct=_pct(r["dots"], r["balls"]),
            par_economy=_economy(r["par_runs"], r["balls"]),
            par_dot_pct=_pct(r["par_dots"], r["balls"]),
            share=round(r["balls"] / bowl_total, 4) if bowl_total else 0.0,
        )
        for key, label in _phase_order()
        if (r := bowl.get(key)) is not None and r["balls"]
    ]
    return PhaseSplits(batting=batting, bowling=bowling)


# --------------------------------------------------------------------------- percentiles

Metric = Callable[[Row], float | None]


def _rank(value: float, population: list[float], higher_is_better: bool) -> int:
    """Share of the population this value beats (ties count half), 0-100."""
    worse = sum(1 for v in population if (v < value if higher_is_better else v > value))
    ties = sum(1 for v in population if v == value) - 1
    return round(100 * (worse + 0.5 * max(ties, 0)) / max(len(population) - 1, 1))


def _group(
    rows: list[Row],
    player_id: str,
    specs: list[tuple[str, str, str, str, bool, str, Metric]],
) -> PercentileGroup | None:
    """Rank one player on each metric among players qualified for it.

    Each spec is (key, label, description, unit, higher_is_better, balls column, metric).
    """
    by_id = {r["player_id"]: r for r in rows}
    me = by_id.get(player_id)
    if me is None or not me["balls"]:
        return None
    items = []
    population_overall = sum(1 for r in rows if r["balls"] >= MIN_BALLS)
    for key, label, description, unit, higher, balls_key, metric in specs:
        minimum = MIN_BALLS if balls_key == "balls" else MIN_PHASE_BALLS
        qualified = [
            v
            for r in rows
            if r[balls_key] >= minimum and r["balls"] >= MIN_BALLS and (v := metric(r)) is not None
        ]
        value = metric(me)
        mine_qualified = me[balls_key] >= minimum and me["balls"] >= MIN_BALLS
        items.append(
            Percentile(
                key=key,
                label=label,
                description=description,
                value=None if value is None else round(value, 2),
                unit=unit,  # type: ignore[arg-type]
                higher_is_better=higher,
                percentile=_rank(value, qualified, higher)
                if mine_qualified and value is not None
                else None,
                balls=int(me[balls_key]),
                min_balls=minimum,
                population=len(qualified),
            )
        )
    return PercentileGroup(
        qualified=me["balls"] >= MIN_BALLS,
        balls=int(me["balls"]),
        min_balls=MIN_BALLS,
        population=population_overall,
        items=items,
    )


def _with_wpa(rows: list[Row], wpa: dict[str, tuple[float, int]]) -> list[Row]:
    out = []
    for r in rows:
        total, innings = wpa.get(r["player_id"], (0.0, 0))
        out.append({**r, "wpa_per_innings": total / innings if innings else None})
    return out


def _per_100(above: float, balls: float) -> float | None:
    return 100 * above / balls if balls else None


def _batting_percentiles(db: Database, player_id: str, w: SeasonWindow) -> PercentileGroup | None:
    rows = _with_wpa(
        repo.batting_population(db, w.first, w.last),
        repo.wpa_population(db, "batting", w.first, w.last),
    )
    specs: list[tuple[str, str, str, str, bool, str, Metric]] = [
        (
            "strike_rate",
            "Strike rate vs par",
            "Runs per 100 balls above an average batter facing the same balls.",
            "runs_per_100",
            True,
            "balls",
            lambda r: _per_100(r["runs"] - r["par_runs"], r["balls"]),
        ),
        (
            "average",
            "Average vs par",
            "Runs per dismissal compared with par, as a percentage.",
            "percent",
            True,
            "balls",
            lambda r: (
                100 * ((r["runs"] / max(r["outs"], 1)) / (r["par_runs"] / r["par_outs"]) - 1)
                if r["par_outs"]
                else None
            ),
        ),
        (
            "boundaries",
            "Boundary rate vs par",
            "Fours and sixes per 100 balls above par.",
            "points",
            True,
            "balls",
            lambda r: _per_100(r["boundaries"] - r["par_boundaries"], r["balls"]),
        ),
        (
            "dots",
            "Dot balls vs par",
            "Dot balls per 100 balls relative to par. Fewer is better.",
            "points",
            False,
            "balls",
            lambda r: _per_100(r["dots"] - r["par_dots"], r["balls"]),
        ),
        (
            "powerplay",
            "Powerplay strike rate vs par",
            "Strike rate above par in overs 1-6.",
            "runs_per_100",
            True,
            "pp_balls",
            lambda r: _per_100(r["pp_above"], r["pp_balls"]),
        ),
        (
            "death",
            "Death-overs strike rate vs par",
            "Strike rate above par in overs 16-20.",
            "runs_per_100",
            True,
            "death_balls",
            lambda r: _per_100(r["death_above"], r["death_balls"]),
        ),
    ]
    if db.has_table("player_wpa"):
        specs.append(
            (
                "wpa",
                "Win probability added per innings",
                "Average change in the team's chance of winning while batting, in points.",
                "points",
                True,
                "balls",
                lambda r: None if r["wpa_per_innings"] is None else 100 * r["wpa_per_innings"],
            )
        )
    return _group(rows, player_id, specs)


def _bowling_percentiles(db: Database, player_id: str, w: SeasonWindow) -> PercentileGroup | None:
    rows = _with_wpa(
        repo.bowling_population(db, w.first, w.last),
        repo.wpa_population(db, "bowling", w.first, w.last),
    )
    specs: list[tuple[str, str, str, str, bool, str, Metric]] = [
        (
            "economy",
            "Economy vs par",
            "Runs per over conceded relative to an average bowler bowling the same balls. "
            "Lower is better.",
            "runs_per_over",
            False,
            "balls",
            lambda r: 6 * (r["runs"] - r["par_runs"]) / r["balls"] if r["balls"] else None,
        ),
        (
            "wickets",
            "Wicket rate vs par",
            "Wickets per ball compared with par, as a percentage.",
            "percent",
            True,
            "balls",
            lambda r: 100 * (r["wickets"] / r["par_wickets"] - 1) if r["par_wickets"] else None,
        ),
        (
            "dots",
            "Dot balls vs par",
            "Dot balls per 100 balls above par.",
            "points",
            True,
            "balls",
            lambda r: _per_100(r["dots"] - r["par_dots"], r["balls"]),
        ),
        (
            "boundaries",
            "Boundaries conceded vs par",
            "Fours and sixes conceded per 100 balls relative to par. Fewer is better.",
            "points",
            False,
            "balls",
            lambda r: _per_100(r["boundaries"] - r["par_boundaries"], r["balls"]),
        ),
        (
            "powerplay",
            "Powerplay economy vs par",
            "Economy relative to par in overs 1-6. Lower is better.",
            "runs_per_over",
            False,
            "pp_balls",
            lambda r: 6 * r["pp_above"] / r["pp_balls"] if r["pp_balls"] else None,
        ),
        (
            "death",
            "Death-overs economy vs par",
            "Economy relative to par in overs 16-20. Lower is better.",
            "runs_per_over",
            False,
            "death_balls",
            lambda r: 6 * r["death_above"] / r["death_balls"] if r["death_balls"] else None,
        ),
    ]
    if db.has_table("player_wpa"):
        specs.append(
            (
                "wpa",
                "Win probability added per innings",
                "Average change in the team's chance of winning while bowling, in points.",
                "points",
                True,
                "balls",
                lambda r: None if r["wpa_per_innings"] is None else 100 * r["wpa_per_innings"],
            )
        )
    return _group(rows, player_id, specs)


# --------------------------------------------------------------------------- recent form


def _recent(db: Database, player_id: str, w: SeasonWindow) -> RecentInnings:
    franchises = repo.franchise_tags(db)
    venues = repo.venue_names(db)
    batting = [
        BattingInnings(
            match_id=r["match_id"],
            season=r["season"],
            date=r["match_date"],
            opposition=_tag(franchises, r["opposition_id"]),
            venue=venues[r["venue_id"]]["name"],
            position=r["position"],
            runs=r["runs"],
            balls=r["balls"],
            fours=r["fours"],
            sixes=r["sixes"],
            is_out=r["is_out"],
            dismissal=r["dismissal"],
            result=r["result"],
            wpa=None if r["wpa"] is None else round(r["wpa"], 4),
        )
        for r in repo.recent_batting(db, player_id, w.first, w.last, RECENT_INNINGS)
    ]
    bowling = [
        BowlingInnings(
            match_id=r["match_id"],
            season=r["season"],
            date=r["match_date"],
            opposition=_tag(franchises, r["opposition_id"]),
            venue=venues[r["venue_id"]]["name"],
            balls=r["balls"],
            overs=overs_notation(r["balls"]),
            runs=r["runs"],
            wickets=r["wickets"],
            economy=_economy(r["runs"], r["balls"]),
            result=r["result"],
            wpa=None if r["wpa"] is None else round(r["wpa"], 4),
        )
        for r in repo.recent_bowling(db, player_id, w.first, w.last, RECENT_INNINGS)
    ]
    return RecentInnings(batting=batting, bowling=bowling)


def get_profile(
    db: Database, player_id: str, first: int | None = None, last: int | None = None
) -> PlayerProfile:
    row = repo.get_player(db, player_id)
    if row is None:
        raise PlayerNotFoundError(player_id)
    w = resolve_window(db, first, last)
    return PlayerProfile(
        player=_bio(db, row),
        window=w,
        batting=_batting(db, player_id, w),
        bowling=_bowling(db, player_id, w),
        fielding=FieldingSummary(**repo.fielding(db, player_id, w.first, w.last)),
        seasons=_seasons(db, player_id, w),
        phases=_phases(db, player_id, w),
        percentiles=Percentiles(
            batting=_batting_percentiles(db, player_id, w),
            bowling=_bowling_percentiles(db, player_id, w),
        ),
        recent=_recent(db, player_id, w),
        dismissals=Dismissals(
            batting=[
                DismissalCount(**r) for r in repo.batting_dismissals(db, player_id, w.first, w.last)
            ],
            bowling=[
                DismissalCount(**r) for r in repo.bowling_dismissals(db, player_id, w.first, w.last)
            ],
        ),
    )


# --------------------------------------------------------------------------- splits

POSITION_LABELS = {
    "1-2": "Opening (1\u20132)",
    "3": "No. 3",
    "4-5": "No. 4\u20135",
    "6-7": "No. 6\u20137",
    "8-11": "No. 8\u201311",
}
RESULT_LABELS = {"won": "In wins", "lost": "In defeats", "no_result": "No result"}
STAGE_LABELS = {"league": "League", "playoffs": "Playoffs"}
BOWLING_TYPE_LABELS = {"pace": "vs pace", "spin": "vs spin", "unknown": "vs unknown type"}
HAND_LABELS = {
    "right": "vs right-handers",
    "left": "vs left-handers",
    "unknown": "vs unknown hand",
}
BATTING_GROUPS = [
    ("phase", "Phase"),
    ("bowling_type", "Bowler type"),
    ("position", "Batting position"),
    ("innings", "Innings"),
    ("result", "Result"),
    ("stage", "Stage"),
    ("opposition", "Opposition"),
    ("venue", "Venue"),
    ("season", "Season"),
]
BOWLING_GROUPS = [
    ("phase", "Phase"),
    ("batting_hand", "Batter hand"),
    ("innings", "Innings"),
    ("result", "Result"),
    ("stage", "Stage"),
    ("opposition", "Opposition"),
    ("venue", "Venue"),
    ("season", "Season"),
]


class _Labeler:
    """Label, colour and display order for split keys."""

    def __init__(self, db: Database) -> None:
        self.franchises = repo.franchise_tags(db)
        self.venues = repo.venue_names(db)
        self.phases = dict(_phase_order())

    def __call__(self, group: str, key: str, role: str) -> tuple[str, str | None]:
        if group == "phase":
            return self.phases.get(key, key), None
        if group == "bowling_type":
            return BOWLING_TYPE_LABELS.get(key, key), None
        if group == "batting_hand":
            return HAND_LABELS.get(key, key), None
        if group == "position":
            return POSITION_LABELS[key], None
        if group == "innings":
            if role == "batting":
                return ("Batting first" if key == "1" else "Chasing"), None
            return ("Bowling first" if key == "1" else "Defending a total"), None
        if group == "result":
            return RESULT_LABELS[key], None
        if group == "stage":
            return STAGE_LABELS[key], None
        if group == "opposition":
            f = self.franchises[key]
            return f"vs {f['name']}", f["color"]
        if group == "venue":
            v = self.venues[key]
            return f"{v['name']}, {v['city']}", None
        return key, None


def _order(group: str, rows: list[Row]) -> list[Row]:
    if group == "phase":
        order = {k: i for i, (k, _) in enumerate(_phase_order())}
        return sorted(rows, key=lambda r: order.get(r["key"], 99))
    if group in ("season", "innings"):
        return sorted(rows, key=lambda r: r["key"])
    if group == "position":
        return sorted(rows, key=lambda r: list(POSITION_LABELS).index(r["key"]))
    if group in ("result", "stage", "bowling_type", "batting_hand"):
        return sorted(rows, key=lambda r: (r["key"] == "unknown", -r["balls"]))
    return sorted(rows, key=lambda r: (-r["balls"], r["key"]))


def _batting_row(r: Row, label: str, color: str | None, innings_level: bool) -> BattingSplitRow:
    return BattingSplitRow(
        key=r["key"],
        label=label,
        color=color,
        innings=r["innings"] if innings_level else None,
        balls=r["balls"],
        runs=r["runs"],
        outs=r["outs"],
        average=_ratio(r["runs"], r["outs"]),
        strike_rate=_strike_rate(r["runs"], r["balls"]),
        par_strike_rate=_strike_rate(r["par_runs"], r["balls"]),
        dot_pct=_pct(r["dots"], r["balls"]),
        boundary_pct=_pct(r["fours"] + r["sixes"], r["balls"]),
        fifties=r["fifties"] if innings_level else None,
        highest=r["highest"] if innings_level else None,
    )


def _bowling_row(r: Row, label: str, color: str | None, innings_level: bool) -> BowlingSplitRow:
    return BowlingSplitRow(
        key=r["key"],
        label=label,
        color=color,
        innings=r["innings"] if innings_level else None,
        balls=r["balls"],
        runs=r["runs"],
        wickets=r["wickets"],
        economy=_economy(r["runs"], r["balls"]),
        average=_ratio(r["runs"], r["wickets"]),
        strike_rate=_ratio(r["balls"], r["wickets"]),
        par_economy=_economy(r["par_runs"], r["balls"]),
        dot_pct=_pct(r["dots"], r["balls"]),
    )


def get_splits(
    db: Database, player_id: str, first: int | None = None, last: int | None = None
) -> PlayerSplits:
    if repo.get_player(db, player_id) is None:
        raise PlayerNotFoundError(player_id)
    w = resolve_window(db, first, last)
    label = _Labeler(db)

    batting: list[BattingSplitGroup] = []
    for group, title in BATTING_GROUPS:
        cells = group in ("phase", "bowling_type")
        rows: list[Any] = (
            repo.batting_cells(db, player_id, w.first, w.last, group)  # type: ignore[arg-type]
            if cells
            else repo.batting_innings_split(
                db, player_id, w.first, w.last, repo.BATTING_DIMENSIONS[group]
            )
        )
        rows = [r for r in rows if r["balls"] or r["outs"]]
        if rows:
            batting.append(
                BattingSplitGroup(
                    key=group,
                    label=title,
                    rows=[
                        _batting_row(r, *label(group, r["key"], "batting"), not cells)
                        for r in _order(group, rows)
                    ],
                )
            )

    bowling: list[BowlingSplitGroup] = []
    for group, title in BOWLING_GROUPS:
        cells = group in ("phase", "batting_hand")
        rows = (
            repo.bowling_cells(db, player_id, w.first, w.last, group)  # type: ignore[arg-type]
            if cells
            else repo.bowling_innings_split(
                db, player_id, w.first, w.last, repo.BOWLING_DIMENSIONS[group]
            )
        )
        rows = [r for r in rows if r["balls"]]
        if rows:
            bowling.append(
                BowlingSplitGroup(
                    key=group,
                    label=title,
                    rows=[
                        _bowling_row(r, *label(group, r["key"], "bowling"), not cells)
                        for r in _order(group, rows)
                    ],
                )
            )
    return PlayerSplits(window=w, batting=batting, bowling=bowling)
