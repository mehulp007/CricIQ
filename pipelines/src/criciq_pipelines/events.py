"""Series and tournaments of the international competitions (Tests, ODIs, T20Is).

Cricsheet records each match's event: its name ("The Ashes", "India tour of
Australia", "ICC Cricket World Cup"), match number, stage and group. Matches of
one event less than ``GAP_DAYS`` apart are one series or tournament, where "one
event" is one major tournament whatever Cricsheet called it that year
(``config/events.yaml``), else one event name, else (for the few matches without
a name) one pair of sides. An event between two sides is a **series**; between
more, a **tournament**.

Tables, in the serving databases of national competitions only:

- ``events``: one row per series or tournament: its name, dates, sides, the
  score (each side's wins, and draws, ties without a winner and no results) and,
  for a tournament, the winner and loser of its final when the final is in the
  data. ``missing`` counts matches a series' numbering shows are not in the data
  (often abandoned without a ball bowled).
- ``event_matches``: the event of each match, and its round: a group, a later
  stage ("Super Sixes"), or a knockout ("Semi Final", "Final").
- ``event_standings``: the table of every round of a tournament: played, won,
  lost, tied, no result, points (two for a win, one for a tie or no result) and
  net run rate, ordered by points, then net run rate, then wins.

Where Cricsheet labels no groups, the matches outside the knockouts are split
into the groups of sides that played each other: four pools of three in the 2004
Champions Trophy, one league of ten at the 2019 World Cup. Matches never started
are not in Cricsheet, so a table can miss the points of a washed-out fixture.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import duckdb

from criciq_pipelines.reference import EventsConfig, Tournament

EVENT_TABLES = ("events", "event_matches", "event_standings")

# Matches of one event further apart than this are separate series or tournaments.
GAP_DAYS = 45
# No bilateral series is longer: higher match numbers belong to a longer league.
MAX_SERIES_MATCHES = 7

EVENTS_DDL = """
CREATE TABLE events (
    event_id      VARCHAR PRIMARY KEY,
    name          VARCHAR NOT NULL,
    season        VARCHAR NOT NULL,
    kind          VARCHAR NOT NULL,
    tournament_id VARCHAR,
    named         BOOLEAN NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    matches       INTEGER NOT NULL,
    missing       INTEGER NOT NULL,
    teams         VARCHAR[] NOT NULL,
    wins          INTEGER[] NOT NULL,
    drawn         INTEGER NOT NULL,
    tied          INTEGER NOT NULL,
    no_result     INTEGER NOT NULL,
    champion_id   VARCHAR,
    runner_up_id  VARCHAR
);
CREATE TABLE event_matches (
    match_id      BIGINT PRIMARY KEY,
    event_id      VARCHAR NOT NULL,
    round         VARCHAR,
    round_order   INTEGER,
    knockout      BOOLEAN NOT NULL,
    match_number  INTEGER
);
CREATE TABLE event_standings (
    event_id      VARCHAR NOT NULL,
    round         VARCHAR NOT NULL,
    round_order   INTEGER NOT NULL,
    position      INTEGER NOT NULL,
    franchise_id  VARCHAR NOT NULL,
    played        INTEGER NOT NULL,
    won           INTEGER NOT NULL,
    lost          INTEGER NOT NULL,
    tied          INTEGER NOT NULL,
    no_result     INTEGER NOT NULL,
    points        INTEGER NOT NULL,
    nrr           DOUBLE
);
"""

# The serving database's matches with their Cricsheet event (from the full warehouse,
# attached as ``ev``: the serving copy keeps the v1 columns only).
MATCHES_SQL = """
SELECT m.match_id, m.match_date, m.end_date, m.match_number, m.stage, m.outcome_type,
       ta.franchise_id AS team1, tb.franchise_id AS team2, tw.franchise_id AS winner,
       e.event_name, e.event_group
FROM matches m
JOIN team_seasons ta ON ta.team_season_id = m.team1_id
JOIN team_seasons tb ON tb.team_season_id = m.team2_id
LEFT JOIN team_seasons tw ON tw.team_season_id = m.winner_id
LEFT JOIN ev.matches e USING (match_id)
ORDER BY m.match_date, m.match_id
"""

NRR_SQL = """
SELECT match_id, franchise_id, nrr_runs_for, nrr_balls_for, nrr_runs_against, nrr_balls_against
FROM team_matches
"""


@dataclass(frozen=True)
class Match:
    match_id: int
    date: dt.date
    end_date: dt.date
    number: int | None
    stage: str
    outcome: str
    teams: tuple[str, str]
    winner: str | None
    event_name: str | None
    group: str | None

    @property
    def knockout(self) -> bool:
        return is_knockout(self.stage)


@dataclass
class Event:
    key: tuple[str, ...]
    tournament: Tournament | None
    matches: list[Match] = field(default_factory=list)

    @property
    def teams(self) -> list[str]:
        return sorted({t for m in self.matches for t in m.teams})

    @property
    def kind(self) -> str:
        return "series" if len(self.teams) <= 2 else "tournament"


@dataclass(frozen=True)
class StandingRow:
    round: str
    round_order: int
    franchise_id: str
    played: int
    won: int
    lost: int
    tied: int
    no_result: int
    points: int
    nrr: float | None


def is_knockout(stage: str) -> bool:
    """Semi-finals, finals, play-offs, qualifiers and eliminators (not "Super Sixes")."""
    s = stage.lower()
    return (
        "final" in s
        or "play-off" in s
        or "playoff" in s
        or s.startswith("qualifier")
        or s == "eliminator"
    )


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    plain = plain.replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def season_label(start: dt.date, end: dt.date) -> str:
    """ "2005", or "2020/21" for an event across the new year."""
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}/{str(end.year)[2:]}"


def group_events(
    matches: list[Match], competition: str, config: EventsConfig, gap_days: int = GAP_DAYS
) -> list[Event]:
    """Matches of one event (tournament, name or pair of sides) less than ``gap_days``
    apart, in order of their first match."""

    def key(m: Match) -> tuple[tuple[str, ...], Tournament | None]:
        tournament = config.tournament_of(competition, m.event_name)
        if tournament is not None:
            return ("tournament", tournament.id), tournament
        if m.event_name is not None:
            return ("name", m.event_name), None
        return ("pair", *sorted(m.teams)), None

    by_key: dict[tuple[str, ...], list[Match]] = {}
    tournaments: dict[tuple[str, ...], Tournament | None] = {}
    for m in matches:
        k, tournament = key(m)
        by_key.setdefault(k, []).append(m)
        tournaments[k] = tournament
    events: list[Event] = []
    for k, found in by_key.items():
        current: Event | None = None
        last_day: dt.date | None = None
        for m in sorted(found, key=lambda x: (x.date, x.match_id)):
            if current is None or last_day is None or (m.date - last_day).days > gap_days:
                current = Event(k, tournaments[k])
                events.append(current)
            current.matches.append(m)
            last_day = max(last_day or m.end_date, m.end_date)
    return sorted(events, key=lambda e: (e.matches[0].date, e.matches[0].match_id))


def event_name(event: Event, team_names: dict[str, str]) -> str:
    if event.tournament is not None:
        return event.tournament.name
    first = event.matches[0]
    if first.event_name is not None:
        return first.event_name
    a, b = event.teams[0], event.teams[-1]
    return f"{team_names.get(a, a)} v {team_names.get(b, b)}"


def event_season(event: Event) -> str:
    """A tournament by the year of its final (its last match); a series by its dates."""
    start, end = event.matches[0].date, max(m.end_date for m in event.matches)
    if event.tournament is not None:
        return str(end.year)
    return season_label(start, end)


def _components(matches: list[Match]) -> list[list[Match]]:
    """Matches split into groups of sides that played each other, by first match."""
    parent: dict[str, str] = {}

    def find(t: str) -> str:
        parent.setdefault(t, t)
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t

    for m in matches:
        a, b = find(m.teams[0]), find(m.teams[1])
        if a != b:
            parent[b] = a
    groups: dict[str, list[Match]] = {}
    for m in matches:
        groups.setdefault(find(m.teams[0]), []).append(m)
    return sorted(groups.values(), key=lambda g: (g[0].date, g[0].match_id))


def rounds(event: Event) -> dict[int, tuple[str | None, int]]:
    """Each match's round and the round's order in the event (knockouts last).

    Labelled groups are named by Cricsheet's label ("Group A") or the edition's
    names; other stages by the stage ("Super Sixes"); the remaining matches by the
    edition's name for them, or as the league stage (one group), pools (several),
    or the first or second round around labelled groups. A series has no rounds.
    """
    found: dict[int, tuple[str | None, int]] = {}
    if event.kind == "series":
        return {m.match_id: (m.stage if m.knockout else None, 0) for m in event.matches}
    edition = None
    if event.tournament is not None:
        year = max(m.end_date for m in event.matches).year
        edition = event.tournament.editions.get(year)
    labelled: list[tuple[str, Match]] = []
    staged: list[tuple[str, Match]] = []
    rest: list[Match] = []
    knockouts: list[Match] = []
    for m in event.matches:
        if m.knockout:
            knockouts.append(m)
        elif m.group is not None:
            name = edition.groups.get(m.group) if edition else None
            labelled.append((name or f"Group {m.group}", m))
        elif m.stage != "League":
            staged.append((m.stage, m))
        else:
            rest.append(m)
    named: list[tuple[str, Match]] = [*labelled, *staged]
    if rest:
        pieces = _components(rest)
        first_labelled = min((m.date for _, m in labelled), default=None)
        for i, piece in enumerate(pieces, start=1):
            if edition and edition.ungrouped:
                label = edition.ungrouped if len(pieces) == 1 else f"{edition.ungrouped} {i}"
            elif len(pieces) > 1:
                label = f"Pool {i}"
            elif first_labelled is None:
                label = "League stage"
            else:
                label = "First round" if piece[0].date < first_labelled else "Second round"
            named.extend((label, m) for m in piece)
    starts: dict[str, dt.date] = {}
    for label, m in named:
        starts[label] = min(starts.get(label, m.date), m.date)
    order = {label: i for i, label in enumerate(sorted(starts, key=lambda x: (starts[x], x)))}
    for label, m in named:
        found[m.match_id] = (label, order[label])
    # Knockouts after every group, each stage in order of its first match.
    first_of: dict[str, dt.date] = {}
    for m in knockouts:
        first_of[m.stage] = min(first_of.get(m.stage, m.date), m.date)
    stages = sorted(first_of, key=lambda x: (first_of[x], x))
    for m in knockouts:
        found[m.match_id] = (m.stage, len(order) + stages.index(m.stage))
    return found


def standings(
    event: Event,
    match_rounds: dict[int, tuple[str | None, int]],
    nrr: dict[tuple[int, str], tuple[int | None, int | None, int | None, int | None]],
) -> list[StandingRow]:
    """The table of every round of a tournament (none for a series or the knockouts)."""
    if event.kind == "series":
        return []
    tally: dict[tuple[str, int, str], Counter[str]] = {}
    for m in event.matches:
        label, order = match_rounds[m.match_id]
        if m.knockout or label is None:
            continue
        for team in m.teams:
            c = tally.setdefault((label, order, team), Counter())
            c["played"] += 1
            if m.outcome == "no_result":
                c["no_result"] += 1
            elif m.winner == team:
                c["won"] += 1
            elif m.winner is not None:
                c["lost"] += 1
            elif m.outcome == "tie":
                c["tied"] += 1
            sums = nrr.get((m.match_id, team))
            if sums is not None and None not in sums:
                for name, value in zip(("rf", "bf", "ra", "ba"), sums, strict=True):
                    c[name] += int(value or 0)
    rows = []
    for (label, order, team), c in tally.items():
        rate = (
            round(6 * c["rf"] / c["bf"] - 6 * c["ra"] / c["ba"], 3)
            if c["bf"] > 0 and c["ba"] > 0
            else None
        )
        rows.append(
            StandingRow(
                label,
                order,
                team,
                c["played"],
                c["won"],
                c["lost"],
                c["tied"],
                c["no_result"],
                2 * c["won"] + c["tied"] + c["no_result"],
                rate,
            )
        )
    return sorted(
        rows,
        key=lambda r: (
            r.round_order,
            r.round,
            -r.points,
            -(r.nrr if r.nrr is not None else -1e9),
            -r.won,
            r.franchise_id,
        ),
    )


def final_of(event: Event) -> Match | None:
    finals = [m for m in event.matches if m.stage.lower() == "final"]
    return finals[-1] if finals else None


def missing_matches(event: Event) -> int:
    """Matches a series' numbering shows are not in the data: 0 without numbers, or
    where they run beyond any series (a league's numbering, such as the World Cricket
    League's, continues across its rounds)."""
    if event.kind != "series":
        return 0
    numbers = {m.number for m in event.matches if m.number is not None}
    if not numbers or max(numbers) > MAX_SERIES_MATCHES:
        return 0
    return max(0, max(numbers) - len(numbers))


def build_event_tables(
    con: duckdb.DuckDBPyConnection, competition: str, config: EventsConfig
) -> None:
    """Create the event tables from the serving tables and the attached full warehouse
    (``ev``); ``team_matches`` must exist (it holds the net run rate credits)."""
    matches = [
        Match(
            match_id=int(r[0]),
            date=r[1],
            end_date=r[2],
            number=r[3],
            stage=r[4] or "League",
            outcome=r[5],
            teams=(r[6], r[7]),
            winner=r[8],
            event_name=r[9],
            group=r[10],
        )
        for r in con.execute(MATCHES_SQL).fetchall()
    ]
    team_names = dict(con.execute("SELECT franchise_id, name FROM franchises").fetchall())
    nrr = {(int(r[0]), r[1]): (r[2], r[3], r[4], r[5]) for r in con.execute(NRR_SQL).fetchall()}
    con.execute(EVENTS_DDL)
    used: Counter[str] = Counter()
    event_rows, match_rows, standing_rows = [], [], []
    for event in group_events(matches, competition, config):
        name = event_name(event, team_names)
        season = event_season(event)
        base = slug(f"{season} {name}")
        used[base] += 1
        event_id = base if used[base] == 1 else f"{base}-{used[base]}"
        teams = event.teams
        wins = [sum(1 for m in event.matches if m.winner == t) for t in teams]
        champion = runner_up = None
        if event.tournament is not None or event.kind == "tournament":
            final = final_of(event)
            if final is not None and final.winner is not None:
                champion = final.winner
                runner_up = next(t for t in final.teams if t != final.winner)
        event_rows.append(
            (
                event_id,
                name,
                season,
                event.kind,
                event.tournament.id if event.tournament else None,
                event.key[0] != "pair",
                event.matches[0].date,
                max(m.end_date for m in event.matches),
                len(event.matches),
                missing_matches(event),
                teams,
                wins,
                sum(1 for m in event.matches if m.outcome == "draw"),
                sum(1 for m in event.matches if m.outcome == "tie" and m.winner is None),
                sum(1 for m in event.matches if m.outcome == "no_result"),
                champion,
                runner_up,
            )
        )
        match_rounds = rounds(event)
        for m in event.matches:
            label, order = match_rounds[m.match_id]
            match_rows.append((m.match_id, event_id, label, order, m.knockout, m.number))
        positions: Counter[tuple[str, int]] = Counter()
        for row in standings(event, match_rounds, nrr):
            positions[(row.round, row.round_order)] += 1
            standing_rows.append(
                (
                    event_id,
                    row.round,
                    row.round_order,
                    positions[(row.round, row.round_order)],
                    row.franchise_id,
                    row.played,
                    row.won,
                    row.lost,
                    row.tied,
                    row.no_result,
                    row.points,
                    row.nrr,
                )
            )
    if event_rows:
        con.executemany(f"INSERT INTO events VALUES ({', '.join('?' * 17)})", event_rows)
    if match_rows:
        con.executemany("INSERT INTO event_matches VALUES (?, ?, ?, ?, ?, ?)", match_rows)
    if standing_rows:
        con.executemany(
            f"INSERT INTO event_standings VALUES ({', '.join('?' * 12)})", standing_rows
        )


@dataclass(frozen=True)
class EventCheck:
    description: str
    problems: list[str]
    # False when the data does not cover the event (the final or a match is missing).
    covered: bool = True

    @property
    def passed(self) -> bool:
        return not self.problems


def check_events(
    con: duckdb.DuckDBPyConnection, competition: str, config: EventsConfig
) -> list[EventCheck]:
    """Compare the events built with the known results in ``config/events.yaml``.

    A tournament is checked when its final is in the data, a series when the data
    has all its matches; an event the data does not cover passes, marked
    ``covered=False`` (the full-data tests require every one to be covered).
    """
    checks: list[EventCheck] = []
    for want in config.results:
        if want.competition != competition:
            continue
        description = want.description
        if want.tournament is not None:
            found = con.execute(
                """
                SELECT event_id, champion_id,
                       EXISTS (SELECT 1 FROM event_matches x JOIN matches m USING (match_id)
                               WHERE x.event_id = e.event_id AND lower(m.stage) = 'final')
                FROM events e WHERE tournament_id = ? AND year(end_date) = ?
                """,
                [want.tournament, want.year],
            ).fetchall()
            if not found or not found[0][2]:
                checks.append(EventCheck(description, [], covered=False))
                continue
            champion = found[0][1]
            problems = (
                [] if champion == want.champion else [f"champion {champion}, known {want.champion}"]
            )
            checks.append(EventCheck(description, problems))
            continue
        sides = sorted(want.series or ())
        found = con.execute(
            """
            SELECT teams, wins, drawn, matches FROM events
            WHERE teams = ? AND kind = 'series' AND year(start_date) = ?
            """,
            [sides, want.year],
        ).fetchall()
        if len(found) > 1:
            checks.append(EventCheck(description, ["several series of these sides that year"]))
            continue
        if not found or found[0][3] != want.matches:
            checks.append(EventCheck(description, [], covered=False))
            continue
        teams, wins, drawn, _ = found[0]
        got = {t: w for t, w in zip(teams, wins, strict=True) if w}
        problems = []
        if got != {t: w for t, w in want.wins.items() if w}:
            problems.append(f"wins {got}, known {want.wins}")
        if drawn != want.drawn:
            problems.append(f"{drawn} drawn, known {want.drawn}")
        checks.append(EventCheck(description, problems))
    return checks
