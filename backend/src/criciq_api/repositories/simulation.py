"""SQL for the match simulator: XIs, bowling usage, league rates and replay states."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from criciq_api.db import Database, Row


def available(db: Database) -> bool:
    return all(
        db.has_table(t) for t in ("ball_model_terms", "bowling_usage", "sim_league_rates", "models")
    )


def era_env(db: Database, match_order: int, window: int) -> float | None:
    """League runs off the bat per ball faced over the ``window`` matches before a
    match: the ball model's scoring era (criciq_ml.ball_outcome.add_situation)."""
    value = db.scalar(
        """
        SELECT sum(d.runs_batter) / count(*) FROM deliveries d
        JOIN matches m USING (match_id)
        JOIN innings i USING (match_id, innings_no)
        WHERE m.match_order BETWEEN ? AND ? AND d.extras_wides = 0 AND NOT i.is_super_over
        """,
        [match_order - window, match_order - 1],
    )
    return None if value is None else float(value)


def level_shift(db: Database, match_order: int | None) -> float:
    """The simulator's tracked scoring level, as a shift of the scoring era, before the
    match at ``match_order`` (or after the latest match); 0 where it is not tracked
    (criciq_ml.simulator.level_shifts)."""
    if not db.has_table("sim_level_shifts"):
        return 0.0
    if match_order is None:
        value = db.scalar(
            "SELECT era_shift FROM sim_level_shifts ORDER BY match_order DESC LIMIT 1"
        )
    else:
        value = db.scalar(
            "SELECT era_shift FROM sim_level_shifts WHERE match_order <= ? "
            "ORDER BY match_order DESC LIMIT 1",
            [match_order],
        )
    return 0.0 if value is None else float(value)


def match_context(db: Database, match_id: int) -> Row | None:
    return db.row(
        "SELECT m.match_order, s.year AS season FROM matches m JOIN seasons s USING (season_id) "
        "WHERE m.match_id = ?",
        [match_id],
    )


def latest_season(db: Database) -> int:
    return int(db.scalar("SELECT max(year) FROM seasons"))


def season_end(db: Database, season: int) -> int | None:
    """The match order of a season's last match."""
    value = db.scalar(
        "SELECT max(m.match_order) FROM matches m JOIN seasons s USING (season_id) "
        "WHERE s.year = ?",
        [season],
    )
    return None if value is None else int(value)


def season_teams(db: Database) -> list[Row]:
    """Every side that played in each season, with its name that season."""
    return db.rows(
        """
        SELECT s.year AS season, f.franchise_id, f.name, f.primary_color AS color,
               t.display_name
        FROM team_seasons t
        JOIN seasons s USING (season_id)
        JOIN franchises f USING (franchise_id)
        WHERE t.team_season_id IN (SELECT DISTINCT team_season_id FROM match_players)
        ORDER BY s.year DESC, f.name
        """
    )


def season_squad(db: Database, season: int, franchise_id: str) -> list[Row]:
    """Everyone who played for a franchise in a season (XI or substitute), with their
    appearances, most first."""
    return db.rows(
        """
        SELECT mp.player_id, count(DISTINCT mp.match_id) AS matches, t.display_name
        FROM match_players mp
        JOIN team_seasons t USING (team_season_id)
        JOIN seasons s USING (season_id)
        WHERE s.year = ? AND t.franchise_id = ?
        GROUP BY ALL
        ORDER BY matches DESC, mp.player_id
        """,
        [season, franchise_id],
    )


def league_rates(db: Database, first: int, last: int) -> list[tuple[Any, ...]]:
    rows = db.rows(
        """
        SELECT innings_no, phase, sum(legal_balls) AS balls, sum(run_outs) AS run_outs,
               sum(x0) AS x0, sum(x1) AS x1, sum(x2) AS x2, sum(x3) AS x3, sum(x4) AS x4,
               sum(x5) AS x5
        FROM sim_league_rates WHERE season BETWEEN ? AND ? GROUP BY ALL
        """,
        [first, last],
    )
    return [tuple(r.values()) for r in rows]


def usage_priors(db: Database, first: int, last: int) -> list[tuple[str | None, int, float]]:
    rows = db.rows(
        """
        SELECT p.bowling_type, u.over_no, sum(u.overs) AS overs FROM bowling_usage u
        LEFT JOIN players p USING (player_id)
        WHERE u.season BETWEEN ? AND ? GROUP BY ALL
        """,
        [first, last],
    )
    return [(r["bowling_type"], int(r["over_no"]), float(r["overs"])) for r in rows]


def candidates(
    db: Database,
    player_ids: Sequence[str],
    history: int,
    upto: int | None = None,
    overs: int = 20,
) -> list[Row]:
    """Players with their usual batting position and recent bowling usage (in the
    format's ``overs``).

    Both come from each player's own last ``history`` seasons up to ``upto`` (any
    season when empty), so a player from any era can be picked as they were then.
    """
    last = 9999 if upto is None else upto
    if not player_ids:
        return []
    marks = ", ".join("?" for _ in player_ids)
    return db.rows(
        f"""
        WITH picked AS (SELECT unnest([{marks}]) AS player_id),
        bat AS (
            SELECT b.player_id, avg(b.position) AS position FROM player_batting_innings b
            JOIN (
                SELECT player_id, max(season) AS last FROM player_batting_innings
                WHERE player_id IN (SELECT player_id FROM picked) AND season <= ?
                GROUP BY player_id
            ) l USING (player_id)
            WHERE b.season > l.last - ? AND b.season <= l.last GROUP BY b.player_id
        ),
        bowl AS (
            SELECT u.player_id, list(struct_pack(over_no := u.over_no, overs := u.overs)) AS overs
            FROM (
                SELECT u.player_id, u.over_no, sum(u.overs) AS overs FROM bowling_usage u
                JOIN (
                    SELECT player_id, max(season) AS last FROM bowling_usage
                    WHERE player_id IN (SELECT player_id FROM picked) AND season <= ?
                    GROUP BY player_id
                ) l USING (player_id)
                WHERE u.season > l.last - ? AND u.season <= l.last AND u.over_no < {overs}
                GROUP BY ALL
            ) u
            GROUP BY u.player_id
        )
        SELECT p.player_id, p.name, p.full_name, i.role, p.batting_hand, p.bowling_type,
               bat.position, bowl.overs
        FROM picked x
        JOIN players p USING (player_id)
        LEFT JOIN player_index i USING (player_id)
        LEFT JOIN bat USING (player_id)
        LEFT JOIN bowl USING (player_id)
        """,
        [*player_ids, last, history, last, history],
    )


def latest_xi(
    db: Database, franchise_id: str, season: int | None = None
) -> tuple[Row, list[str]] | None:
    """The franchise's most recent playing XI (in ``season``, if given), in that
    match's batting order."""
    match = db.row(
        """
        SELECT match_id, team_id, season, match_date FROM team_matches
        WHERE franchise_id = ? AND season <= coalesce(?, 9999)
        ORDER BY match_order DESC LIMIT 1
        """,
        [franchise_id, season],
    )
    if match is not None and season is not None and int(match["season"]) != season:
        return None
    if match is None:
        return None
    rows = db.rows(
        """
        SELECT mp.player_id
        FROM match_players mp
        LEFT JOIN player_batting_innings b
            ON b.player_id = mp.player_id AND b.match_id = mp.match_id
        WHERE mp.match_id = ? AND mp.team_season_id = ? AND mp.selection = 'playing_xi'
        ORDER BY coalesce(b.position, 99), mp.list_position
        """,
        [match["match_id"], match["team_id"]],
    )
    return match, [r["player_id"] for r in rows]


# --------------------------------------------------------------------------- replay states


def state_ball(db: Database, match_id: int, innings_no: int, seq_no: int) -> Row | None:
    """The delivery at a replay position, with the match's teams and target."""
    return db.row(
        """
        SELECT d.*, i.target_runs, i.target_balls, m.scheduled_overs,
               m.team1_id, m.team2_id
        FROM deliveries d
        JOIN innings i USING (match_id, innings_no)
        JOIN matches m USING (match_id)
        WHERE d.match_id = ? AND d.innings_no = ? AND d.seq_no = ? AND NOT i.is_super_over
        """,
        [match_id, innings_no, seq_no],
    )


def next_ball(db: Database, match_id: int, innings_no: int, seq_no: int) -> Row | None:
    return db.row(
        """
        SELECT batter_id, non_striker_id, bowler_id, over_no FROM deliveries
        WHERE match_id = ? AND innings_no = ? AND seq_no > ?
        ORDER BY seq_no LIMIT 1
        """,
        [match_id, innings_no, seq_no],
    )


def innings_so_far(db: Database, match_id: int, innings_no: int, seq_no: int) -> list[Row]:
    """Every delivery of an innings up to and including ``seq_no``."""
    return db.rows(
        """
        SELECT d.seq_no, d.over_no, d.is_legal, d.batter_id, d.non_striker_id, d.bowler_id,
               d.runs_batter, d.extras_wides, d.legal_ball_no, d.team_runs, d.team_wickets
        FROM deliveries d
        WHERE d.match_id = ? AND d.innings_no = ? AND d.seq_no <= ?
        ORDER BY d.seq_no
        """,
        [match_id, innings_no, seq_no],
    )


def dismissed(db: Database, match_id: int, innings_no: int, seq_no: int) -> list[str]:
    rows = db.rows(
        """
        SELECT player_out_id FROM wickets
        WHERE match_id = ? AND innings_no = ? AND seq_no <= ? AND is_dismissal
        """,
        [match_id, innings_no, seq_no],
    )
    return [r["player_out_id"] for r in rows]


def squad(db: Database, match_id: int, team_season_id: str) -> list[str]:
    """Everyone who played for a side in a match: the XI and any substitute who batted
    or bowled, XI first in list order."""
    rows = db.rows(
        """
        SELECT player_id, min(o) AS o FROM (
            SELECT player_id, list_position AS o FROM match_players
            WHERE match_id = ? AND team_season_id = ?
            UNION ALL
            SELECT batter_id, 100 FROM deliveries WHERE match_id = ? AND batting_team_id = ?
            UNION ALL
            SELECT bowler_id, 100 FROM deliveries WHERE match_id = ? AND bowling_team_id = ?
        ) GROUP BY player_id ORDER BY o, player_id
        """,
        [match_id, team_season_id] * 3,
    )
    return [r["player_id"] for r in rows]


def win_probability(db: Database, match_id: int, innings_no: int, seq_no: int) -> float | None:
    if not db.has_table("wp_predictions"):
        return None
    value = db.scalar(
        "SELECT wp_team_a FROM wp_predictions WHERE match_id = ? AND innings_no = ? AND seq_no = ?",
        [match_id, innings_no, seq_no],
    )
    return None if value is None else float(value)


def first_innings(db: Database, match_id: int) -> Row | None:
    return db.row(
        """
        SELECT batting_team_id, bowling_team_id, runs, wickets, legal_balls FROM innings
        WHERE match_id = ? AND innings_no = 1
        """,
        [match_id],
    )
