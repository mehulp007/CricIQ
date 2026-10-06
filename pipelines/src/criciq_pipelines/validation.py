"""Warehouse validation: declarative invariant checks + golden scorecards.

Each check is a SQL query returning *violating* rows, so a passing check
returns nothing and a failing one explains itself. Schema constraints
(keys, references, domains) are already enforced at load time; these checks
cover cricket logic that a schema cannot express, for every format: limited-
overs checks skip Tests (``scheduled_overs`` is NULL), and Test results get
their own checks. Every violating row carries its competition.

In a curated (strict) competition every violation is an error. Elsewhere the
source data has known quirks (associate matches with inconsistent margins, rain
reductions without a recorded method, sides of ten), so violations are reported
as notes in the data-quality report instead of failing the build.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import duckdb

from criciq_pipelines.reference import GoldenMatch, load_competitions, load_golden_matches

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
    # Violations in curated competitions (and in rows without a competition).
    violations: int
    sample: list[dict[str, Any]] = field(default_factory=list)
    # Violations in the other competitions, by competition: reported, not failed.
    notes: dict[str, int] = field(default_factory=dict)
    notes_sample: list[dict[str, Any]] = field(default_factory=list)
    # The matches behind the notes, by competition.
    notes_match_ids: dict[str, list[int]] = field(default_factory=dict)
    # Every match behind a counted violation (a data sync quarantines new ones).
    match_ids: list[int] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.violations == 0


CHECKS: tuple[Check, ...] = (
    Check(
        "innings_legal_balls_within_limit",
        "An innings never has more legal balls than its format allows "
        "(beyond balls from umpire-miscounted overs, reported separately).",
        """
        SELECT m.competition_id, i.match_id, i.innings_no, i.legal_balls,
               coalesce(x.extra_balls, 0) AS miscounted
        FROM innings i JOIN matches m USING (match_id)
        LEFT JOIN (
            SELECT match_id, innings_no, sum(n - 6) AS extra_balls
            FROM (SELECT match_id, innings_no, over_no, count(*) AS n
                  FROM deliveries WHERE is_legal GROUP BY ALL HAVING count(*) > 6)
            GROUP BY ALL
        ) x USING (match_id, innings_no)
        WHERE m.scheduled_overs IS NOT NULL
          AND i.legal_balls - coalesce(x.extra_balls, 0)
              > CASE WHEN i.is_super_over THEN m.balls_per_over
                     ELSE m.scheduled_overs * m.balls_per_over END
        """,
    ),
    Check(
        "innings_wickets_within_limit",
        "At most 10 wickets fall in an innings (2 in a super over).",
        """
        SELECT m.competition_id, i.match_id, i.innings_no, i.wickets
        FROM innings i JOIN matches m USING (match_id)
        WHERE i.wickets > CASE WHEN i.is_super_over THEN 2 ELSE 10 END
        """,
    ),
    Check(
        "innings_totals_match_ball_by_ball",
        "Innings totals equal the running score after the final delivery "
        "(plus any penalty runs awarded outside it).",
        """
        SELECT m.competition_id, i.match_id, i.innings_no, i.runs, i.wickets,
               d.team_runs, d.team_wickets
        FROM innings i JOIN matches m USING (match_id)
        JOIN (SELECT match_id, innings_no, arg_max(team_runs, seq_no) AS team_runs,
                     arg_max(team_wickets, seq_no) AS team_wickets
              FROM deliveries GROUP BY ALL) d USING (match_id, innings_no)
        WHERE i.runs - i.penalty_runs <> d.team_runs OR i.wickets <> d.team_wickets
        """,
    ),
    Check(
        "chase_target_is_first_innings_plus_one",
        "In limited-overs cricket without a rain rule, the chase target is the "
        "first-innings total plus one.",
        """
        SELECT m.competition_id, m.match_id, i1.runs AS first_innings, i2.target_runs
        FROM matches m
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.win_method IS NULL AND NOT i2.is_super_over AND m.scheduled_overs IS NOT NULL
          -- a chase shortened by rain can be revised without a recorded method
          AND coalesce(i2.target_overs, m.scheduled_overs) >= m.scheduled_overs
          AND i2.target_runs IS DISTINCT FROM i1.runs + 1
        """,
    ),
    Check(
        "rain_rule_matches_have_revised_target",
        "Every D/L result carries a revised target on the chase.",
        """
        SELECT m.competition_id, m.match_id FROM matches m
        LEFT JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.win_method IS NOT NULL AND (i2.target_runs IS NULL OR i2.target_overs IS NULL)
        """,
    ),
    Check(
        "win_by_runs_is_consistent",
        "In limited-overs cricket a win by runs goes to the side batting first, by the "
        "exact run margin. Under D/L the chasing side can also win 'by runs' when ahead of "
        "par as play is abandoned.",
        """
        SELECT m.competition_id, m.match_id, m.winner_id, i1.batting_team_id, i1.runs, i2.runs,
               m.win_by_runs
        FROM matches m
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.outcome_type = 'win' AND m.win_by_runs IS NOT NULL
          AND m.win_method IS NULL AND m.scheduled_overs IS NOT NULL
          AND (m.winner_id <> i1.batting_team_id OR i1.runs - i2.runs <> m.win_by_runs)
        """,
    ),
    Check(
        "win_by_wickets_is_consistent",
        "In limited-overs cricket a win by wickets goes to the chasing side, which "
        "reached its target.",
        """
        SELECT m.competition_id, m.match_id, m.winner_id, i2.batting_team_id, i2.runs,
               i2.target_runs, i2.wickets, m.win_by_wickets
        FROM matches m
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        WHERE m.outcome_type = 'win' AND m.win_by_wickets IS NOT NULL
          AND m.scheduled_overs IS NOT NULL
          AND (m.winner_id <> i2.batting_team_id OR i2.runs < i2.target_runs
               OR m.win_by_wickets <> 10 - i2.wickets)
        """,
    ),
    Check(
        "ties_have_equal_scores",
        "Limited-overs ties have level scores (without a rain rule); a tie decided by a "
        "super over has both super-over innings.",
        """
        SELECT m.competition_id, m.match_id, i1.runs, i2.runs,
               count(so.innings_no) AS super_over_innings
        FROM matches m
        JOIN innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        JOIN innings i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        LEFT JOIN innings so ON so.match_id = m.match_id AND so.is_super_over
        WHERE m.outcome_type = 'tie' AND m.scheduled_overs IS NOT NULL
        GROUP BY ALL
        HAVING (m.win_method IS NULL AND i1.runs <> i2.runs)
            OR (any_value(m.decided_by_super_over) AND count(so.innings_no) < 2)
        """,
    ),
    Check(
        "ties_in_the_ipl_go_to_a_super_over",
        "Every tie in a curated T20 league is settled by a super over.",
        """
        SELECT competition_id, match_id FROM matches
        WHERE competition_id = 'IPL' AND outcome_type = 'tie' AND NOT decided_by_super_over
        """,
    ),
    Check(
        "no_result_has_no_winner",
        "No-result matches and draws have no winner.",
        """
        SELECT competition_id, match_id FROM matches
        WHERE outcome_type IN ('no_result', 'draw') AND winner_id IS NOT NULL
        """,
    ),
    Check(
        "decided_matches_have_a_participating_winner",
        "Every win, and every tie settled by a super over or bowl-out, names a winner who "
        "played in the match; toss winners played too.",
        """
        SELECT competition_id, match_id, winner_id, toss_winner_id FROM matches
        WHERE (winner_id IS NOT NULL AND winner_id NOT IN (team1_id, team2_id))
           OR (outcome_type = 'win' AND winner_id IS NULL)
           OR (outcome_type = 'tie' AND (decided_by_super_over OR decided_by_bowl_out)
               AND winner_id IS NULL)
           OR (outcome_type = 'tie' AND NOT (decided_by_super_over OR decided_by_bowl_out)
               AND winner_id IS NOT NULL)
           OR toss_winner_id NOT IN (team1_id, team2_id)
        """,
    ),
    Check(
        "innings_per_format",
        "A Test has at most four innings; a limited-overs match at most two before any super over.",
        """
        SELECT m.competition_id, m.match_id,
               count(*) FILTER (WHERE NOT i.is_super_over) AS innings
        FROM matches m JOIN innings i USING (match_id)
        GROUP BY ALL
        HAVING count(*) FILTER (WHERE NOT i.is_super_over)
               > CASE WHEN any_value(m.scheduled_overs) IS NULL THEN 4 ELSE 2 END
        """,
    ),
    Check(
        "test_wins_are_consistent",
        "Test results add up: an innings win goes to a side that batted once and outscored "
        "the other; a win by runs goes to the side that did not bat last, by the run "
        "difference; a win by wickets goes to the side batting last.",
        """
        WITH totals AS (
            SELECT match_id, batting_team_id AS team, sum(runs) AS runs, count(*) AS innings,
                   max(innings_no) AS last_innings
            FROM innings WHERE NOT is_super_over GROUP BY ALL
        ),
        last AS (
            SELECT match_id, arg_max(batting_team_id, innings_no) AS team,
                   arg_max(wickets, innings_no) AS wickets
            FROM innings WHERE NOT is_super_over GROUP BY match_id
        )
        SELECT m.competition_id, m.match_id, m.winner_id, m.win_by_runs, m.win_by_wickets,
               m.win_by_innings, w.runs AS winner_runs, l.runs AS loser_runs
        FROM matches m
        JOIN totals w ON w.match_id = m.match_id AND w.team = m.winner_id
        JOIN totals l ON l.match_id = m.match_id AND l.team <> m.winner_id
        JOIN last ON last.match_id = m.match_id
        WHERE m.scheduled_overs IS NULL AND m.outcome_type = 'win'
          AND (
              (m.win_by_innings IS NOT NULL
               AND (w.innings <> 1 OR w.runs - l.runs <> m.win_by_runs))
              OR (m.win_by_innings IS NULL AND m.win_by_runs IS NOT NULL
                  AND (last.team = m.winner_id OR w.runs - l.runs <> m.win_by_runs))
              OR (m.win_by_wickets IS NOT NULL
                  AND (last.team <> m.winner_id OR m.win_by_wickets <> 10 - last.wickets))
          )
        """,
    ),
    Check(
        "batters_belong_to_batting_side",
        "Striker and non-striker are in the batting side's match squad.",
        """
        SELECT m.competition_id, d.match_id, d.innings_no, d.seq_no, p.player_id
        FROM matches m JOIN deliveries d USING (match_id),
             (SELECT UNNEST([d2.batter_id, d2.non_striker_id]) AS player_id,
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
        SELECT m.competition_id, d.match_id, d.innings_no, d.seq_no, d.bowler_id
        FROM deliveries d JOIN matches m USING (match_id)
        WHERE NOT EXISTS (SELECT 1 FROM match_players mp
                          WHERE mp.match_id = d.match_id AND mp.player_id = d.bowler_id
                            AND mp.team_season_id = d.bowling_team_id)
        """,
    ),
    Check(
        "striker_differs_from_non_striker",
        "The striker and non-striker are different players.",
        """
        SELECT m.competition_id, d.match_id, d.innings_no, d.seq_no
        FROM deliveries d JOIN matches m USING (match_id) WHERE d.batter_id = d.non_striker_id
        """,
    ),
    Check(
        "eleven_players_per_side",
        "Each side names exactly 11 starting players (12 under the 2005-06 supersub rule).",
        """
        SELECT m.competition_id, mp.match_id, mp.team_season_id,
               count(*) FILTER (WHERE mp.selection = 'playing_xi') AS xi
        FROM match_players mp JOIN matches m USING (match_id)
        GROUP BY ALL
        HAVING xi <> 11 AND NOT (any_value(m.has_supersubs) AND xi = 12)
        """,
    ),
    Check(
        "impact_substitutes_only_under_the_rule",
        "Impact Player substitutes appear only in seasons where the rule applied.",
        """
        SELECT m.competition_id, mp.match_id, mp.player_id FROM match_players mp
        JOIN matches m USING (match_id) JOIN seasons s USING (season_id)
        WHERE mp.selection = 'impact_substitute' AND NOT s.impact_player_rule
        """,
    ),
    Check(
        "season_label_matches_match_year",
        "Cricsheet season labels agree with match dates (e.g. '2007/08' -> 2008).",
        """
        SELECT competition_id, season_id, year, cricsheet_label FROM seasons
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
        SELECT any_value(m.competition_id) AS competition_id, d.match_id, d.innings_no,
               d.over_no, count(*) AS legal_balls
        FROM deliveries d JOIN innings i USING (match_id, innings_no)
        JOIN matches m USING (match_id)
        WHERE d.is_legal
        GROUP BY ALL
        HAVING count(*) > 6
           AND (any_value(i.miscounted_overs) IS NULL
                OR json_extract(any_value(i.miscounted_overs), '$."' || d.over_no || '"') IS NULL)
        """,
        severity="warning",
    ),
)


def run_checks(
    con: duckdb.DuckDBPyConnection, lenient: frozenset[str] = frozenset(), sample_size: int = 5
) -> list[CheckResult]:
    """Run every check; violations in ``lenient`` competitions become notes."""
    results = []
    for check in CHECKS:
        relation = con.sql(check.sql)
        columns = relation.columns
        rows = [dict(zip(columns, row, strict=True)) for row in relation.fetchall()]
        strict = [r for r in rows if r.get("competition_id") not in lenient]
        noted = [r for r in rows if r.get("competition_id") in lenient]
        notes: dict[str, int] = {}
        noted_ids: dict[str, set[int]] = {}
        for r in noted:
            notes[str(r["competition_id"])] = notes.get(str(r["competition_id"]), 0) + 1
            if r.get("match_id"):
                noted_ids.setdefault(str(r["competition_id"]), set()).add(int(r["match_id"]))
        results.append(
            CheckResult(
                id=check.id,
                description=check.description,
                severity=check.severity,
                violations=len(strict),
                sample=strict[:sample_size],
                notes=dict(sorted(notes.items())),
                notes_sample=noted[:sample_size],
                notes_match_ids={k: sorted(v) for k, v in sorted(noted_ids.items())},
                match_ids=sorted({int(r["match_id"]) for r in strict if r.get("match_id")}),
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
        SELECT m.match_date, m.outcome_type, w.team_id, m.win_by_runs, m.win_by_wickets,
               m.win_method, m.decided_by_super_over, m.win_by_innings
        FROM matches m LEFT JOIN team_seasons w ON w.team_season_id = m.winner_id
        WHERE m.match_id = ?
        """,
        [golden.match_id],
    ).fetchone()
    if row is None:
        return GoldenResultRow(golden.match_id, golden.description, ["match not in warehouse"])
    date, outcome, winner, by_runs, by_wickets, method, super_over, by_innings = row

    def expect(label: str, actual: object, expected: object) -> None:
        if expected is not None and actual != expected:
            problems.append(f"{label}: expected {expected!r}, got {actual!r}")

    expect("date", date, golden.date)
    result = golden.result
    if result.draw:
        expect("outcome", outcome, "draw")
    elif result.tie:
        expect("outcome", outcome, "tie")
        expect("decided by super over", super_over, True)
        expect("super-over winner", winner, result.super_over_winner)
    else:
        expect("outcome", outcome, "win")
        expect("winner", winner, result.winner)
        expect("win by runs", by_runs, result.by_runs)
        expect("win by wickets", by_wickets, result.by_wickets)
        expect("method", method, result.method)
        expect("win by innings", by_innings, result.by_innings)

    innings = con.execute(
        """
        SELECT i.innings_no, t.team_id, i.runs, i.wickets, i.target_runs, i.target_overs
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

    def failing_match_ids(self) -> set[int]:
        """Matches behind every failure; a failure tied to no match is reported as -1."""
        ids: set[int] = set()
        for check in self.checks:
            if check.severity == "error" and not check.passed:
                ids.update(check.match_ids or [-1])
        ids.update(g.match_id for g in self.golden if not g.passed)
        return ids


def validate(
    warehouse: Path, config_dir: Path | None = None, *, require_all_golden: bool = True
) -> ValidationReport:
    """Run every check. With ``require_all_golden`` a golden match missing from the
    warehouse fails; test fixtures that hold a subset of matches turn it off."""
    lenient = frozenset(c.id for c in load_competitions(config_dir).competitions if not c.strict)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        golden_config = load_golden_matches(config_dir)
        present = {r[0] for r in con.execute("SELECT match_id FROM matches").fetchall()}
        built = {
            r[0] for r in con.execute("SELECT DISTINCT competition_id FROM matches").fetchall()
        }
        golden = [
            check_golden(con, g)
            for g in golden_config.matches
            if g.competition in built and (require_all_golden or g.match_id in present)
        ]
        return ValidationReport(checks=run_checks(con, lenient), golden=golden)
    finally:
        con.close()
