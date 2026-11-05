"""Daily notes: a short, news-style note for every day matches ended, written from the data.

Each note is built only from the serving databases (no outside source, no model writing
text): every sentence comes from a fixed rule, and every figure in it is read from the
tables, so the same data always gives the same note. A day's matches come from every
served competition. For each match, in this order:

1. **Result**: who beat whom and how, where in the season or series, the innings totals,
   the top batter and bowler and the player of the match.
2. **Turning point**: the ball with the biggest change in win probability (``match_swings``,
   a model estimate), when it moved a side by at least ``MIN_SWING`` points.
3. **Match-winner**: the highest win probability added in the match (``player_wpa``).
4. **Milestones** reached in the match, within the competition's data: runs at every
   1,000 (500 in the leagues), wickets at every 50, appearances at every 50.
5. **Records**: an innings total, score, bowling figures or stand that went into the top 10
   of the competition's data so far (once it has ``MIN_HISTORY`` matches).
6. **Standings**: a league side's table position after the match, or a series score.

Matches beyond the day's ``FULL_MATCHES`` most notable carry only their result and any new
record. The output, ``notes.duckdb``, holds ``notes`` (one row per day), ``note_items`` and
``note_figures`` (the day's standout performers with their career totals before and after),
and is published like the serving databases (``criciq_core.publish``).
"""

from __future__ import annotations

import bisect
import datetime as dt
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from criciq_core.publish import current, publish

Log = Callable[[str], None]
Row = dict[str, Any]

NOTE_TABLES = ("notes", "note_items", "note_figures")
METHOD = (
    "Written automatically from CricIQ's ball-by-ball data (Cricsheet). Matches appear here "
    "once Cricsheet publishes them, usually a day or two after play. Win-probability figures "
    "are model estimates."
)
# The order competitions are listed in, and their names in a sentence.
ORDER = ("IPL", "BBL", "PSL", "CPL", "SA20", "T20I", "ODI", "TEST")
NOUNS = {"TEST": "Test"}
MIN_SWING = 0.10
MIN_WPA = 0.05
MIN_HISTORY = 30
MAX_MILESTONES = 2
TOP = 10
FULL_MATCHES = 6
FIGURE_ROWS = 6
DASH = chr(0x2013)


@dataclass(frozen=True)
class Source:
    competition_id: str
    path: Path

    @property
    def site(self) -> str:
        return self.competition_id.lower()

    @property
    def noun(self) -> str:
        return NOUNS.get(self.competition_id, self.competition_id)


@dataclass
class Item:
    kind: str
    title: str
    body: str
    why: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    score: int = 0


@dataclass
class Match:
    source: Source
    match_id: int
    match_order: int
    date: dt.date
    notability: int
    items: list[Item]
    figures: list[Row]


# --------------------------------------------------------------------------- words


def plural(n: int, word: str) -> str:
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }".replace(" ", "")


def article(word: str) -> str:
    return "an" if word[:1].upper() in "AEIOU" or word.startswith(("ODI", "8", "11")) else "a"


def overs(balls: int) -> str:
    whole, rest = divmod(balls, 6)
    return f"{whole}.{rest}" if rest else str(whole)


def score(runs: int, wickets: int) -> str:
    return str(runs) if wickets >= 10 else f"{runs}/{wickets}"


def batting(name: str, runs: int, balls: int, out: bool) -> str:
    return f"{name} {runs}{'' if out else '*'} ({balls})"


def possessive(name: str) -> str:
    """ "Punjab Kings'", "Virat Kohli's"."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def the(name: str) -> str:
    return name if name.lower().startswith("the ") else f"the {name}"


def sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


# --------------------------------------------------------------------------- reading


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: Iterable[Any] = ()) -> list[Row]:
    cursor = con.execute(sql, list(params))
    columns = [d[0] for d in cursor.description or []]
    return [dict(zip(columns, r, strict=True)) for r in cursor.fetchall()]


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}


class _Competition:
    """Everything the notes need from one serving database, read once."""

    def __init__(self, con: duckdb.DuckDBPyConnection, source: Source) -> None:
        self.con = con
        self.source = source
        self.tables = _tables(con)
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        self.data_version = str(meta.get("data_version", ""))
        self.pipeline_version = str(meta.get("pipeline_version", ""))
        spans = meta.get("season_spans_new_year") == "true"
        info = con.execute("SELECT format, team_type FROM competitions LIMIT 1").fetchone()
        assert info is not None
        self.format, self.team_type = str(info[0]), str(info[1])
        self.national = self.team_type == "national"
        self.limited = self.format != "Test"
        self.names = {
            r["player_id"]: r["name"]
            for r in _rows(con, "SELECT player_id, coalesce(full_name, name) AS name FROM players")
        }
        self.teams = {
            r["team_season_id"]: (r["franchise_id"], r["display_name"])
            for r in _rows(
                con, "SELECT team_season_id, franchise_id, display_name FROM team_seasons"
            )
        }
        self.franchises = {
            r["franchise_id"]: r["name"]
            for r in _rows(con, "SELECT franchise_id, name FROM franchises")
        }
        innings_win = (
            "m.win_by_innings" if "win_by_innings" in _columns(con, "matches") else "FALSE"
        )
        self.matches = _rows(
            con,
            f"""
            SELECT m.match_id, m.match_order, coalesce(m.end_date, m.match_date) AS end_date,
                   s.year AS season,
                   CASE WHEN ? THEN s.cricsheet_label ELSE s.year::VARCHAR END AS season_label,
                   m.stage, m.is_playoff, m.outcome_type, m.win_by_runs, m.win_by_wickets,
                   m.win_method, m.decided_by_super_over,
                   coalesce({innings_win}, FALSE) AS win_by_innings,
                   ms.team_a_id, ms.team_a_name, ms.team_b_id, ms.team_b_name,
                   ms.winner_id, ms.winner_name, ms.venue_name, ms.player_of_match
            FROM matches m
            JOIN seasons s USING (season_id)
            JOIN match_summaries ms USING (match_id)
            ORDER BY m.match_order, m.match_id
            """,
            [spans],
        )
        self.order = {m["match_id"]: m["match_order"] for m in self.matches}
        self.index = {m["match_id"]: i for i, m in enumerate(self.matches)}
        self.innings = self._group(
            """
            SELECT match_id, innings_no, batting_team_id, runs, wickets, legal_balls
            FROM innings WHERE NOT is_super_over ORDER BY match_id, innings_no
            """
        )
        self.top_batter = {
            r["match_id"]: r
            for r in _rows(
                con,
                """
                SELECT match_id, player_id, runs, balls, is_out FROM player_batting_innings
                QUALIFY row_number() OVER (
                    PARTITION BY match_id ORDER BY runs DESC, balls, player_id
                ) = 1
                """,
            )
        }
        self.top_bowler = {
            r["match_id"]: r
            for r in _rows(
                con,
                """
                SELECT match_id, player_id, wickets, runs, balls FROM player_bowling_innings
                WHERE balls > 0
                QUALIFY row_number() OVER (
                    PARTITION BY match_id ORDER BY wickets DESC, runs, balls, player_id
                ) = 1
                """,
            )
        }
        self.batting = self._group(
            """
            SELECT match_id, player_id, team_id, runs, balls, is_out FROM player_batting_innings
            ORDER BY match_id, runs DESC, balls, player_id
            """
        )
        self.bowling = self._group(
            """
            SELECT match_id, player_id, team_id, wickets, runs, balls FROM player_bowling_innings
            WHERE balls > 0
            ORDER BY match_id, wickets DESC, runs, balls, player_id
            """
        )
        self.swings = self._swings()
        self.wpa = self._wpa()
        self.careers = self._careers()

    def _group(self, sql: str) -> dict[int, list[Row]]:
        found: dict[int, list[Row]] = {}
        for r in _rows(self.con, sql):
            found.setdefault(r["match_id"], []).append(r)
        return found

    def name(self, player_id: str | None) -> str:
        if player_id is None:
            return "?"
        return str(self.names.get(player_id, player_id))

    def team_name(self, team_season_id: str | None) -> str:
        return str(self.teams.get(team_season_id or "", ("", team_season_id or "?"))[1])

    def franchise(self, team_season_id: str | None) -> str | None:
        found = self.teams.get(team_season_id or "")
        return found[0] if found else None

    def _swings(self) -> dict[int, Row]:
        if "match_swings" not in self.tables:
            return {}
        return {
            r["match_id"]: r
            for r in _rows(
                self.con,
                """
                SELECT s.match_id, s.innings_no, s.seq_no, s.swing, s.team_season_id,
                       s.wp_before, s.wp_after, d.ball_label, d.batter_id, d.bowler_id,
                       d.runs_total, d.runs_batter, d.is_four, d.is_six, d.is_wicket,
                       d.extras_wides, d.extras_noballs, d.team_runs, d.team_wickets,
                       d.batting_team_id, w.player_out_id, w.kind AS wicket_kind
                FROM match_swings s
                JOIN deliveries d USING (match_id, innings_no, seq_no)
                LEFT JOIN wickets w USING (match_id, innings_no, seq_no)
                QUALIFY row_number() OVER (PARTITION BY s.match_id ORDER BY w.wicket_no) = 1
                """,
            )
        }

    def _wpa(self) -> dict[int, Row]:
        if "player_wpa" not in self.tables:
            return {}
        return {
            r["match_id"]: r
            for r in _rows(
                self.con,
                """
                WITH totals AS (
                    SELECT match_id, player_id, sum(wpa) AS wpa FROM player_wpa
                    GROUP BY match_id, player_id
                )
                SELECT t.match_id, t.player_id, t.wpa, mp.team_season_id
                FROM totals t
                LEFT JOIN match_players mp USING (match_id, player_id)
                QUALIFY row_number() OVER (
                    PARTITION BY t.match_id ORDER BY t.wpa DESC, t.player_id
                ) = 1
                """,
            )
        }

    def _careers(self) -> dict[str, dict[tuple[str, int], Row]]:
        """Each player's totals in the competition after every match they played."""
        found: dict[str, dict[tuple[str, int], Row]] = {}
        queries = {
            "runs": """
                SELECT b.player_id, b.match_id, sum(b.runs) AS amount, count(*) AS innings
                FROM player_batting_innings b GROUP BY b.player_id, b.match_id
            """,
            "wickets": """
                SELECT b.player_id, b.match_id, sum(b.wickets) AS amount, count(*) AS innings
                FROM player_bowling_innings b WHERE b.balls > 0
                GROUP BY b.player_id, b.match_id
            """,
            "matches": """
                SELECT mp.player_id, mp.match_id, 1 AS amount, 1 AS innings
                FROM match_players mp
            """,
        }
        for kind, inner in queries.items():
            rows = _rows(
                self.con,
                f"""
                WITH per AS ({inner}),
                ordered AS (
                    SELECT p.*, m.match_order FROM per p JOIN matches m USING (match_id)
                )
                SELECT player_id, match_id, match_order, amount::BIGINT AS amount,
                       sum(amount) OVER w AS after, sum(innings) OVER w AS innings_after,
                       min(match_order) OVER (PARTITION BY player_id) AS first_order
                FROM ordered
                WINDOW w AS (PARTITION BY player_id ORDER BY match_order, match_id
                             ROWS UNBOUNDED PRECEDING)
                """,
            )
            found[kind] = {(r["player_id"], r["match_id"]): r for r in rows}
        return found


# --------------------------------------------------------------------------- items


def _context(c: _Competition, m: Row, event: Row | None) -> str:
    """Where the match sits: "in the IPL 2026 final", "in the 2nd Test of ..."."""
    stage = m["stage"] or "League"
    if not c.national:
        label = f"{c.source.noun} {m['season_label']}"
        if stage == "Final":
            return f"in the {label} final"
        if stage != "League":
            return (
                f"in {article(stage)} {stage} of {label}"
                if stage.endswith("Final")
                else (f"in {stage} of {label}")
            )
        return f"in {label}"
    noun = c.source.noun
    if event is None:
        return f"in {article(noun)} {noun}"
    name = event["name"] if event["named"] else None
    if event["kind"] == "tournament":
        where = the(name) if name else "a tournament"
        rnd = event["round"]
        if rnd and event["knockout"]:
            return f"in the {rnd.lower() if rnd == 'Final' else rnd} of {where}"
        return f"at {where}"
    number = event["match_number"]
    if number:
        return f"in the {ordinal(number)} {noun}" + (f" of {the(name)}" if name else "")
    return f"in {article(noun)} {noun}" + (f" ({name})" if name else "")


def _margin(m: Row) -> str:
    if m["win_by_innings"]:
        return f"an innings and {plural(m['win_by_runs'] or 0, 'run')}"
    if m["win_by_runs"]:
        return plural(m["win_by_runs"], "run")
    if m["win_by_wickets"]:
        return plural(m["win_by_wickets"], "wicket")
    return ""


def _method(m: Row) -> str:
    method = m["win_method"]
    if not method:
        return ""
    if "D/L" in method or "DLS" in method:
        return " (DLS method)"
    return f" ({method.lower()})"


def _result(c: _Competition, m: Row, event: Row | None) -> Item:
    a, b = m["team_a_name"], m["team_b_name"]
    where = _context(c, m, event)
    winner = m["winner_id"]
    if winner and m["decided_by_super_over"]:
        loser = b if winner == m["team_a_id"] else a
        title = f"{m['winner_name']} beat {loser} in a super over after a tie {where}"
    elif winner:
        loser = b if winner == m["team_a_id"] else a
        margin = _margin(m)
        if margin:
            title = f"{m['winner_name']} beat {loser} by {margin}{_method(m)} {where}"
        else:
            title = f"{m['winner_name']} won against {loser}{_method(m)} {where}"
    elif m["outcome_type"] == "draw":
        title = f"{a} and {b} drew {where}"
    elif m["outcome_type"] == "tie":
        title = f"{a} and {b} tied {where}"
    else:
        title = f"{a} v {b} ended without a result {where}"

    parts: list[str] = []
    by_team: dict[str, list[str]] = {}
    for inn in c.innings.get(m["match_id"], []):
        figure = score(inn["runs"], inn["wickets"])
        if c.limited:
            figure += f" ({overs(inn['legal_balls'])} overs)"
        by_team.setdefault(c.team_name(inn["batting_team_id"]), []).append(figure)
    if by_team:
        parts.append(sentence("; ".join(f"{t} {' and '.join(f)}" for t, f in by_team.items())))
    links = [{"label": "Scorecard and replay", "href": f"/{c.source.site}/matches/{m['match_id']}"}]
    stars: list[str] = []
    bat = c.top_batter.get(m["match_id"])
    if bat and bat["runs"] > 0:
        stars.append(batting(c.name(bat["player_id"]), bat["runs"], bat["balls"], bat["is_out"]))
        links.append({"label": c.name(bat["player_id"]), "href": _player(c, bat["player_id"])})
    bowl = c.top_bowler.get(m["match_id"])
    if bowl and bowl["wickets"] > 0:
        stars.append(f"{c.name(bowl['player_id'])} {bowl['wickets']}/{bowl['runs']}")
        if bowl["player_id"] != (bat or {}).get("player_id"):
            links.append(
                {"label": c.name(bowl["player_id"]), "href": _player(c, bowl["player_id"])}
            )
    if stars:
        parts.append(sentence("Best figures: " + ", ".join(stars)))
    pom = [p for p in (m["player_of_match"] or []) if p]
    if pom:
        parts.append(sentence("Player of the match: " + ", ".join(pom)))
    stage = m["stage"] or "League"
    why = ""
    score_ = 3
    if stage == "Final" or (event and event.get("round") == "Final"):
        why = f"The final: it decided the {_title(c, m, event)}."
        score_ = 8
    elif m["is_playoff"] or (event and event.get("knockout")):
        why = "A knockout or playoff match."
        score_ = 6
    return Item("result", sentence(title), " ".join(parts), why, links, score_)


def _title(c: _Competition, m: Row, event: Row | None) -> str:
    if not c.national:
        return f"{c.source.noun} {m['season_label']} title"
    if event and event["named"]:
        return str(event["name"])
    return "tournament"


def _player(c: _Competition, player_id: str) -> str:
    return f"/{c.source.site}/players/{player_id}"


def _turning_point(c: _Competition, m: Row) -> Item | None:
    s = c.swings.get(m["match_id"])
    if s is None or s["swing"] is None or abs(s["swing"]) < MIN_SWING:
        return None
    side = c.team_name(s["team_season_id"])
    before, after = round(100 * s["wp_before"]), round(100 * s["wp_after"])
    batter, bowler = c.name(s["batter_id"]), c.name(s["bowler_id"])
    if s["is_wicket"] and s["player_out_id"]:
        kind = (s["wicket_kind"] or "out").replace("_", " ")
        what = f"{c.name(s['player_out_id'])} out ({kind})"
        short = f"{possessive(c.name(s['player_out_id']))} wicket"
    elif s["is_six"]:
        what, short = f"{batter} hit a six", f"{possessive(batter)} six"
    elif s["is_four"]:
        what, short = f"{batter} hit a four", f"{possessive(batter)} four"
    elif s["extras_wides"]:
        what, short = f"a wide from {bowler}", f"{possessive(bowler)} wide"
    elif s["runs_total"]:
        what = f"{plural(s['runs_total'], 'run')} to {batter}"
        short = f"the {plural(s['runs_total'], 'run')} to {batter}"
    else:
        what, short = f"{bowler} beat {batter} for a dot ball", f"{possessive(bowler)} dot ball"
    batting_side = c.team_name(s["batting_team_id"])
    title = (
        f"Turning point: {short} at {s['ball_label']} moved {side} from {before}% to "
        f"{after}% (model estimate)"
    )
    body = (
        f"Ball {s['ball_label']} of the {ordinal(s['innings_no'])} innings, {bowler} to {batter}: "
        f"{what}, leaving {batting_side} {score(s['team_runs'], s['team_wickets'])}. "
        f"{possessive(side)} chance of winning went from {before}% to {after}%, the biggest "
        "move from one ball in the match (model estimate)."
    )
    href = f"/{c.source.site}/matches/{m['match_id']}?ball={s['innings_no']}.{s['seq_no']}"
    return Item(
        "turning_point",
        sentence(title),
        body,
        "The biggest single-ball swing in win probability in the match.",
        [{"label": "Replay that ball", "href": href}],
        2 if abs(s["swing"]) >= 0.5 else 1,
    )


def _match_winner(c: _Competition, m: Row) -> Item | None:
    w = c.wpa.get(m["match_id"])
    if w is None or w["wpa"] is None or w["wpa"] < MIN_WPA:
        return None
    name = c.name(w["player_id"])
    points = round(100 * w["wpa"])
    team = c.team_name(w["team_season_id"]) if w["team_season_id"] else None
    for_team = f" for {team}" if team else ""
    title = f"Match-winner: {name}, +{points} points of win probability{for_team} (model estimate)"
    chance = f"{possessive(team)} chance of winning" if team else "the side's chance of winning"
    body = (
        f"Counting every ball faced and bowled, {name} moved {chance} by {points} percentage "
        "points, the most of anyone in the match (model estimate)."
    )
    return Item(
        "match_winner",
        sentence(title),
        body,
        "The highest win probability added by any player in the match.",
        [{"label": name, "href": _player(c, w["player_id"])}],
        1,
    )


@dataclass(frozen=True)
class _Crossing:
    kind: str
    threshold: int
    player_id: str
    match_id: int
    after: int
    innings: int
    amount: int
    nth: int


def _crossings(c: _Competition) -> dict[int, list[_Crossing]]:
    """Every milestone reached in the data, by match, with how many reached it before."""
    steps = {
        "runs": 1000 if c.national else 500,
        "wickets": 50,
        "matches": 50,
    }
    first_match_order = c.matches[0]["match_order"] if c.matches else 0
    first_date = c.matches[0]["end_date"] if c.matches else None
    # Internationals: a player in the data's first year may have started before it.
    early = {
        m["match_order"]
        for m in c.matches
        if c.national and first_date is not None and (m["end_date"] - first_date).days < 366
    }
    found: list[_Crossing] = []
    for kind, step in steps.items():
        reached: list[tuple[int, int, str, int, Row]] = []
        for (player_id, match_id), r in c.careers[kind].items():
            after, before = int(r["after"]), int(r["after"]) - int(r["amount"])
            if after // step <= before // step:
                continue
            if r["first_order"] in early and r["first_order"] != first_match_order - 1:
                continue
            threshold = after // step * step
            reached.append((threshold, r["match_order"], player_id, match_id, r))
        reached.sort(key=lambda x: (x[0], x[1], x[3], x[2]))
        count: dict[int, int] = {}
        for threshold, _, player_id, match_id, r in reached:
            count[threshold] = count.get(threshold, 0) + 1
            found.append(
                _Crossing(
                    kind,
                    threshold,
                    player_id,
                    match_id,
                    int(r["after"]),
                    int(r["innings_after"]),
                    int(r["amount"]),
                    count[threshold],
                )
            )
    by_match: dict[int, list[_Crossing]] = {}
    for x in found:
        by_match.setdefault(x.match_id, []).append(x)
    for items in by_match.values():
        items.sort(key=lambda x: (-x.threshold, x.kind, x.player_id))
    return by_match


def _milestone(c: _Competition, x: _Crossing) -> Item:
    name, noun = c.name(x.player_id), c.source.noun
    nth = "the first player" if x.nth == 1 else f"the {ordinal(x.nth)} player"
    if x.kind == "runs":
        title = f"{name} passed {x.threshold:,} {noun} runs"
        body = (
            f"With {x.amount} in this match: {x.after:,} runs in "
            f"{x.innings:,} innings in CricIQ's {noun} "
            f"data, {nth} to get there."
        )
    elif x.kind == "wickets":
        title = f"{name} reached {x.threshold:,} {noun} wickets"
        body = (
            f"With {plural(x.amount, 'wicket')} in this match: {x.after:,} in CricIQ's {noun} "
            f"data, {nth} to get there."
        )
    else:
        title = f"{x.threshold:,} {noun} matches for {name}"
        body = (
            f"{possessive(name)} {ordinal(x.threshold)} {noun} match in CricIQ's data, {nth} to "
            "play as many."
        )
    return Item(
        "milestone",
        sentence(title),
        body,
        f"A milestone in CricIQ's {noun} data, which begins with its first ball-by-ball season.",
        [{"label": name, "href": _player(c, x.player_id)}],
        4,
    )


# Record lists checked as each match is played: the key in the Records hub, what an entry
# is, and how it is written.
_RECORD_LABELS = {
    "highest-totals": "total",
    "highest-scores": "score",
    "best-bowling-figures": "bowling figures",
    "highest-partnerships": "partnership",
}


def _record_entries(c: _Competition) -> dict[str, list[tuple[int, int, tuple[int, int], str, str]]]:
    """(match index, match id, value, who, figure) for every entry of each list."""
    entries: dict[str, list[tuple[int, int, tuple[int, int], str, str]]] = {
        k: [] for k in _RECORD_LABELS
    }
    for match_id, innings in c.innings.items():
        if match_id not in c.index:
            continue
        for inn in innings:
            team = c.team_name(inn["batting_team_id"])
            entries["highest-totals"].append(
                (
                    c.index[match_id],
                    match_id,
                    (inn["runs"], 0),
                    team,
                    score(inn["runs"], inn["wickets"]),
                )
            )
    for match_id, rows in c.batting.items():
        if match_id not in c.index:
            continue
        for r in rows:
            entries["highest-scores"].append(
                (
                    c.index[match_id],
                    match_id,
                    (r["runs"], 0),
                    c.name(r["player_id"]),
                    f"{r['runs']}{'' if r['is_out'] else '*'} ({r['balls']})",
                )
            )
    for match_id, rows in c.bowling.items():
        if match_id not in c.index:
            continue
        for r in rows:
            if r["wickets"] == 0:
                continue
            entries["best-bowling-figures"].append(
                (
                    c.index[match_id],
                    match_id,
                    (r["wickets"], -r["runs"]),
                    c.name(r["player_id"]),
                    f"{r['wickets']}/{r['runs']}",
                )
            )
    if "partnerships" in c.tables:
        for r in _rows(
            c.con, "SELECT match_id, first_id, second_id, runs, wicket FROM partnerships"
        ):
            if r["match_id"] not in c.index:
                continue
            who = f"{c.name(r['first_id'])} and {c.name(r['second_id'])}"
            entries["highest-partnerships"].append(
                (c.index[r["match_id"]], r["match_id"], (r["runs"], 0), who, str(r["runs"]))
            )
    for values in entries.values():
        values.sort(key=lambda e: (e[0], e[1], e[3]))
    return entries


@dataclass(frozen=True)
class _Ranked:
    key: str
    match_id: int
    rank: int
    tied: bool
    who: str
    figure: str


def _record_ranks(c: _Competition) -> dict[int, list[_Ranked]]:
    """Entries that went into a list's top 10 when they were made (earlier matches only)."""
    found: dict[int, list[_Ranked]] = {}
    for key, entries in _record_entries(c).items():
        best: list[tuple[int, int]] = []  # the top values so far, ascending
        i = 0
        while i < len(entries):
            j = i
            while j < len(entries) and entries[j][0] == entries[i][0]:
                j += 1
            batch = entries[i:j]
            if batch[0][0] >= MIN_HISTORY:
                for _, match_id, value, who, figure in batch:
                    better = len(best) - bisect.bisect_right(best, value)
                    if better < TOP:
                        equal = bisect.bisect_right(best, value) - bisect.bisect_left(best, value)
                        found.setdefault(match_id, []).append(
                            _Ranked(key, match_id, better + 1, equal > 0, who, figure)
                        )
            for _, _, value, _, _ in batch:
                bisect.insort(best, value)
            del best[: max(0, len(best) - TOP * 4)]
            i = j
    for items in found.values():
        items.sort(key=lambda r: (r.rank, list(_RECORD_LABELS).index(r.key), r.who))
    return found


def _record(c: _Competition, r: _Ranked) -> Item:
    label = _RECORD_LABELS[r.key]
    noun = c.source.noun
    figures = r.key == "best-bowling-figures"
    adjective = "best" if figures else "highest"
    if r.key == "highest-partnerships":
        subject = f"The stand of {r.figure} between {r.who}"
    else:
        subject = f"{possessive(r.who)} {r.figure}"
    where = f"in CricIQ's {noun} data"
    if r.rank == 1 and r.tied:
        title = f"{subject} {'equal' if figures else 'equals'} the {adjective} {label} {where}"
    else:
        place = (
            adjective if r.rank == 1 else f"{'=' if r.tied else ''}{ordinal(r.rank)}-{adjective}"
        )
        title = f"{subject} {'are' if figures else 'is'} the {place} {label} {where}"
    new = r.rank == 1 and not r.tied
    return Item(
        "record",
        sentence(title),
        f"Ranked against every {noun} match in the data before this one.",
        f"A new record {where}." if new else f"Into the top {TOP} {where}.",
        [{"label": "The full list", "href": f"/{c.source.site}/records/{r.key}"}],
        9 if new else 2,
    )


def _series_states(c: _Competition) -> tuple[dict[int, Row], dict[int, Item]]:
    """Each international match's event, and the series score after it."""
    if "events" not in c.tables or "event_matches" not in c.tables:
        return {}, {}
    events = {r["event_id"]: r for r in _rows(c.con, "SELECT * FROM events")}
    by_match: dict[int, Row] = {}
    members: dict[str, list[Row]] = {}
    for r in _rows(c.con, "SELECT * FROM event_matches"):
        e = events.get(r["event_id"])
        if e is None or r["match_id"] not in c.index:
            continue
        joined = {**e, **r}
        by_match[r["match_id"]] = joined
        members.setdefault(r["event_id"], []).append(joined)
    matches = {m["match_id"]: m for m in c.matches}
    states: dict[int, Item] = {}
    for event_id, rows in members.items():
        e = events[event_id]
        if e["kind"] != "series":
            continue
        # A series with matches missing from the data can't be scored from it.
        total = int(e["matches"] or 0)
        if total < 2 or int(e["missing"] or 0) > 0 or len(rows) != total:
            continue
        rows.sort(key=lambda r: (c.index[r["match_id"]], r["match_id"]))
        wins: dict[str, int] = {t: 0 for t in e["teams"] or []}
        drawn = 0
        decided = False
        for played, r in enumerate(rows, start=1):
            m = matches[r["match_id"]]
            winner = c.franchise(m["winner_id"])
            if winner:
                wins[winner] = wins.get(winner, 0) + 1
            elif m["outcome_type"] == "draw":
                drawn += 1
            ranked = sorted(wins.items(), key=lambda kv: (-kv[1], kv[0]))
            if len(ranked) < 2:
                continue
            (top, a), (other, b) = ranked[0], ranked[1]
            top_name = c.franchises.get(top, top)
            other_name = c.franchises.get(other, other)
            extra = f" ({drawn} drawn)" if drawn else ""
            series = f"the {total}-match series"
            why = ""
            score_ = 1
            if a > total / 2 and not decided:
                decided = True
                left = total - played
                spare = f" with {left} to spare" if left else ""
                title = f"{top_name} won {series} {a}{DASH}{b}{extra}{spare}"
                why = "It settled the series."
                score_ = 5
            elif played == total:
                if a == b:
                    title = f"{top_name} and {other_name} drew {series} {a}{DASH}{b}{extra}"
                else:
                    title = f"{top_name} took {series} {a}{DASH}{b}{extra}"
            elif decided:
                title = f"{top_name} lead {series} {a}{DASH}{b}{extra}, already won"
            elif a == b:
                title = f"{top_name} and {other_name} are level at {a}{DASH}{b} in {series}{extra}"
            else:
                title = f"{top_name} lead {series} {a}{DASH}{b}{extra}"
            states[r["match_id"]] = Item(
                "standings",
                sentence(title),
                f"After {played} of {total} matches.",
                why,
                [{"label": "The series", "href": f"/{c.source.site}/series/{event_id}"}],
                score_,
            )
    return by_match, states


def _league_tables(c: _Competition) -> dict[int, Item]:
    """A league side's position in the table worked out from the results so far."""
    if c.national or "team_matches" not in c.tables:
        return {}
    rows = _rows(
        c.con,
        """
        SELECT match_id, match_order, season, franchise_id, team_name, result,
               coalesce(nrr_runs_for, 0) AS rf, coalesce(nrr_balls_for, 0) AS bf,
               coalesce(nrr_runs_against, 0) AS ra, coalesce(nrr_balls_against, 0) AS ba
        FROM team_matches WHERE in_table
        ORDER BY season, match_order, match_id, franchise_id
        """,
    )
    table: dict[tuple[int, str], dict[str, Any]] = {}
    found: dict[int, Item] = {}
    by_match: dict[int, list[Row]] = {}
    for r in rows:
        by_match.setdefault(r["match_id"], []).append(r)
    for match_id, sides in by_match.items():
        season = sides[0]["season"]
        for r in sides:
            t = table.setdefault(
                (season, r["franchise_id"]),
                {
                    "name": r["team_name"],
                    "played": 0,
                    "won": 0,
                    "points": 0,
                    "rf": 0,
                    "bf": 0,
                    "ra": 0,
                    "ba": 0,
                },
            )
            t["name"] = r["team_name"]
            t["played"] += 1
            t["won"] += r["result"] == "won"
            t["points"] += 2 if r["result"] == "won" else 1 if r["result"] == "no_result" else 0
            for k in ("rf", "bf", "ra", "ba"):
                t[k] += r[k]

        def nrr(t: dict[str, Any]) -> float:
            f = t["rf"] / (t["bf"] / 6) if t["bf"] else 0.0
            a = t["ra"] / (t["ba"] / 6) if t["ba"] else 0.0
            return f - a

        standing = sorted(
            ((k[1], t) for k, t in table.items() if k[0] == season),
            key=lambda kv: (-kv[1]["points"], -nrr(kv[1]), kv[0]),
        )
        position = {team: i + 1 for i, (team, _) in enumerate(standing)}
        parts = []
        top = False
        for r in sorted(sides, key=lambda r: position[r["franchise_id"]]):
            t = table[(season, r["franchise_id"])]
            p = position[r["franchise_id"]]
            top = top or p == 1
            parts.append(
                f"{t['name']} {ordinal(p)} ({t['won']} {'win' if t['won'] == 1 else 'wins'} from "
                f"{t['played']})"
            )
        found[match_id] = Item(
            "standings",
            sentence("Table: " + ", ".join(parts)),
            f"The league table worked out from the {c.source.noun} results in the data, on "
            "points and then net run rate.",
            "Top of the table." if top else "",
            [{"label": "Season table", "href": f"/{c.source.site}/teams?season={season}"}],
            1,
        )
    return found


def _figures(c: _Competition, match_id: int) -> list[Row]:
    """The match's best batting and bowling, with the players' totals before and after it."""
    rows: list[Row] = []
    for r in c.batting.get(match_id, [])[:2]:
        if r["runs"] < (50 if c.limited else 100) and rows:
            continue
        career = c.careers["runs"].get((r["player_id"], match_id))
        after = int(career["after"]) if career else r["runs"]
        rows.append(
            {
                "player_id": r["player_id"],
                "name": c.name(r["player_id"]),
                "team": c.franchises.get(r["team_id"], r["team_id"]),
                "kind": "batting",
                "figure": batting("", r["runs"], r["balls"], r["is_out"]).strip(),
                "career_before": after - int(career["amount"]) if career else 0,
                "career_after": after,
                "unit": "runs",
                "weight": r["runs"],
            }
        )
    for r in c.bowling.get(match_id, [])[:2]:
        if r["wickets"] < 3 and any(x["kind"] == "bowling" for x in rows):
            continue
        if r["wickets"] == 0:
            continue
        career = c.careers["wickets"].get((r["player_id"], match_id))
        after = int(career["after"]) if career else r["wickets"]
        rows.append(
            {
                "player_id": r["player_id"],
                "name": c.name(r["player_id"]),
                "team": c.franchises.get(r["team_id"], r["team_id"]),
                "kind": "bowling",
                "figure": f"{r['wickets']}/{r['runs']}",
                "career_before": after - int(career["amount"]) if career else 0,
                "career_after": after,
                "unit": "wickets",
                "weight": r["wickets"] * 20 - r["runs"] / 10,
            }
        )
    return rows


def _notability(c: _Competition, m: Row, items: list[Item]) -> int:
    n = 0
    if (m["stage"] or "League") == "Final":
        n += 3
    elif m["is_playoff"]:
        n += 2
    bat = c.top_batter.get(m["match_id"])
    if bat:
        n += 3 if bat["runs"] >= 100 else 1 if bat["runs"] >= 50 else 0
    bowl = c.top_bowler.get(m["match_id"])
    if bowl:
        n += 3 if bowl["wickets"] >= 5 else 1 if bowl["wickets"] >= 4 else 0
    for item in items:
        if item.kind == "record":
            n += 3 if item.score >= 9 else 1
        elif item.kind == "standings" and item.score >= 5:
            n += 2
        elif item.kind in ("milestone", "turning_point"):
            n += 1
    return n


def collect(con: duckdb.DuckDBPyConnection, source: Source) -> tuple[list[Match], _Competition]:
    """Every match of one competition with its note items."""
    c = _Competition(con, source)
    events, series = _series_states(c)
    tables = _league_tables(c)
    crossings = _crossings(c)
    ranks = _record_ranks(c)
    found: list[Match] = []
    for m in c.matches:
        match_id = m["match_id"]
        event = events.get(match_id)
        items = [_result(c, m, event)]
        for extra in (_turning_point(c, m), _match_winner(c, m)):
            if extra is not None:
                items.append(extra)
        items += [_milestone(c, x) for x in crossings.get(match_id, [])[:MAX_MILESTONES]]
        items += [_record(c, r) for r in ranks.get(match_id, [])[:3]]
        standing = series.get(match_id) or tables.get(match_id)
        if standing is not None:
            if standing.why == "It settled the series.":
                items[0].score = max(items[0].score, 5)
            items.append(standing)
        found.append(
            Match(
                source,
                match_id,
                m["match_order"],
                m["end_date"],
                _notability(c, m, items),
                items,
                _figures(c, match_id),
            )
        )
    return found, c


# --------------------------------------------------------------------------- notes


@dataclass
class Note:
    date: dt.date
    headline: str
    summary: str
    competitions: list[str]
    matches: list[Match]
    items: list[tuple[Match, Item]]
    figures: list[tuple[Match, Row]]


def _order_key(m: Match) -> tuple[int, int, int, int]:
    rank = ORDER.index(m.source.competition_id) if m.source.competition_id in ORDER else 99
    return (-m.notability, rank, m.match_order, m.match_id)


def compose(matches: Iterable[Match]) -> list[Note]:
    """One note per date, its matches most notable first."""
    by_date: dict[dt.date, list[Match]] = {}
    for m in matches:
        by_date.setdefault(m.date, []).append(m)
    notes: list[Note] = []
    for date in sorted(by_date):
        day = sorted(by_date[date], key=_order_key)
        items: list[tuple[Match, Item]] = []
        for i, m in enumerate(day):
            for item in m.items:
                if i < FULL_MATCHES or item.kind == "result" or item.score >= 9:
                    items.append((m, item))
        records = [item for _, item in items if item.kind == "record" and item.score >= 9]
        results = [item for _, item in items if item.kind == "result"]
        lead = records[0] if records else items[0][1]
        headline = lead.title.rstrip(".")
        top = [lead.title, *[i.title for i in results if i is not lead][:2]]
        competitions = sorted(
            {m.source.site for m in day},
            key=lambda s: ORDER.index(s.upper()) if s.upper() in ORDER else 99,
        )
        figures = sorted(
            ((m, f) for m in day for f in m.figures),
            key=lambda pair: (-pair[1]["weight"], _order_key(pair[0]), pair[1]["player_id"]),
        )[:FIGURE_ROWS]
        notes.append(Note(date, headline, " ".join(top), competitions, day, items, figures))
    return notes


def _write(
    out: Path,
    notes: list[Note],
    *,
    data_version: str,
    pipeline_version: str,
    added: Mapping[int, dt.datetime],
    built: dt.datetime,
) -> dict[str, int]:
    staging = out.with_name(out.name + ".building")
    staging.unlink(missing_ok=True)
    con = duckdb.connect(str(staging))
    try:
        con.execute(
            """
            CREATE TABLE notes (
                date DATE PRIMARY KEY, slug VARCHAR NOT NULL, headline VARCHAR NOT NULL,
                summary VARCHAR NOT NULL, competitions VARCHAR[] NOT NULL,
                match_count INTEGER NOT NULL, data_version VARCHAR NOT NULL,
                added_on TIMESTAMP NOT NULL
            );
            CREATE TABLE note_items (
                date DATE NOT NULL, position INTEGER NOT NULL, kind VARCHAR NOT NULL,
                competition_id VARCHAR NOT NULL, match_id BIGINT NOT NULL, title VARCHAR NOT NULL,
                body VARCHAR NOT NULL, why_it_matters VARCHAR NOT NULL, links VARCHAR NOT NULL,
                PRIMARY KEY (date, position)
            );
            CREATE TABLE note_figures (
                date DATE NOT NULL, position INTEGER NOT NULL, competition_id VARCHAR NOT NULL,
                match_id BIGINT NOT NULL, player_id VARCHAR NOT NULL, name VARCHAR NOT NULL,
                team VARCHAR, kind VARCHAR NOT NULL, figure VARCHAR NOT NULL,
                career_before INTEGER NOT NULL, career_after INTEGER NOT NULL,
                unit VARCHAR NOT NULL, PRIMARY KEY (date, position)
            );
            CREATE TABLE meta (key VARCHAR PRIMARY KEY, value VARCHAR);
            """
        )
        note_rows, item_rows, figure_rows = [], [], []
        for note in notes:
            seen = [added[m.match_id] for m in note.matches if m.match_id in added]
            note_rows.append(
                (
                    note.date,
                    note.date.isoformat(),
                    note.headline,
                    note.summary,
                    note.competitions,
                    len(note.matches),
                    data_version,
                    max(seen) if seen else built,
                )
            )
            for position, (m, item) in enumerate(note.items, start=1):
                item_rows.append(
                    (
                        note.date,
                        position,
                        item.kind,
                        m.source.site,
                        m.match_id,
                        item.title,
                        item.body,
                        item.why,
                        json.dumps(item.links, ensure_ascii=False),
                    )
                )
            for position, (m, f) in enumerate(note.figures, start=1):
                figure_rows.append(
                    (
                        note.date,
                        position,
                        m.source.site,
                        m.match_id,
                        f["player_id"],
                        f["name"],
                        f["team"],
                        f["kind"],
                        f["figure"],
                        f["career_before"],
                        f["career_after"],
                        f["unit"],
                    )
                )
        if note_rows:
            con.executemany("INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, ?)", note_rows)
        if item_rows:
            con.executemany("INSERT INTO note_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", item_rows)
        if figure_rows:
            con.executemany(
                "INSERT INTO note_figures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", figure_rows
            )
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("data_version", data_version),
                ("pipeline_version", pipeline_version),
                ("built_at", built.isoformat(timespec="seconds")),
                ("method", METHOD),
            ],
        )
        counts = {t: len(con.execute(f"SELECT 1 FROM {t}").fetchall()) for t in NOTE_TABLES}
    finally:
        con.close()
    publish(staging, out)
    return counts


def build_notes(
    servings: Mapping[str, Path],
    out: Path,
    *,
    added: Mapping[int, dt.datetime] | None = None,
    built: dt.datetime | None = None,
    log: Log = lambda _: None,
) -> dict[str, int]:
    """Write ``out`` (notes.duckdb) from the serving databases, keyed by competition id.

    ``added`` gives when each match first came into the data (the sync's ingest log); a
    note was added when its newest match was. Missing databases are skipped.
    """
    built = built or dt.datetime.now().replace(microsecond=0)
    matches: list[Match] = []
    versions: list[tuple[str, str]] = []
    for competition_id in sorted(servings, key=lambda k: ORDER.index(k) if k in ORDER else 99):
        path = current(servings[competition_id])
        if not path.exists():
            log(f"  notes: no {competition_id} database, skipped")
            continue
        con = duckdb.connect(str(path), read_only=True)
        try:
            found, c = collect(con, Source(competition_id, path))
        finally:
            con.close()
        matches += found
        versions.append((c.data_version, c.pipeline_version))
        log(f"  notes: {competition_id} {len(found)} matches")
    notes = compose(matches)
    data_version, pipeline_version = versions[0] if versions else ("", "")
    return _write(
        out,
        notes,
        data_version=data_version,
        pipeline_version=pipeline_version,
        added=added or {},
        built=built,
    )


def ingest_added(ingest: Path) -> dict[int, dt.datetime]:
    """When each match first came into the data, from the sync's ingest log (if there is one)."""
    if not ingest.exists():
        return {}
    con = duckdb.connect(str(ingest), read_only=True)
    try:
        if "ingest_log" not in _tables(con):
            return {}
        return {
            int(r[0]): r[1]
            for r in con.execute("SELECT match_id, first_seen FROM ingest_log").fetchall()
        }
    finally:
        con.close()
