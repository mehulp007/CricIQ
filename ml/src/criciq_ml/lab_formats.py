"""Analytics Lab notes across formats: the toss, and home advantage.

Each compares the kinds of cricket CricIQ covers, each from its own matches (the
IPL; the BBL, CPL, PSL and SA20 together; T20Is; ODIs; Tests), and answers with
intervals that resample whole matches:

* **The toss.** The toss is a coin flip, so the toss winner's results against an
  even share measure what winning it is worth, with nothing else mixed in. Does it
  matter more in Tests, where a pitch changes over five days? And in Tests in Asia,
  where pitches are thought to turn later in the match?
* **Home advantage.** How much better do sides do at home in each format? The raw
  home record mixes in strength (strong sides host more), so the note also
  balances it: for every pair of sides that met at both ends, the home share at
  each end is averaged, so each pair's strength cancels out.

A result's share counts a win as one, and a draw or a tie without a winner as a
half; matches without a result are left out.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from criciq_core import paths

LAB_DIR = paths.repo_root() / "frontend" / "data" / "lab"
SEED = 11
REPS = 2000
# The kinds of cricket compared, in display order: (key, label, competitions).
FORMATS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("test", "Tests", ("TEST",)),
    ("odi", "ODIs", ("ODI",)),
    ("t20i", "T20Is", ("T20I",)),
    ("ipl", "IPL", ("IPL",)),
    ("leagues", "BBL, CPL, PSL and SA20", ("BBL", "CPL", "PSL", "SA20")),
)
ASIA = ("India", "Pakistan", "Sri Lanka", "Bangladesh", "United Arab Emirates", "Afghanistan")
# Pairs need this many matches at each end to enter the balanced home estimate.
MIN_EACH_END = 2

SIDES_SQL = """
SELECT t.match_id, t.match_date, t.franchise_id, t.opponent_id, t.result, t.tied,
       t.won_toss, t.toss_decision, t.venue_type, v.country
FROM team_matches t JOIN venues v USING (venue_id)
WHERE t.result <> 'no_result'
"""


def load_sides(servings: Mapping[str, Path]) -> pd.DataFrame:
    """Both sides of every decided match, by competition, from the serving databases."""
    frames = []
    for competition, path in servings.items():
        con = duckdb.connect(str(path), read_only=True)
        try:
            frame = con.execute(SIDES_SQL).df()
        finally:
            con.close()
        frames.append(frame.assign(competition=competition))
    if not frames:
        return pd.DataFrame()
    sides = pd.concat(frames, ignore_index=True)
    # A tie without a winner is lost by both sides in team_matches: count it as level.
    level = sides["tied"] & ~sides.groupby("match_id")["result"].transform(
        lambda r: (r == "won").any()
    )
    sides["share"] = np.where(
        sides["result"] == "won",
        1.0,
        np.where((sides["result"] == "drawn") | level, 0.5, 0.0),
    )
    return sides


def _interval(values: np.ndarray, rng: np.random.Generator) -> dict[str, float]:
    """The mean and its 90% bootstrap interval (each value is one match), like the
    other Analytics Lab notes."""
    if len(values) == 0:
        return {"value": float("nan"), "low": float("nan"), "high": float("nan")}
    draws = rng.choice(values, size=(REPS, len(values)), replace=True).mean(axis=1)
    low, high = np.quantile(draws, [0.05, 0.95])
    return {
        "value": round(float(values.mean()), 4),
        "low": round(float(low), 4),
        "high": round(float(high), 4),
    }


def _row(label: str, frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any]:
    return {
        "label": label,
        "matches": len(frame),
        "won": int((frame["result"] == "won").sum()),
        "drawn": int((frame["share"] == 0.5).sum()),
        "lost": int(((frame["result"] != "won") & (frame["share"] == 0)).sum()),
        "share": _interval(frame["share"].to_numpy(), rng),
    }


def toss_note(sides: pd.DataFrame) -> dict[str, Any]:
    """The toss winner's share of results in each format, and what they chose."""
    rng = np.random.default_rng(SEED)
    winners = sides[sides["won_toss"].fillna(False).astype(bool)]
    formats, choices, asia = [], [], []
    for key, label, members in FORMATS:
        frame = winners[winners["competition"].isin(members)]
        if frame.empty:
            continue
        formats.append({"key": key, **_row(label, frame, rng)})
        for decision, name in (("bat", "Chose to bat"), ("field", "Chose to bowl")):
            chosen = frame[frame["toss_decision"] == decision]
            choices.append(
                {
                    "key": key,
                    "decision": decision,
                    "chose": round(len(chosen) / len(frame), 4),
                    **_row(name, chosen, rng),
                }
            )
        if key == "test":
            in_asia = frame["country"].isin(ASIA)
            asia.append(_row("Tests in Asia", frame[in_asia], rng))
            asia.append(_row("Tests elsewhere", frame[~in_asia], rng))
    return {"formats": formats, "choices": choices, "tests_by_region": asia}


def _balanced(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any] | None:
    """Home share with each pair's strength cancelled: the mean of the home shares at
    each end, over pairs that met at least MIN_EACH_END times at both ends; the interval
    resamples pairs."""
    home = frame[frame["venue_type"] == "home"]
    ends = home.groupby(["franchise_id", "opponent_id"])["share"].agg(["mean", "size"])
    pairs = []
    for (host, guest), row in ends.iterrows():
        if host > guest or (guest, host) not in ends.index:
            continue
        other = ends.loc[(guest, host)]
        if row["size"] < MIN_EACH_END or other["size"] < MIN_EACH_END:
            continue
        pairs.append(((row["mean"] + other["mean"]) / 2, int(row["size"] + other["size"])))
    if not pairs:
        return None
    values = np.array([p[0] for p in pairs])
    return {
        "pairs": len(pairs),
        "matches": sum(p[1] for p in pairs),
        "share": _interval(values, rng),
    }


def home_note(sides: pd.DataFrame) -> dict[str, Any]:
    """The home side's share of results in each format, raw and balanced for strength."""
    rng = np.random.default_rng(SEED)
    rows = []
    for key, label, members in FORMATS:
        frame = sides[sides["competition"].isin(members)]
        home = frame[frame["venue_type"] == "home"]
        if home.empty:
            continue
        rows.append(
            {
                "key": key,
                "neutral_share": round(float((frame["venue_type"] == "neutral").mean()), 4),
                **_row(label, home, rng),
                "balanced": _balanced(frame, rng),
            }
        )
    return {"formats": rows, "min_each_end": MIN_EACH_END}


def write_all(servings: Mapping[str, Path], out_dir: Path = LAB_DIR) -> list[Path]:
    """Write ``toss.json`` and ``home.json`` from the serving databases of every
    competition the notes compare (by competition id)."""
    sides = load_sides(servings)
    if sides.empty:
        return []
    versions = set()
    for path in servings.values():
        con = duckdb.connect(str(path), read_only=True)
        try:
            found = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
        finally:
            con.close()
        if found:
            versions.add(found[0])
    version = max(versions) if versions else "unknown"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, note in (("toss", toss_note(sides)), ("home", home_note(sides))):
        note["data_version"] = version
        path = out_dir / f"{slug}.json"
        path.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written
