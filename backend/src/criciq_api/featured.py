"""Export featured match timelines and a latest-season snapshot for the frontend to bundle.

Featured replays ship inside the web app, so each competition's overview and these
replays work instantly even while the (free-tier) API is asleep. They are
produced by the same service code as the API, so the payloads are identical.
Every competition with a serving database gets a folder
(``frontend/data/featured/<competition>/``); ``index.ts`` imports them all.

Usage: uv run python -m criciq_api.featured   (or `just featured`)
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from criciq_api.core.config import get_settings
from criciq_api.db import Database, serving_paths
from criciq_api.schemas.matches import MatchSummary
from criciq_api.services.matches import get_timeline
from criciq_core import paths

OUT_DIR = paths.repo_root() / "frontend" / "data" / "featured"

# match_id -> why it is worth replaying, by competition
IPL_FEATURED: dict[int, str] = {
    1535465: "IPL 2026 final",
    1473511: "IPL 2025 final: Royal Challengers' first title",
    1426312: "IPL 2024 final",
    1426268: "The 287 vs 262 run-fest, the highest total in IPL history",
    1370353: "IPL 2023 final: a rain-reduced chase won off the last ball",
    1216517: "A tie that needed two super overs",
    1181768: "IPL 2019 final: Mumbai win by one run",
    1082625: "Gujarat Lions vs Mumbai Indians: decided by a super over",
    981019: "IPL 2016 final: Sunrisers edge Royal Challengers",
    335982: "The first IPL match: McCullum's 158*",
}
# Every men's T20 World Cup final.
T20I_FEATURED: dict[int, str] = {
    1512773: "T20 World Cup 2026 final",
    1415755: "T20 World Cup 2024 final",
    1298179: "T20 World Cup 2022 final",
    1273756: "T20 World Cup 2021 final",
    951373: "T20 World Cup 2016 final",
    682965: "T20 World Cup 2014 final",
    533298: "T20 World Cup 2012 final",
    412703: "T20 World Cup 2010 final",
    356017: "T20 World Cup 2009 final",
    287879: "T20 World Cup 2007 final, the first",
}
# Every men's ODI World Cup final in the data, the Champions Trophy finals, and the
# highest chase.
ODI_FEATURED: dict[int, str] = {
    1384439: "World Cup 2023 final",
    1144530: "World Cup 2019 final: tied, then a tied super over, won on boundaries",
    656495: "World Cup 2015 final",
    433606: "World Cup 2011 final: India win at home",
    247507: "World Cup 2007 final, cut to 38 overs by rain",
    65286: "World Cup 2003 final",
    1466428: "Champions Trophy 2025 final",
    1022375: "Champions Trophy 2017 final",
    566948: "Champions Trophy 2013 final, reduced to 20 overs",
    238200: "South Africa chase 435 against Australia, the highest chase in ODI history",
}
FEATURED: dict[str, dict[int, str]] = {
    "ipl": IPL_FEATURED,
    "t20i": T20I_FEATURED,
    "odi": ODI_FEATURED,
}
# Other competitions feature their latest finals.
FINALS = 6


class FeaturedEntry(BaseModel):
    match_id: int
    headline: str
    summary: MatchSummary


class FeaturedIndex(BaseModel):
    data_version: str
    matches: list[FeaturedEntry]


class Leader(BaseModel):
    player_id: str
    name: str
    team: str | None
    value: float
    detail: str


class SeasonSnapshot(BaseModel):
    """The latest season at a glance, for the overview page."""

    season: int
    label: str
    matches: int
    champion: str | None
    first_innings_average: float
    previous_first_innings_average: float | None
    sixes: int
    leaders: dict[str, Leader]


def _label(db: Database, season: int) -> str:
    if not db.season_spans_new_year:
        return str(season)
    found = db.scalar("SELECT cricsheet_label FROM seasons WHERE year = ?", [season])
    return str(found or season)


def season_snapshot(db: Database) -> SeasonSnapshot:
    season = int(db.scalar("SELECT max(season) FROM match_summaries"))

    def avg_first(year: int) -> float | None:
        value = db.scalar(
            """
            SELECT avg(team_a_runs) FROM match_summaries
            WHERE season = ? AND team_a_runs IS NOT NULL AND outcome_type <> 'no_result'
            """,
            [year],
        )
        return None if value is None else round(float(value), 1)

    # A league's champions won its final; internationals have no single champion.
    team_type = db.scalar("SELECT team_type FROM competitions LIMIT 1")
    final = (
        db.row(
            """
            SELECT winner_name FROM match_summaries
            WHERE season = ? AND stage = 'Final' ORDER BY match_order DESC LIMIT 1
            """,
            [season],
        )
        if team_type == "club"
        else None
    )

    def leader(sql: str, detail: str) -> Leader:
        row = db.row(sql, [season])
        assert row is not None
        return Leader(
            player_id=row["player_id"],
            name=row["name"],
            team=row["team"],
            value=float(row["value"]),
            detail=detail.format(**row),
        )

    name = "coalesce(p.full_name, p.name) AS name"
    leaders = {
        "runs": leader(
            f"""
            SELECT b.player_id, {name}, arg_max(b.team_id, b.match_order) AS team,
                   sum(b.runs) AS value, round(100.0 * sum(b.runs) / sum(b.balls), 1) AS sr
            FROM player_batting_innings b JOIN players p USING (player_id)
            WHERE b.season = ? GROUP BY ALL ORDER BY value DESC LIMIT 1
            """,
            "strike rate {sr}",
        ),
        "wickets": leader(
            f"""
            SELECT b.player_id, {name}, arg_max(b.team_id, b.match_order) AS team,
                   sum(b.wickets) AS value, round(6.0 * sum(b.runs) / sum(b.balls), 2) AS econ
            FROM player_bowling_innings b JOIN players p USING (player_id)
            WHERE b.season = ? GROUP BY ALL ORDER BY value DESC, econ LIMIT 1
            """,
            "economy {econ}",
        ),
        "runs_above_par": leader(
            f"""
            SELECT b.player_id, {name}, arg_max(b.team_id, b.match_order) AS team,
                   round(sum(b.runs) - sum(b.par_runs)) AS value, sum(b.balls) AS balls
            FROM player_batting_innings b JOIN players p USING (player_id)
            WHERE b.season = ? GROUP BY ALL ORDER BY value DESC LIMIT 1
            """,
            "from {balls} balls",
        ),
        "runs_saved": leader(
            f"""
            SELECT b.player_id, {name}, arg_max(b.team_id, b.match_order) AS team,
                   round(sum(b.par_runs) - sum(b.runs)) AS value, sum(b.balls) AS balls
            FROM player_bowling_innings b JOIN players p USING (player_id)
            WHERE b.season = ? GROUP BY ALL ORDER BY value DESC LIMIT 1
            """,
            "from {balls} balls",
        ),
    }
    sixes = db.scalar("SELECT sum(sixes) FROM player_batting_innings WHERE season = ?", [season])
    return SeasonSnapshot(
        season=season,
        label=_label(db, season),
        matches=int(db.scalar("SELECT count(*) FROM match_summaries WHERE season = ?", [season])),
        champion=final["winner_name"] if final else None,
        first_innings_average=avg_first(season) or 0.0,
        previous_first_innings_average=avg_first(season - 1),
        sixes=int(sixes or 0),
        leaders=leaders,
    )


def featured_matches(db: Database) -> dict[int, str]:
    """The competition's featured replays: a curated list, else its latest finals."""
    competition = (db.competition_id or "IPL").lower()
    if competition in FEATURED:
        return FEATURED[competition]
    short = db.scalar("SELECT short_name FROM competitions LIMIT 1")
    rows = db.rows(
        """
        SELECT match_id, season FROM match_summaries
        WHERE stage = 'Final' AND outcome_type <> 'no_result'
        ORDER BY match_order DESC LIMIT ?
        """,
        [FINALS],
    )
    return {r["match_id"]: f"{short} {_label(db, r['season'])} final" for r in rows}


def export_featured(db: Database, out_dir: Path) -> FeaturedIndex:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in [*out_dir.glob("*.json"), *out_dir.glob("*.ts")]:
        stale.unlink()
    entries = []
    featured = featured_matches(db)
    for match_id, headline in featured.items():
        timeline = get_timeline(db, match_id)
        (out_dir / f"{match_id}.json").write_text(
            timeline.model_dump_json() + "\n", encoding="utf-8", newline="\n"
        )
        entries.append(
            FeaturedEntry(match_id=match_id, headline=headline, summary=timeline.summary)
        )
    index = FeaturedIndex(data_version=db.data_version, matches=entries)
    (out_dir / "index.json").write_text(
        json.dumps(index.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out_dir / "manifest.ts").write_text(_manifest(list(featured)), encoding="utf-8", newline="\n")
    (out_dir / "snapshot.json").write_text(
        json.dumps(season_snapshot(db).model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return index


def _manifest(match_ids: list[int]) -> str:
    """Explicit lazy imports so the bundler ships exactly the featured files."""
    lines = [
        "// Generated by `python -m criciq_api.featured`. Do not edit.",
        'import type { Timeline } from "@/lib/api/types";',
        "",
        "export const featuredTimelines: Record<number, () => Promise<Timeline>> = {",
    ]
    lines += [
        f'  {mid}: () => import("./{mid}.json").then((m) => m.default as unknown as Timeline),'
        for mid in match_ids
    ]
    lines += ["};", ""]
    return "\n".join(lines)


def _bundles(competitions: list[str]) -> str:
    """Static imports of every competition's bundle (the bundler needs them spelled out)."""
    lines = [
        "// Generated by `python -m criciq_api.featured`. Do not edit.",
        'import type { Timeline } from "@/lib/api/types";',
        "",
    ]
    for c in competitions:
        lines += [
            f'import {c}Index from "./{c}/index.json";',
            f'import {{ featuredTimelines as {c}Timelines }} from "./{c}/manifest";',
            f'import {c}Snapshot from "./{c}/snapshot.json";',
        ]
    lines += [
        "",
        "export interface FeaturedBundle {",
        "  index: unknown;",
        "  snapshot: unknown;",
        "  timelines: Record<number, () => Promise<Timeline>>;",
        "}",
        "",
        "export const featuredBundles: Record<string, FeaturedBundle> = {",
    ]
    lines += [
        f"  {c}: {{ index: {c}Index, snapshot: {c}Snapshot, timelines: {c}Timelines }},"
        for c in competitions
    ]
    lines += ["};", ""]
    return "\n".join(lines)


def export_all(serving_db: Path, out_dir: Path = OUT_DIR) -> dict[str, FeaturedIndex]:
    """Every competition's bundle, and the index that imports them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in [*out_dir.glob("*.json"), *out_dir.glob("*.ts")]:
        stale.unlink()
    found = {}
    for path in serving_paths(serving_db):
        if not path.exists():
            continue
        db = Database(path)
        try:
            competition = (db.competition_id or "IPL").lower()
            found[competition] = export_featured(db, out_dir / competition)
        finally:
            db.close()
    (out_dir / "index.ts").write_text(_bundles(list(found)), encoding="utf-8", newline="\n")
    return found


def main() -> None:
    for competition, index in export_all(get_settings().serving_db).items():
        print(f"{competition}: {len(index.matches)} featured timelines")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
