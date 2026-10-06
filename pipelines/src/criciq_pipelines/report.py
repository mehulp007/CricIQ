"""Generate the committed data-quality reports.

``docs/data-quality-report.md`` covers the IPL in detail and every competition
in summary; ``docs/data-quality/<competition>.md`` covers one other competition
in the same detail. Reports are deterministic for a given data version (no
timestamps), so they only change in git when the data or the checks change.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import duckdb

from criciq_pipelines.reference import Competition
from criciq_pipelines.scope import build_scope
from criciq_pipelines.validation import ValidationReport

# Competitions of these formats have a report of their own (the IPL's is the main one).
REPORTED_FORMATS = ("T20",)

# Sample thresholds used to define "players with a meaningful IPL sample".
MIN_BALLS_FACED = 100
MIN_BALLS_BOWLED = 120


def _table(headers: list[str], rows: list[tuple[Any, ...]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(lines)


def _pct(part: int, whole: int) -> str:
    return f"{part:,} / {whole:,} ({100 * part / whole:.1f}%)" if whole else "0 / 0"


def render_report(
    warehouse: Path, validation: ValidationReport, everything: Path | None = None
) -> str:
    """The IPL report from ``warehouse``, with an all-competitions section from
    ``everything`` (the full warehouse) when given."""
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        text = _render(con, validation)
    finally:
        con.close()
    if everything is None or not everything.exists():
        return text
    full = duckdb.connect(str(everything), read_only=True)
    try:
        return text + "\n" + _competitions_section(full, validation) + "\n"
    finally:
        full.close()


def report_path_for(main_report: Path, competition_id: str) -> Path:
    """Where a competition's report goes, beside the main report."""
    return main_report.parent / "data-quality" / f"{competition_id.lower()}.md"


def render_competition_report(
    everything: Path, validation: ValidationReport, competition: Competition
) -> str:
    """One competition's report, from the full warehouse ``everything``."""
    with tempfile.TemporaryDirectory(prefix="criciq-report-") as work:
        scoped = Path(work) / "scope.duckdb"
        build_scope(everything, competition.id, scoped)
        con = duckdb.connect(str(scoped), read_only=True)
        try:
            text = _render(con, validation, competition)
        finally:
            con.close()
    full = duckdb.connect(str(everything), read_only=True)
    try:
        return text + "\n" + _competition_extras(full, competition) + "\n"
    finally:
        full.close()


# The Contents table: (label, table).
_ENTITIES: tuple[tuple[str, str], ...] = (
    ("seasons", "seasons"),
    ("franchises", "franchises"),
    ("team_seasons", "team_seasons"),
    ("venues", "venues"),
    ("players", "players"),
    ("matches", "matches"),
    ("innings", "innings"),
    ("deliveries", "deliveries"),
    ("wickets", "wickets"),
    ("match_players", "match_players"),
    ("substitutions", "substitutions"),
)


def _render(
    con: duckdb.DuckDBPyConnection,
    validation: ValidationReport,
    competition: Competition | None = None,
) -> str:
    """The detailed report of a v1-shaped warehouse: the IPL's, or ``competition``'s."""

    def one(sql: str) -> Any:
        row = con.execute(sql).fetchone()
        return None if row is None else row[0]

    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    present = {int(r[0]) for r in con.execute("SELECT match_id FROM matches").fetchall()}
    status = "PASS" if validation.passed else "FAIL"
    if competition is None:
        title = "# Data Quality Report"
        source = "IPL ball-by-ball JSON"
        entities = _ENTITIES
        season = "s.year"
        golden = validation.golden
    else:
        title = f"# Data Quality Report: {competition.name}"
        source = f"{competition.short_name} ball-by-ball JSON"
        noted = sum(c.notes.get(competition.id, 0) for c in validation.checks)
        if noted:
            status += f" ({noted} {'note' if noted == 1 else 'notes'} on the source, below)"
        # The copy keeps every curated ground; count the ones this competition used.
        renamed = {
            "franchises": ("teams", "franchises"),
            "venues": ("venues", "venues WHERE venue_id IN (SELECT venue_id FROM matches)"),
        }
        entities = tuple(renamed.get(t, (t, t)) for _, t in _ENTITIES)
        # The BBL names a season by the years it spans ("2023/24").
        season = "any_value(s.cricsheet_label)" if competition.season_spans_new_year else "s.year"
        golden = [g for g in validation.golden if g.match_id in present]
    sections: list[str] = [
        title,
        "",
        "_Generated by `criciq-data report`. Do not edit by hand._",
        "",
        f"- **Data version:** `{meta['data_version']}`",
        f"- **Source:** [Cricsheet](https://cricsheet.org) {source} (ODC-BY 1.0)",
        f"- **Overall status:** {status}",
        "",
        "## Contents",
        "",
        _table(
            ["Entity", "Rows"],
            [(label, f"{one(f'SELECT count(*) FROM {table}'):,}") for label, table in entities],
        ),
        "",
        "## Coverage by season",
        "",
        _table(
            [
                "Season",
                "Matches",
                "Wins",
                "Ties",
                "No result",
                "D/L",
                "Deliveries",
                "Avg 1st-innings score",
            ],
            con.execute(
                f"""
                SELECT {season},
                       count(DISTINCT m.match_id),
                       count(DISTINCT m.match_id) FILTER (WHERE m.outcome_type = 'win'),
                       count(DISTINCT m.match_id) FILTER (WHERE m.outcome_type = 'tie'),
                       count(DISTINCT m.match_id) FILTER (WHERE m.outcome_type = 'no_result'),
                       count(DISTINCT m.match_id) FILTER (WHERE m.win_method IS NOT NULL),
                       (SELECT count(*) FROM deliveries d JOIN matches m2 USING (match_id)
                        WHERE m2.season_id = s.season_id),
                       round(avg(i.runs) FILTER (WHERE i.innings_no = 1
                                                   AND m.outcome_type <> 'no_result'
                                                   AND m.win_method IS NULL), 1)
                FROM seasons s JOIN matches m USING (season_id)
                LEFT JOIN innings i USING (match_id)
                GROUP BY s.year, s.season_id ORDER BY s.year
                """
            ).fetchall(),
        ),
        "",
        "Average first-innings scores exclude no-results and rain-affected (D/L) matches.",
        "",
        "## Validation checks",
        "",
        "Schema constraints (primary keys, foreign keys, value domains) are enforced when the",
        "warehouse loads. The checks below cover cricket logic a schema cannot express.",
        "",
        _checks_section(validation, competition),
        "",
        "## Golden matches",
        "",
        "Independently known scorecards that the warehouse must reproduce exactly",
        "(`config/golden_matches.yaml`).",
        "",
        _table(
            ["Match", "Description", "Status"],
            [
                (
                    g.match_id,
                    g.description,
                    "pass" if g.passed else "FAIL: " + "; ".join(g.mismatches),
                )
                for g in golden
            ],
        )
        if golden
        else "None for this competition yet.",
        "",
        "## Recorded anomalies",
        "",
        "These are faithful records of what happened on the field, kept as-is and handled",
        "explicitly downstream.",
        "",
        _table(
            ["Anomaly", "Count", "Handling"],
            [
                (
                    "Overs miscounted by the umpire (5 or 7 legal balls), as recorded by Cricsheet",
                    one("""SELECT coalesce(sum(len(json_keys(miscounted_overs))), 0)
                           FROM innings WHERE miscounted_overs IS NOT NULL"""),
                    "Legal balls are counted, never assumed to be 6 per over",
                ),
                (
                    "Rain-affected results (D/L)",
                    one("SELECT count(*) FROM matches WHERE win_method IS NOT NULL"),
                    "Chase uses the revised target and overs",
                ),
                (
                    "Tied matches decided by super over",
                    one("SELECT count(*) FROM matches WHERE decided_by_super_over"),
                    "Super-over innings flagged `is_super_over`; excluded from models",
                ),
                (
                    "No-result matches",
                    one("SELECT count(*) FROM matches WHERE outcome_type = 'no_result'"),
                    "Kept for display; excluded from outcome models",
                ),
                (
                    "Retired hurt",
                    one("SELECT count(*) FROM wickets WHERE kind = 'retired hurt'"),
                    "Not a dismissal: does not count toward team wickets",
                ),
                (
                    "Penalty runs awarded",
                    one("SELECT count(*) FROM deliveries WHERE extras_penalty > 0"),
                    "Counted in extras and team total",
                ),
                (
                    "Fours run (not boundaries)",
                    one("""SELECT count(*) FROM deliveries
                           WHERE runs_batter = 4 AND NOT is_four"""),
                    "Excluded from boundary counts",
                ),
                (
                    "Impact Player substitutions",
                    one("SELECT count(*) FROM substitutions WHERE reason = 'impact_player'"),
                    "Substitute flagged in `match_players.selection`",
                ),
                (
                    "Concussion substitutions",
                    one(
                        "SELECT count(*) FROM substitutions WHERE reason = 'concussion_substitute'"
                    ),
                    "Substitute flagged in `match_players.selection`",
                ),
                (
                    "Mid-over bowler replacements",
                    one("SELECT count(*) FROM substitutions WHERE kind = 'role'"),
                    "Recorded in `substitutions`",
                ),
            ],
        ),
        "",
        _attribute_section(con),
    ]
    return "\n".join(sections) + "\n"


def _checks_section(validation: ValidationReport, competition: Competition | None) -> str:
    if competition is None:
        return "\n".join(
            [
                "Violations count curated competitions (the IPL), where any fails the build. "
                "Elsewhere",
                "the source has known quirks, reported as notes (see All competitions below).",
                "",
                _table(
                    ["Check", "Severity", "Status", "Violations", "Notes elsewhere", "Rule"],
                    [
                        (
                            f"`{c.id}`",
                            c.severity,
                            "pass" if c.passed else ("FAIL" if c.severity == "error" else "warn"),
                            c.violations,
                            ", ".join(f"{k} {v}" for k, v in c.notes.items()) or "",
                            c.description,
                        )
                        for c in validation.checks
                    ],
                ),
            ]
        )
    cid = competition.id
    noted = [c for c in validation.checks if c.notes.get(cid)]
    lines = [
        "Outside curated competitions, what a check finds is reported as a note on the source:",
        "the match is kept as Cricsheet records it, and anything that relies on the rule (a",
        "model's chase target, for example) handles the exception itself.",
        "",
        _table(
            ["Check", "Severity", "Status", "Notes", "Rule"],
            [
                (
                    f"`{c.id}`",
                    c.severity,
                    "note" if c.notes.get(cid) else "pass",
                    c.notes.get(cid, 0),
                    c.description,
                )
                for c in validation.checks
            ],
        ),
    ]
    if noted:
        lines += ["", "The matches behind each note:", ""]
        lines += [
            f"- `{c.id}`: " + ", ".join(str(m) for m in c.notes_match_ids.get(cid, []))
            for c in noted
        ]
    return "\n".join(lines)


def _competition_extras(con: duckdb.DuckDBPyConnection, competition: Competition) -> str:
    """From the full warehouse: the competition's teams, their players' attributes,
    quarantined matches and grounds added automatically."""
    con.execute("SET VARIABLE competition = ?", [competition.id])
    teams = con.execute(
        f"""
        WITH played AS (
            SELECT ts.team_id, count(DISTINCT m.match_id) AS matches
            FROM matches m
            JOIN team_seasons ts ON ts.team_season_id IN (m.team1_id, m.team2_id)
            WHERE m.competition_id = getvariable('competition')
            GROUP BY ALL
        ),
        balls AS (
            SELECT d.batter_id, d.bowler_id, bt.team_id AS batting_team, bw.team_id AS bowling_team
            FROM deliveries d
            JOIN matches m USING (match_id)
            JOIN team_seasons bt ON bt.team_season_id = d.batting_team_id
            JOIN team_seasons bw ON bw.team_season_id = d.bowling_team_id
            WHERE m.competition_id = getvariable('competition')
        ),
        batters AS (
            SELECT batting_team AS team_id, batter_id AS player_id FROM balls
            GROUP BY ALL HAVING count(*) >= {MIN_BALLS_FACED}
        ),
        bowlers AS (
            SELECT bowling_team AS team_id, bowler_id AS player_id FROM balls
            GROUP BY ALL HAVING count(*) >= {MIN_BALLS_BOWLED}
        ),
        hands AS (
            SELECT b.team_id, count(*) AS batters, count(p.batting_hand) AS with_hand
            FROM batters b JOIN players p USING (player_id) GROUP BY ALL
        ),
        styles AS (
            SELECT b.team_id, count(*) AS bowlers, count(p.bowling_type) AS with_type
            FROM bowlers b JOIN players p USING (player_id) GROUP BY ALL
        )
        SELECT t.team_id, t.name,
               ct.first_season || '-' || coalesce(ct.last_season::VARCHAR, ''),
               coalesce(p.matches, 0),
               CASE WHEN t.is_curated THEN 'curated' ELSE 'added' END,
               coalesce(h.with_hand, 0) || ' / ' || coalesce(h.batters, 0),
               coalesce(s.with_type, 0) || ' / ' || coalesce(s.bowlers, 0)
        FROM competition_teams ct JOIN teams t USING (team_id)
        LEFT JOIN played p USING (team_id)
        LEFT JOIN hands h USING (team_id)
        LEFT JOIN styles s USING (team_id)
        WHERE ct.competition_id = getvariable('competition')
        ORDER BY p.matches DESC NULLS LAST, t.team_id
        """
    ).fetchall()
    quarantined = con.execute(
        """
        SELECT match_id, rule, detail FROM quarantine
        WHERE competition_id = getvariable('competition') ORDER BY ALL
        """
    ).fetchall()
    grounds = con.execute(
        """
        SELECT v.venue_id, v.name, v.city, v.country, count(*) AS matches
        FROM matches m JOIN venues v USING (venue_id)
        WHERE m.competition_id = getvariable('competition') AND NOT v.is_curated
        GROUP BY ALL ORDER BY matches DESC, v.venue_id
        """
    ).fetchall()
    added = sum(1 for t in teams if t[4] == "added")
    origin = (
        f"Teams come from `config/teams/{competition.teams}.yaml` (names, and colours where "
        "the side has established ones)"
    )
    origin += (
        f"; {added} of {len(teams)} were added from Cricsheet's names and are listed for review."
        if added
        else ", all of them curated."
    )
    return "\n".join(
        [
            "## Teams",
            "",
            origin,
            "",
            "The last two columns count the team's players with a meaningful sample (batters",
            f"who faced {MIN_BALLS_FACED}+ balls, bowlers who bowled {MIN_BALLS_BOWLED}+) whose",
            "batting hand and bowling type are known. Wikipedia covers most players of the leagues",
            "and the full members but few associate nations' players, left unknown.",
            "",
            _table(
                ["Team", "Name", "Seasons", "Matches", "Source", "Batting hand", "Bowling type"],
                teams,
            ),
            "",
            "## Quarantined matches",
            "",
            "Matches with a source error that would break the warehouse's keys are left out:",
            "",
            _table(["Match", "Rule", "Detail"], quarantined) if quarantined else "None.",
            "",
            "## Grounds added automatically",
            "",
            "Grounds outside the curated `config/venues.yaml`, named from Cricsheet and placed",
            "with `config/venue_countries.yaml`:",
            "",
            _table(["Ground", "Name", "City", "Country", "Matches"], grounds)
            if grounds
            else "None.",
        ]
    )


def _competitions_section(con: duckdb.DuckDBPyConnection, validation: ValidationReport) -> str:
    """Every competition in the full warehouse: coverage, quarantine and notes."""
    notes: dict[str, int] = {}
    for check in validation.checks:
        for competition, count in check.notes.items():
            notes[competition] = notes.get(competition, 0) + count
    rows = con.execute(
        """
        WITH games AS (
            SELECT competition_id, min(s.year) || '-' || max(s.year) AS seasons,
                   count(*) AS matches
            FROM matches m JOIN seasons s USING (season_id, competition_id) GROUP BY ALL
        ),
        balls AS (
            SELECT m.competition_id, count(*) AS deliveries
            FROM deliveries d JOIN matches m USING (match_id) GROUP BY ALL
        ),
        sides AS (
            SELECT s.competition_id, count(DISTINCT ts.team_id) AS teams
            FROM team_seasons ts JOIN seasons s USING (season_id) GROUP BY ALL
        ),
        held AS (SELECT competition_id, count(*) AS quarantined FROM quarantine GROUP BY ALL)
        SELECT c.competition_id, c.name, c.format, g.seasons, g.matches,
               coalesce(b.deliveries, 0), coalesce(t.teams, 0), coalesce(h.quarantined, 0)
        FROM competitions c
        JOIN games g USING (competition_id)
        LEFT JOIN balls b USING (competition_id)
        LEFT JOIN sides t USING (competition_id)
        LEFT JOIN held h USING (competition_id)
        ORDER BY c.competition_id <> 'IPL', c.format, c.competition_id
        """
    ).fetchall()
    table_rows = [
        (cid, name, fmt, span, f"{n:,}", f"{balls:,}", teams, q, notes.get(cid, 0))
        for cid, name, fmt, span, n, balls, teams, q in rows
    ]
    quarantined = con.execute(
        "SELECT match_id, competition_id, rule, detail FROM quarantine ORDER BY ALL"
    ).fetchall()
    added = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE country IS NULL) FROM venues WHERE NOT is_curated"
    ).fetchone()
    assert added is not None
    return "\n".join(
        [
            "## All competitions",
            "",
            "The warehouse holds every competition in `config/competitions.yaml`; the sections",
            "above cover the IPL, which the site serves today. Cricsheet holds no matches",
            "involving Afghanistan, in any format, so Afghanistan's record is absent.",
            "",
            _table(
                [
                    "Competition",
                    "Name",
                    "Format",
                    "Seasons",
                    "Matches",
                    "Deliveries",
                    "Teams",
                    "Quarantined",
                    "Notes",
                ],
                table_rows,
            ),
            "",
            "Each T20 competition has a detailed report of its own: "
            + ", ".join(
                f"[{cid}](data-quality/{cid.lower()}.md)"
                for cid, _, fmt, *_ in table_rows
                if fmt in REPORTED_FORMATS and cid != "IPL"
            )
            + ".",
            "",
            "**Quarantined matches** have a source error that would break the warehouse's keys",
            "and are left out:",
            "",
            _table(["Match", "Competition", "Rule", "Detail"], quarantined)
            if quarantined
            else "None.",
            "",
            f"**Grounds added automatically:** {added[0]} grounds outside the curated",
            "`config/venues.yaml`, named from Cricsheet and placed with",
            f"`config/venue_countries.yaml`; {added[1]} without a country.",
        ]
    )


def _attribute_section(con: duckdb.DuckDBPyConnection) -> str:
    faced = "(SELECT count(*) FROM deliveries d WHERE d.batter_id = p.player_id)"
    bowled = "(SELECT count(*) FROM deliveries d WHERE d.bowler_id = p.player_id)"
    significant = f"""
        SELECT p.* FROM players p
        WHERE {faced} >= {MIN_BALLS_FACED} OR {bowled} >= {MIN_BALLS_BOWLED}
    """
    bowlers = f"SELECT p.* FROM players p WHERE {bowled} >= {MIN_BALLS_BOWLED}"

    def coverage(population: str, column: str) -> str:
        row = con.execute(
            f"SELECT count(*) FILTER (WHERE {column} IS NOT NULL), count(*) FROM ({population})"
        ).fetchone()
        assert row is not None
        return _pct(int(row[0]), int(row[1]))

    everyone = "SELECT * FROM players"
    rows = [
        (label, coverage(everyone, column), coverage(significant, column))
        for label, column in (
            ("Full name", "full_name"),
            ("Date of birth", "date_of_birth"),
            ("Country", "country"),
            ("Batting hand", "batting_hand"),
        )
    ]
    rows.append(
        (
            "Bowling type (pace/spin)",
            coverage(everyone, "bowling_type"),
            coverage(bowlers, "bowling_type") + " of bowlers",
        )
    )
    return "\n".join(
        [
            "## Player attributes",
            "",
            "Cricsheet identifies players but has no biographical attributes. These come from",
            "Wikidata (CC0) and English Wikipedia cricketer infoboxes (CC BY-SA 4.0), linked",
            "through ESPNcricinfo ids, plus a small set of documented manual overrides",
            "(`reference/player_attributes_overrides.csv`). Missing values are left empty rather",
            "than guessed.",
            "",
            f"Players with a meaningful sample: at least {MIN_BALLS_FACED} balls faced or "
            f"{MIN_BALLS_BOWLED} balls bowled.",
            "",
            _table(["Attribute", "All players", "Players with a meaningful sample"], rows),
        ]
    )
