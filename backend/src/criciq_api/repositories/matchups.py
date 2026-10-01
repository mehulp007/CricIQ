"""SQL for the Matchup Lab (``matchup_cells`` and ``ball_model_terms``, written by criciq-ml)."""

from __future__ import annotations

from typing import Literal

from criciq_api.db import Database, Row
from criciq_core.phases import default_phase_config

CLASSES = ("dot", "one", "two", "three", "four", "six", "out")
RUNS = (0, 1, 2, 3, 4, 6, 0)

MatchupSort = Literal["balls", "batter_edge", "bowler_edge"]

_SUMS = ", ".join(
    [f"sum(n_{c})::INTEGER AS n_{c}" for c in CLASSES] + [f"sum(e_{c}) AS e_{c}" for c in CLASSES]
)
# Matchup effect beyond form: (observed - expected) runs per ball, shrunk by kappa.
_EDGE = "100 * ({diff}) / (sum(balls) + ?)".format(
    diff=" + ".join(
        f"{r} * (sum(n_{c}) - sum(e_{c}))" for c, r in zip(CLASSES, RUNS, strict=True) if r
    )
)


def available(db: Database) -> bool:
    return db.has_table("matchup_cells") and db.has_table("ball_model_terms")


def terms(db: Database) -> dict[str, list[float]]:
    rows = db.rows("SELECT term, coefs FROM ball_model_terms")
    return {r["term"]: list(r["coefs"]) for r in rows}


def cells(db: Database, batter_id: str, bowler_id: str, first: int, last: int) -> list[Row]:
    return db.rows(
        f"""
        SELECT season, phase, sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs, {_SUMS}
        FROM matchup_cells
        WHERE batter_id = ? AND bowler_id = ? AND season BETWEEN ? AND ?
        GROUP BY season, phase ORDER BY season, phase
        """,
        [batter_id, bowler_id, first, last],
    )


def player(db: Database, player_id: str) -> Row | None:
    return db.row(
        """
        SELECT i.player_id, i.name, i.full_name, i.batting_hand, i.bowling_type, i.bowling_style,
               i.latest_team_id, f.name AS team_name, f.primary_color AS team_color
        FROM player_index i LEFT JOIN franchises f ON f.franchise_id = i.latest_team_id
        WHERE i.player_id = ?
        """,
        [player_id],
    )


def dismissals(
    db: Database, batter_id: str, bowler_id: str, first: int, last: int, phase: str | None
) -> list[Row]:
    """Every time the bowler took the batter's wicket, newest first."""
    phase_sql = default_phase_config().for_format("T20").sql_case("d.over_no")
    phase_filter = f"AND {phase_sql} = ?" if phase else ""
    return db.rows(
        f"""
        SELECT w.match_id, s.year AS season, m.match_date AS date, w.kind
        FROM wickets w
        JOIN deliveries d USING (match_id, innings_no, seq_no)
        JOIN innings i USING (match_id, innings_no)
        JOIN matches m USING (match_id)
        JOIN seasons s USING (season_id)
        WHERE w.player_out_id = ? AND w.bowler_id = ? AND w.bowler_credited
          AND NOT i.is_super_over AND s.year BETWEEN ? AND ? {phase_filter}
        ORDER BY m.match_order DESC
        """,
        [batter_id, bowler_id, first, last, *([phase] if phase else [])],
    )


def list_pairs(
    db: Database,
    *,
    batter_id: str | None,
    bowler_id: str | None,
    first: int,
    last: int,
    min_balls: int,
    sort: MatchupSort,
    kappa: float,
    limit: int,
    offset: int,
) -> tuple[list[Row], int]:
    clauses = ["season BETWEEN ? AND ?"]
    params: list[object] = [first, last]
    if batter_id:
        clauses.append("batter_id = ?")
        params.append(batter_id)
    if bowler_id:
        clauses.append("bowler_id = ?")
        params.append(bowler_id)
    order = {
        "balls": "balls DESC, runs DESC",
        "batter_edge": "edge DESC, balls DESC",
        "bowler_edge": "edge ASC, balls DESC",
    }[sort]
    base = f"""
        SELECT batter_id, bowler_id, sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs,
               {_SUMS}, {_EDGE} AS edge
        FROM matchup_cells
        WHERE {" AND ".join(clauses)}
        GROUP BY batter_id, bowler_id
        HAVING sum(balls) >= ?
    """
    all_params = [kappa, *params, min_balls]
    total = int(db.scalar(f"SELECT count(*) FROM ({base})", all_params))
    rows = db.rows(f"{base} ORDER BY {order} LIMIT ? OFFSET ?", [*all_params, limit, offset])
    return rows, total
