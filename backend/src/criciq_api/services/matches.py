"""Assemble match summaries, scorecards and replay timelines."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import matches as repo
from criciq_api.schemas.matches import (
    BattingEntry,
    BowlingEntry,
    Extras,
    FallOfWicket,
    InningsScorecard,
    MatchDetail,
    MatchPage,
    MatchSummary,
    PlayerRef,
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
)
from criciq_core.cricket import overs_notation


class MatchNotFoundError(LookupError):
    pass


def summary_from_row(row: Row) -> MatchSummary:
    def side(prefix: str) -> TeamScore:
        return TeamScore(
            team_season_id=row[f"{prefix}_id"],
            franchise_id=row[f"{prefix}_short"],
            name=row[f"{prefix}_name"],
            color=row[f"{prefix}_color"],
            runs=row[f"{prefix}_runs"],
            wickets=row[f"{prefix}_wickets"],
            overs=row[f"{prefix}_overs"],
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


def get_timeline(db: Database, match_id: int) -> Timeline:
    summary = _summary(db, match_id)
    deliveries = []
    for r in repo.get_deliveries(db, match_id):
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
            )
        )
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
            )
            for r in repo.get_innings(db, match_id)
        ],
        deliveries=deliveries,
        substitutions=[TimelineSubstitution(**r) for r in repo.get_substitutions(db, match_id)],
    )
