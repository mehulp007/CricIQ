"""Warehouse validation: declarative invariant checks + golden scorecards.

Each check is a SQL query returning *violating* rows, so a passing check
returns nothing and a failing one explains itself. Schema constraints
(keys, references, domains) are already enforced at load time; these checks
cover cricket logic that a schema cannot express.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import duckdb

from criciq_pipelines.reference import GoldenMatch, load_golden_matches

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Check:
    id: str
    description: str
    sql: str
    severity: Severity = "error"


@dataclass
class CheckResult:
    id: str
    description: str
    severity: Severity
    violations: int
    sample: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.violations == 0


CHECKS: tuple[Check, ...] = (
    Check(
        "innings_legal_balls_within_limit",
        "An innings never has more legal balls than its format allows "
        "(beyond balls from umpire-miscounted overs, reported separately).",
        """
        SELECT i.match_id, i.innings_no, i.legal_balls, coalesce(x.extra_balls, 0) AS miscounted
        FROM innings i JOIN matches m USING (match_id)
        LEFT JOIN (
            SELECT match_id, innings_no, sum(n - 6) AS extra_balls
            FROM (SELECT match_id, innings_no, over_no, count(*) AS n
                  FROM deliveries WHERE is_legal GROUP BY ALL HAVING count(*) > 6)
            GROUP BY ALL
        ) x USING (match_id, innings_no)
        WHERE i.legal_balls - coalesce(x.extra_balls, 0)
              > CASE WHEN i.is_super_over THEN m.balls_per_over
                     ELSE m.scheduled_overs * m.balls_per_over END
        """,
    ),
    Check(
        "innings_wickets_within_limit",
        "At most 10 wickets fall in an innings (2 in a super over).",
        """
        SELECT match_id, innings_no, wickets FROM innings
        WHERE wickets > CASE WHEN is_super_over THEN 2 ELSE 10 END
        """,
    ),
    Check(
        "innings_totals_match_ball_by_ball",
        "Innings totals equal the running score after the final delivery.",
        """
        SELECT i.match_id, i.innings_no, i.runs, i.wickets, d.team_runs, d.team_wickets
        FROM innings i
        JOIN (SELECT match_id, innings_no, arg_max(team_runs, seq_no) AS team_runs,
                     arg_max(team_wickets, seq_no) AS team_wickets
              FROM deliveries GROUP BY ALL) d USING (match_id, innings_no)
        WHERE i.runs <> d.team_runs OR i.wickets <> d.team_wickets
        """,
    ),
    Check(
        "chase_target_is_first_innings_plus_one",
        "Without a rain rule, the chase target is the first-innings total plus one.",
        """
        SELECT m.match_id, i1.runs AS first_innings, i2.target_runs
        FROM matches m
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.win_method IS NULL AND NOT i2.is_super_over
          AND i2.target_runs IS DISTINCT FROM i1.runs + 1
        """,
    ),
    Check(
        "rain_rule_matches_have_revised_target",
        "Every D/L result carries a revised target on the chase.",
        """
        SELECT m.match_id FROM matches m
        LEFT JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.win_method IS NOT NULL AND (i2.target_runs IS NULL OR i2.target_overs IS NULL)
        """,
    ),
    Check(
        "win_by_runs_is_consistent",
        "A win by runs goes to the side batting first, by the exact run margin. Under D/L "
        "the chasing side can also win 'by runs' when ahead of par as play is abandoned.",
        """
        SELECT m.match_id, m.winner_id, i1.batting_team_id, i1.runs, i2.runs, m.win_by_runs
        FROM matches m
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.outcome_type = 'win' AND m.win_by_runs IS NOT NULL
          AND m.win_method IS NULL
          AND (m.winner_id <> i1.batting_team_id OR i1.runs - i2.runs <> m.win_by_runs)
        """,
    ),
    Check(
        "win_by_wickets_is_consistent",
        "A win by wickets goes to the chasing side, which reached its target.",
        """
        SELECT m.match_id, m.winner_id, i2.batting_team_id, i2.runs, i2.target_runs,
               i2.wickets, m.win_by_wickets
        FROM matches m
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.outcome_type = 'win' AND m.win_by_wickets IS NOT NULL
          AND (m.winner_id <> i2.batting_team_id OR i2.runs < i2.target_runs
               OR m.win_by_wickets <> 10 - i2.wickets)
        """,
    ),
    Check(
        "ties_have_equal_scores_and_a_super_over",
        "Tied matches have level scores (without a rain rule) and a super-over decider.",
        """
        SELECT m.match_id, i1.runs, i2.runs, count(so.innings_no) AS super_over_innings
        FROM matches m
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        LEFT JOIN innings so ON so.match_id = m.match_id AND so.is_super_over
        WHERE m.outcome_type = 'tie'
        GROUP BY ALL
        HAVING (m.win_method IS NULL AND i1.runs <> i2.runs) OR count(so.innings_no) < 2
            OR NOT any_value(m.decided_by_super_over)
        """,
    ),
    Check(
        "no_result_has_no_winner",
        "No-result matches have no winner.",
        "SELECT match_id FROM matches WHERE outcome_type = 'no_result' AND winner_id IS NOT NULL",
    ),
    Check(
        "decided_matches_have_a_participating_winner",
        "Every win or tie names a winner who played in the match; toss winners played too.",
        """
        SELECT match_id, winner_id, toss_winner_id FROM matches
        WHERE (outcome_type <> 'no_result' AND winner_id NOT IN (team1_id, team2_id))
           OR (outcome_type <> 'no_result' AND winner_id IS NULL)
           OR toss_winner_id NOT IN (team1_id, team2_id)
        """,
    ),
    Check(
        "batters_belong_to_batting_side",
        "Striker and non-striker are in the batting side's match squad.",
        """
        SELECT d.match_id, d.innings_no, d.seq_no, p.player_id
        FROM deliveries d, (SELECT UNNEST([d2.batter_id, d2.non_striker_id]) AS player_id,
                                   d2.match_id, d2.innings_no, d2.seq_no
                            FROM deliveries d2) p
        WHERE p.match_id = d.match_id AND p.innings_no = d.innings_no AND p.seq_no = d.seq_no
          AND NOT EXISTS (SELECT 1 FROM match_players mp
                          WHERE mp.match_id = d.match_id AND mp.player_id = p.player_id
                            AND mp.team_season_id = d.batting_team_id)
        """,
    ),
    Check(
        "bowlers_belong_to_bowling_side",
        "The bowler is in the bowling side's match squad.",
        """
        SELECT d.match_id, d.innings_no, d.seq_no, d.bowler_id FROM deliveries d
        WHERE NOT EXISTS (SELECT 1 FROM match_players mp
                          WHERE mp.match_id = d.match_id AND mp.player_id = d.bowler_id
                            AND mp.team_season_id = d.bowling_team_id)
        """,
    ),
    Check(
        "striker_differs_from_non_striker",
        "The striker and non-striker are different players.",
        "SELECT match_id, innings_no, seq_no FROM deliveries WHERE batter_id = non_striker_id",
    ),
    Check(
        "eleven_players_per_side",
        "Each side names exactly 11 starting players.",
        """
        SELECT match_id, team_season_id, count(*) FILTER (WHERE selection = 'playing_xi') AS xi
        FROM match_players GROUP BY ALL HAVING xi <> 11
        """,
    ),
    Check(
        "impact_substitutes_only_under_the_rule",
        "Impact Player substitutes appear only in seasons where the rule applied.",
        """
        SELECT mp.match_id, mp.player_id FROM match_players mp
        JOIN matches m USING (match_id) JOIN seasons s USING (season_id)
        WHERE mp.selection = 'impact_substitute' AND NOT s.impact_player_rule
        """,
    ),
    Check(
        "season_label_matches_match_year",
        "Cricsheet season labels agree with match dates (e.g. '2007/08' -> 2008).",
        """
        SELECT season_id, year, cricsheet_label FROM seasons
        WHERE cricsheet_label <> year::VARCHAR
          AND right(cricsheet_label, 2) <> right(year::VARCHAR, 2)
          AND left(cricsheet_label, 4) <> year::VARCHAR
        """,
    ),
    Check(
        "overs_have_at_most_six_legal_balls",
        "Overs have at most six legal balls unless Cricsheet records an umpire miscount "
        "(its miscounted_overs keys use the same 0-based numbering as over_no).",
        """
        SELECT d.match_id, d.innings_no, d.over_no, count(*) AS legal_balls
        FROM deliveries d JOIN innings i USING (match_id, innings_no)
        WHERE d.is_legal
        GROUP BY ALL
        HAVING count(*) > 6
           AND (any_value(i.miscounted_overs) IS NULL
                OR json_extract(any_value(i.miscounted_overs), '$."' || d.over_no || '"') IS NULL)
        """,
        severity="warning",
    ),
)


def run_checks(con: duckdb.DuckDBPyConnection, sample_size: int = 5) -> list[CheckResult]:
    results = []
    for check in CHECKS:
        relation = con.sql(check.sql)
        columns = relation.columns
        rows = relation.fetchall()
        results.append(
            CheckResult(
                id=check.id,
                description=check.description,
                severity=check.severity,
                violations=len(rows),
                sample=[dict(zip(columns, row, strict=True)) for row in rows[:sample_size]],
            )
        )
    return results


# --------------------------------------------------------------------------- golden


@dataclass
class GoldenResultRow:
    match_id: int
    description: str
    mismatches: list[str]

    @property
    def passed(self) -> bool:
        return not self.mismatches


def check_golden(con: duckdb.DuckDBPyConnection, golden: GoldenMatch) -> GoldenResultRow:
    problems: list[str] = []
    row = con.execute(
        """
        SELECT m.match_date, m.outcome_type, w.franchise_id, m.win_by_runs, m.win_by_wickets,
               m.win_method, m.decided_by_super_over
        FROM matches m LEFT JOIN team_seasons w ON w.team_season_id = m.winner_id
        WHERE m.match_id = ?
        """,
        [golden.match_id],
    ).fetchone()
    if row is None:
        return GoldenResultRow(golden.match_id, golden.description, ["match not in warehouse"])
    date, outcome, winner, by_runs, by_wickets, method, super_over = row

    def expect(label: str, actual: object, expected: object) -> None:
        if expected is not None and actual != expected:
            problems.append(f"{label}: expected {expected!r}, got {actual!r}")

    expect("date", date, golden.date)
    result = golden.result
    if result.tie:
        expect("outcome", outcome, "tie")
        expect("decided by super over", super_over, True)
        expect("super-over winner", winner, result.super_over_winner)
    else:
        expect("outcome", outcome, "win")
        expect("winner", winner, result.winner)
        expect("win by runs", by_runs, result.by_runs)
        expect("win by wickets", by_wickets, result.by_wickets)
        expect("method", method, result.method)

    innings = con.execute(
        """
        SELECT i.innings_no, t.franchise_id, i.runs, i.wickets, i.target_runs, i.target_overs
        FROM innings i JOIN team_seasons t ON t.team_season_id = i.batting_team_id
        WHERE i.match_id = ? AND NOT i.is_super_over ORDER BY i.innings_no
        """,
        [golden.match_id],
    ).fetchall()
    for expected, actual in zip(golden.innings, innings, strict=False):
        number, team, runs, wickets, target_runs, target_overs = actual
        prefix = f"innings {number}"
        expect(f"{prefix} team", team, expected.team)
        expect(f"{prefix} score", (runs, wickets), (expected.runs, expected.wickets))
        expect(f"{prefix} target runs", target_runs, expected.target_runs)
        if expected.target_overs is not None:
            expect(f"{prefix} target overs", target_overs, float(expected.target_overs))
    if golden.innings and len(innings) != len(golden.innings):
        problems.append(f"expected {len(golden.innings)} innings, found {len(innings)}")
    return GoldenResultRow(golden.match_id, golden.description, problems)


@dataclass
class ValidationReport:
    checks: list[CheckResult]
    golden: list[GoldenResultRow]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error") and all(
            g.passed for g in self.golden
        )


def validate(
    warehouse: Path, config_dir: Path | None = None, *, require_all_golden: bool = True
) -> ValidationReport:
    """Run every check. With ``require_all_golden`` a golden match missing from the
    warehouse fails; test fixtures that hold a subset of matches turn it off."""
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        golden_config = load_golden_matches(config_dir)
        present = {r[0] for r in con.execute("SELECT match_id FROM matches").fetchall()}
        golden = [
            check_golden(con, g)
            for g in golden_config.matches
            if require_all_golden or g.match_id in present
        ]
        return ValidationReport(checks=run_checks(con), golden=golden)
    finally:
        con.close()
