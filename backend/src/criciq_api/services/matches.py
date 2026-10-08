"""Assemble match summaries, scorecards and replay timelines."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import matches as repo
from criciq_api.schemas.matches import (
    BattingEntry,
    BowlingEntry,
    DayMarker,
    Extras,
    FallOfWicket,
    InningsScore,
    InningsScorecard,
    MatchDetail,
    MatchPage,
    MatchSummary,
    PlayerRef,
    ScoreProjectionModel,
    TeamRef,
    TeamScore,
    Timeline,
    TimelineDelivery,
    TimelineInnings,
    TimelinePlayer,
    TimelineSubstitution,
    TimelineWicket,
    Toss,
    VenueRef,
    WinProbabilityModel,
)
from criciq_core.cricket import overs_notation


class MatchNotFoundError(LookupError):
    pass


def summary_from_row(row: Row) -> MatchSummary:
    def side(prefix: str) -> TeamScore:
        # A Test's summary lists each side's innings; a limited-overs one has none.
        innings = row.get(f"{prefix}_innings")
        return TeamScore(
            team_season_id=row[f"{prefix}_id"],
            franchise_id=row[f"{prefix}_short"],
            name=row[f"{prefix}_name"],
            color=row[f"{prefix}_color"],
            runs=row[f"{prefix}_runs"],
            wickets=row[f"{prefix}_wickets"],
            overs=row[f"{prefix}_overs"],
            innings=None if innings is None else [InningsScore(**i) for i in innings],
        )

    return MatchSummary(
        match_id=row["match_id"],
        season=row["season"],
        date=row["match_date"],
        match_number=row["match_number"],
        stage=row["stage"],
        is_playoff=row["is_playoff"],
        venue=VenueRef(venue_id=row["venue_id"], name=row["venue_name"], city=row["venue_city"]),
        team_a=side("team_a"),
        team_b=side("team_b"),
        target_runs=row["target_runs"],
        outcome_type=row["outcome_type"],
        winner_id=row["winner_id"],
        result_text=row["result_text"],
        win_method=row["win_method"],
        decided_by_super_over=row["decided_by_super_over"],
        won_by_innings=row.get("won_by_innings"),
        toss=Toss(
            winner_id=row["toss_winner_id"],
            winner_name=row["toss_winner_name"],
            decision=row["toss_decision"],
        ),
        player_of_match=list(row["player_of_match"] or []),
    )


def list_matches(db: Database, filters: repo.MatchFilters, page: int, page_size: int) -> MatchPage:
    rows, total = repo.list_matches(db, filters, limit=page_size, offset=(page - 1) * page_size)
    return MatchPage(
        items=[summary_from_row(r) for r in rows], total=total, page=page, page_size=page_size
    )


def _summary(db: Database, match_id: int) -> MatchSummary:
    row = repo.get_summary(db, match_id)
    if row is None:
        raise MatchNotFoundError(match_id)
    return summary_from_row(row)


def _teams(db: Database, match_id: int) -> dict[str, TeamRef]:
    return {
        r["team_season_id"]: TeamRef(
            team_season_id=r["team_season_id"],
            franchise_id=r["franchise_id"],
            name=r["name"],
            color=r["color"],
        )
        for r in repo.get_team_refs(db, match_id)
    }


def _rate(numerator: float, denominator: float, scale: float) -> float | None:
    return round(numerator * scale / denominator, 2) if denominator else None


def dismissal_text(kind: str | None, bowler: str | None, fielders: list[str]) -> str | None:
    """Scorecard-style dismissal, e.g. 'c Dhoni b Bravo', 'run out (Jadeja)'."""
    if kind is None:
        return None
    fielder = fielders[0] if fielders else None
    match kind:
        case "caught":
            if fielder is not None and fielder == bowler:
                return f"c & b {bowler}"
            return f"c {fielder} b {bowler}" if fielder else f"c ? b {bowler}"
        case "caught and bowled":
            return f"c & b {bowler}"
        case "bowled":
            return f"b {bowler}"
        case "lbw":
            return f"lbw b {bowler}"
        case "stumped":
            return f"st {fielder} b {bowler}" if fielder else f"st b {bowler}"
        case "hit wicket":
            return f"hit wicket b {bowler}"
        case "run out":
            return f"run out ({' / '.join(fielders)})" if fielders else "run out"
        case _:
            return kind


def get_detail(db: Database, match_id: int) -> MatchDetail:
    summary = _summary(db, match_id)
    teams = _teams(db, match_id)
    names = {p["player_id"]: p["name"] for p in repo.get_match_people(db, match_id)}

    batting: dict[int, list[BattingEntry]] = defaultdict(list)
    appeared: dict[int, set[str]] = defaultdict(set)
    for r in repo.get_batting(db, match_id):
        fielders = [
            names.get(fid, fid) + (" (sub)" if sub else "")
            for fid, sub in zip(
                r["fielder_ids"] or [], r["fielder_is_substitute"] or [], strict=False
            )
        ]
        batting[r["innings_no"]].append(
            BattingEntry(
                player_id=r["player_id"],
                name=r["name"],
                runs=r["runs"],
                balls=r["balls"],
                fours=r["fours"],
                sixes=r["sixes"],
                strike_rate=_rate(r["runs"], r["balls"], 100),
                dismissal=dismissal_text(r["kind"], r["bowler_name"], fielders),
                is_out=r["is_out"],
            )
        )
        appeared[r["innings_no"]].add(r["player_id"])

    bowling: dict[int, list[BowlingEntry]] = defaultdict(list)
    for r in repo.get_bowling(db, match_id):
        bowling[r["innings_no"]].append(
            BowlingEntry(
                player_id=r["player_id"],
                name=r["name"],
                overs=overs_notation(r["legal_balls"]),
                maidens=r["maidens"],
                runs=r["runs"],
                wickets=r["wickets"],
                economy=_rate(r["runs"], r["legal_balls"], 6),
                wides=r["wides"],
                noballs=r["noballs"],
            )
        )

    falls: dict[int, list[FallOfWicket]] = defaultdict(list)
    for r in repo.get_fall_of_wickets(db, match_id):
        falls[r["innings_no"]].append(
            FallOfWicket(
                wicket=r["wicket"],
                runs=r["runs"],
                overs=overs_notation(r["legal_ball_no"]),
                player_id=r["player_id"],
                name=r["name"],
            )
        )

    squads: dict[str, list[Row]] = defaultdict(list)
    for r in repo.get_squads(db, match_id):
        squads[r["team_season_id"]].append(r)

    innings = []
    for r in repo.get_innings(db, match_id):
        number = r["innings_no"]
        extras = {k: int(r[k] or 0) for k in ("byes", "legbyes", "wides", "noballs", "penalty")}
        innings.append(
            InningsScorecard(
                innings_no=number,
                is_super_over=r["is_super_over"],
                batting_team=teams[r["batting_team_id"]],
                bowling_team=teams[r["bowling_team_id"]],
                runs=r["runs"],
                wickets=r["wickets"],
                overs=overs_notation(r["legal_balls"]),
                target_runs=r["target_runs"],
                target_overs=r["target_overs"],
                declared=bool(r.get("declared")),
                follow_on=bool(r.get("follow_on")),
                extras=Extras(**extras, total=sum(extras.values())),
                batting=batting[number],
                did_not_bat=(
                    []
                    if r["is_super_over"]
                    else [
                        PlayerRef(player_id=s["player_id"], name=s["name"])
                        for s in squads[r["batting_team_id"]]
                        if s["player_id"] not in appeared[number]
                    ]
                ),
                bowling=bowling[number],
                fall_of_wickets=falls[number],
            )
        )
    return MatchDetail(summary=summary, innings=innings)


def _wp_model(row: Row) -> WinProbabilityModel:
    """The win probability model, with the pressure bands in leverage units if scored."""
    scale = row.get("pressure")
    thresholds = (
        [round(scale["quantiles"][q] / scale["mean_swing"], 3) for q in (50, 80, 95)]
        if scale
        else None
    )
    fields = {k: v for k, v in row.items() if k != "pressure"}
    # A Test model has no explanations (and publishes its terms for the chase what-if).
    fields.setdefault("factor_keys", [])
    fields.setdefault("base_innings1", None)
    fields.setdefault("base_innings2", None)
    return WinProbabilityModel(**fields, pressure_thresholds=thresholds)


def day_markers(deliveries: list[Row], days: int) -> list[DayMarker]:
    """Where each day of a Test began, estimated: Cricsheet has the dates a Test was played
    on but not when each day's play started, so its legal balls are shared evenly between
    them (a day begins at the first delivery past the previous days' share)."""
    legal = sum(1 for d in deliveries if d["is_legal"])
    if days < 1 or legal == 0:
        return []
    per_day = legal / days
    markers = [DayMarker(day=1, innings_no=deliveries[0]["innings_no"], seq_no=0)]
    bowled = 0
    for d in deliveries:
        if len(markers) < days and bowled >= per_day * len(markers):
            markers.append(
                DayMarker(day=len(markers) + 1, innings_no=d["innings_no"], seq_no=d["seq_no"])
            )
        bowled += int(d["is_legal"])
    return markers


def get_timeline(db: Database, match_id: int) -> Timeline:
    summary = _summary(db, match_id)
    wp = {(r["innings_no"], r["seq_no"]): r for r in repo.get_win_probabilities(db, match_id)}
    model_row = repo.get_model(db, "win_probability") if wp else None
    # Tests project every innings; limited-overs matches only the first.
    test_projections = {
        (r["innings_no"], r["seq_no"]): list(r["quantiles"])
        for r in repo.get_innings_projections(db, match_id)
    }
    projections = {
        r["seq_no"]: list(r["quantiles"]) for r in repo.get_score_projections(db, match_id)
    }
    projection_row = (
        repo.get_model(db, "score_projection") if projections or test_projections else None
    )

    def projection(innings_no: int, seq_no: int) -> list[int] | None:
        if test_projections:
            return test_projections.get((innings_no, seq_no))
        return projections.get(seq_no) if innings_no == 1 else None

    def probability(row: Row | None) -> float | None:
        return None if row is None else float(row["wp_team_a"])

    def draw(row: Row | None) -> float | None:
        value = None if row is None else row.get("wp_draw")
        return None if value is None else float(value)

    def factors(row: Row | None) -> list[float] | None:
        return None if row is None or row["factors"] is None else list(row["factors"])

    def number(row: Row | None, key: str, digits: int) -> float | None:
        value = None if row is None else row.get(key)
        return None if value is None or value != value else round(float(value), digits)

    def index(row: Row | None) -> int | None:
        value = number(row, "pressure", 0)
        return None if value is None else int(value)

    rows = repo.get_deliveries(db, match_id)
    deliveries = []
    for r in rows:
        wicket: Any = None
        if r["player_out_id"] is not None:
            wicket = TimelineWicket(
                player_out_id=r["player_out_id"],
                kind=r["wicket_kind"],
                bowler_credited=r["bowler_credited"],
                is_dismissal=r["is_dismissal"],
                fielder_ids=list(r["fielder_ids"] or []),
            )
        deliveries.append(
            TimelineDelivery(
                innings_no=r["innings_no"],
                seq_no=r["seq_no"],
                over_no=r["over_no"],
                ball_label=r["ball_label"],
                legal_ball_no=r["legal_ball_no"],
                is_legal=r["is_legal"],
                batter_id=r["batter_id"],
                non_striker_id=r["non_striker_id"],
                bowler_id=r["bowler_id"],
                runs_batter=r["runs_batter"],
                runs_extras=r["runs_extras"],
                runs_total=r["runs_total"],
                wides=r["extras_wides"],
                noballs=r["extras_noballs"],
                byes=r["extras_byes"],
                legbyes=r["extras_legbyes"],
                penalty=r["extras_penalty"],
                is_four=r["is_four"],
                is_six=r["is_six"],
                team_runs=r["team_runs"],
                team_wickets=r["team_wickets"],
                wicket=wicket,
                wp=probability(p := wp.get((r["innings_no"], r["seq_no"]))),
                wp_draw=draw(p),
                factors=factors(p),
                projection=projection(r["innings_no"], r["seq_no"]),
                leverage=number(p, "leverage", 2),
                pressure=index(p),
                momentum=number(p, "momentum", 1),
            )
        )
    days = repo.get_days(db, match_id)
    return Timeline(
        summary=summary,
        teams=_teams(db, match_id),
        players={
            p["player_id"]: TimelinePlayer(name=p["name"], full_name=p["full_name"])
            for p in repo.get_match_people(db, match_id)
        },
        innings=[
            TimelineInnings(
                innings_no=r["innings_no"],
                batting_team_id=r["batting_team_id"],
                bowling_team_id=r["bowling_team_id"],
                is_super_over=r["is_super_over"],
                target_runs=r["target_runs"],
                target_balls=r["target_balls"],
                max_balls=r["max_balls"],
                declared=bool(r.get("declared")),
                follow_on=bool(r.get("follow_on")),
                wp_start=probability(s := wp.get((r["innings_no"], 0))),
                draw_start=draw(s),
                factors_start=factors(s),
                projection_start=projection(r["innings_no"], 0),
                leverage_start=number(s, "leverage", 2),
                pressure_start=index(s),
            )
            for r in repo.get_innings(db, match_id)
        ],
        deliveries=deliveries,
        substitutions=[TimelineSubstitution(**r) for r in repo.get_substitutions(db, match_id)],
        win_probability=_wp_model(model_row) if model_row else None,
        score_projection=ScoreProjectionModel(**projection_row) if projection_row else None,
        days=None if days is None or not rows else day_markers(rows, days),
    )
