"""Pipeline orchestration: the steps behind each ``criciq-data`` command.

Each step reads the outputs of the previous one from well-known locations
keyed by ``data_version``, so any step can be re-run on its own. The *current
data state* (version, interim tables, people register) comes from the latest
full download, or from the latest sync once one has run (``criciq_pipelines.sync``).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb

from criciq_core import paths
from criciq_core.groups import model_groups
from criciq_core.publish import publish
from criciq_pipelines import enrich
from criciq_pipelines.export import export_serving
from criciq_pipelines.extract import extract_archive
from criciq_pipelines.player_db import FORMATS as PLAYER_FORMATS
from criciq_pipelines.player_db import export_players
from criciq_pipelines.raw import RawSnapshot, latest_snapshot
from criciq_pipelines.reference import Competition, load_competitions
from criciq_pipelines.report import (
    REPORTED_FORMATS,
    render_competition_report,
    render_report,
    report_path_for,
)
from criciq_pipelines.scope import build_scope
from criciq_pipelines.validation import ValidationReport, validate
from criciq_pipelines.warehouse import BuildInputs, build_warehouse

ATTRIBUTES_FILE = "player_attributes.csv"
OVERRIDES_FILE = "player_attributes_overrides.csv"
# Cricsheet's register ids for ESPNcricinfo (a few players have two or three).
CRICINFO_SOURCES = ("cricinfo", "cricinfo_2", "cricinfo_3")


# Competitions whose v1-shaped warehouse the export and the models read.
SCOPED = ("IPL",)
# The pooled copy of every selected T20 competition, in one time order: what the
# pooled T20 models of V2-3 trained on and score from (criciq_ml), until each model
# group has trained its own.
POOLED = "T20"
# Formats with models of their own.
MODEL_FORMATS = ("T20", "ODI", "Test")
# Formats the site serves.
SERVED_FORMATS = ("T20", "ODI", "Test")


def selected_competitions() -> list[Competition]:
    """Competitions to download and build: ``CRICIQ_COMPETITIONS`` (comma separated)
    or every configured competition."""
    wanted = os.environ.get("CRICIQ_COMPETITIONS", "").strip()
    ids = [c.strip() for c in wanted.split(",") if c.strip()] or None
    return load_competitions().select(ids)


def archives_to_download() -> list[str]:
    return list(dict.fromkeys(c.cricsheet.archive for c in selected_competitions()))


def interim_dir_for(snapshot: RawSnapshot) -> Path:
    return paths.interim_dir() / snapshot.version


@dataclass(frozen=True)
class DataState:
    """What the warehouse is built from: a data version, its interim tables and register."""

    version: str
    interim: Path
    people: Path

    @classmethod
    def of(cls, snapshot: RawSnapshot) -> DataState:
        return cls(snapshot.version, interim_dir_for(snapshot), snapshot.people)


STATE_FILE = "state.json"


def save_state(state: DataState) -> None:
    """Make ``state`` current (written by a sync or a full rebuild)."""
    target = paths.sync_dir() / STATE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "data_version": state.version,
        "interim": str(state.interim),
        "people": str(state.people),
    }
    staging = target.with_name(target.name + ".new")
    staging.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(staging, target)


def current_state() -> DataState:
    """The latest synced state, else the latest downloaded snapshot."""
    saved = paths.sync_dir() / STATE_FILE
    if saved.exists():
        data = json.loads(saved.read_text(encoding="utf-8"))
        state = DataState(data["data_version"], Path(data["interim"]), Path(data["people"]))
        if (state.interim / "matches.parquet").exists() and state.people.exists():
            return state
    return DataState.of(latest_snapshot())


def run_extract(snapshot: RawSnapshot | None = None) -> dict[str, int]:
    snapshot = snapshot or latest_snapshot()
    return extract_archive(snapshot.archives, interim_dir_for(snapshot))


def run_build(
    snapshot: RawSnapshot | DataState | None = None,
    *,
    warehouse: Path | None = None,
    scopes: dict[str, Path] | None = None,
) -> dict[str, int]:
    """Build the full warehouse, then the v1-shaped copy of each scoped competition
    and each format's model copy (the pooled T20 copy, the ODIs').

    Without arguments this builds the current data state. ``scopes`` maps a scoped
    competition (or a model format) to where its copy goes (default: its usual
    warehouse path).
    """
    if isinstance(snapshot, RawSnapshot):
        if not (interim_dir_for(snapshot) / "matches.parquet").exists():
            run_extract(snapshot)
        state = DataState.of(snapshot)
    else:
        state = snapshot or current_state()
    selected = selected_competitions()
    target = warehouse or paths.cricket_warehouse_path()
    counts = build_warehouse(
        BuildInputs(
            interim_dir=state.interim,
            people_csv=state.people,
            data_version=state.version,
            attributes_csv=paths.reference_dir() / ATTRIBUTES_FILE,
            competitions=tuple(c.id for c in selected),
        ),
        target,
    )
    for competition in scoped_competitions():
        out = (scopes or {}).get(competition) or paths.warehouse_path(competition)
        build_scope(target, competition, out)
    for name, members in model_copies().items():
        out = (scopes or {}).get(name) or paths.warehouse_path(name)
        build_scope(target, members, out)
    return counts


def scoped_competitions() -> list[str]:
    """The scoped competitions among the selected ones."""
    selected = {c.id for c in selected_competitions()}
    return [c for c in SCOPED if c in selected]


def pooled_competitions() -> list[str]:
    """The selected T20 competitions, which the pooled copy holds."""
    return [c.id for c in selected_competitions() if c.format == "T20"]


def model_copies() -> dict[str, list[str]]:
    """The warehouse copies the models train on and score from, by name: the pooled
    T20 copy (``POOLED``) and each model group's (``LEAGUES``, ``T20I``, ``ODI``;
    ``criciq_core.groups``), each with its selected competitions. The IPL's is its
    scoped copy."""
    selected = [c for c in selected_competitions() if c.format in MODEL_FORMATS]
    found: dict[str, list[str]] = {}
    pooled = [c.id for c in selected if c.format == POOLED]
    if pooled:
        found[POOLED] = pooled
    for group in model_groups().groups:
        if group.copy_name in SCOPED:
            continue
        members = [c.id for c in selected if c.id in group.competitions]
        if members:
            found[group.copy_name] = members
    return found


def served_competitions() -> list[str]:
    """The selected switcher competitions the site serves, each from its own serving
    database (the IPL's from its scoped copy, the others exported from the warehouse)."""
    return [c.id for c in selected_competitions() if c.switcher and c.format in SERVED_FORMATS]


def exported_competitions() -> list[str]:
    """The served competitions without a scoped copy of their own."""
    return [c for c in served_competitions() if c not in SCOPED]


def serving_path() -> Path:
    return paths.serving_path()


def run_export(
    *,
    warehouse: Path | None = None,
    target: Path | None = None,
    updates: Path | None = None,
) -> dict[str, int]:
    """Export the serving database and put it in place (beside it while the API has it open).

    ``updates`` is the sync's ingest database, whose record of data updates the API
    reports; by default the local one, if it exists.
    """
    final = target or serving_path()
    staging = final.with_name(final.name + ".export")
    ingest = updates or paths.sync_dir() / "ingest.duckdb"
    counts = export_serving(
        warehouse or paths.warehouse_path(), staging, updates=ingest if ingest.exists() else None
    )
    publish(staging, final)
    return counts


def run_export_competition(
    competition: str,
    target: Path,
    *,
    warehouse: Path | None = None,
    updates: Path | None = None,
) -> dict[str, int]:
    """One competition's serving-shaped database, from its v1-shaped copy of the full
    warehouse (written beside ``target`` and removed afterwards)."""
    scoped = target.with_name(target.stem + "-scope.duckdb")
    build_scope(warehouse or paths.cricket_warehouse_path(), competition, scoped)
    try:
        return export_serving(scoped, target, updates=updates)
    finally:
        scoped.unlink(missing_ok=True)


def run_export_competitions(
    *, warehouse: Path | None = None, updates: Path | None = None
) -> dict[str, dict[str, int]]:
    """Export and put in place the serving database of every served competition
    besides the IPL's (``run_export``); row counts by competition."""
    ingest = updates or paths.sync_dir() / "ingest.duckdb"
    found: dict[str, dict[str, int]] = {}
    for competition in exported_competitions():
        final = paths.serving_path(competition)
        staging = final.with_name(final.name + ".export")
        found[competition] = run_export_competition(
            competition,
            staging,
            warehouse=warehouse,
            updates=ingest if ingest.exists() else None,
        )
        publish(staging, final)
    return found


def player_competitions() -> list[str]:
    """The selected competitions the players database covers."""
    return [c.id for c in selected_competitions() if c.format in PLAYER_FORMATS]


def run_export_players(
    *, warehouse: Path | None = None, target: Path | None = None
) -> dict[str, int]:
    """Export the players database and put it in place (beside it while the API has it
    open). Nothing to do when no T20 competition is selected."""
    competitions = player_competitions()
    if not competitions:
        return {}
    final = target or paths.players_path()
    staging = final.with_name(final.name + ".export")
    counts = export_players(warehouse or paths.cricket_warehouse_path(), staging, competitions)
    publish(staging, final)
    return counts


def write_reports(main_report: Path, validation: ValidationReport) -> list[Path]:
    """The main data-quality report and one per reported competition; the files written."""
    main_report.parent.mkdir(parents=True, exist_ok=True)
    main_report.write_text(
        render_report(paths.warehouse_path(), validation, paths.cricket_warehouse_path()),
        encoding="utf-8",
        newline="\n",
    )
    written = [main_report]
    for competition in selected_competitions():
        if competition.format not in REPORTED_FORMATS or competition.id in SCOPED:
            continue
        target = report_path_for(main_report, competition.id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            render_competition_report(paths.cricket_warehouse_path(), validation, competition),
            encoding="utf-8",
            newline="\n",
        )
        written.append(target)
    return written


def run_validate(
    *, warehouse: Path | None = None, require_all_golden: bool = True
) -> ValidationReport:
    target = warehouse or paths.cricket_warehouse_path()
    report = validate(target, require_all_golden=require_all_golden)
    save_validation(report, target)
    return report


def save_validation(report: ValidationReport, warehouse: Path) -> None:
    """Write ``validation.json`` beside the warehouse (read by the data-quality report)."""
    summary = {
        "passed": report.passed,
        "checks": [asdict(c) for c in report.checks],
        "golden": [asdict(g) for g in report.golden],
    }
    (warehouse.parent / "validation.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )


def run_enrich_players(*, warehouse: Path | None = None, refresh: bool = False) -> dict[str, int]:
    """Add Wikidata + Wikipedia attributes to reference/player_attributes.csv (network).

    Covers every player in the full warehouse with an ESPNcricinfo id; a player
    Cricsheet knows by several ids is matched on whichever Wikidata records. Players
    already in the file keep their row unless ``refresh``: re-reading Wikipedia can
    change an existing player's attributes, and with them the inputs of the
    committed models.
    """
    con = duckdb.connect(str(warehouse or paths.cricket_warehouse_path()), read_only=True)
    try:
        ids: dict[str, list[str]] = {}
        for pid, value in con.execute(
            f"""
            SELECT player_id, value FROM player_identifiers
            WHERE source IN {CRICINFO_SOURCES!r} ORDER BY player_id, source
            """
        ).fetchall():
            ids.setdefault(str(pid), []).append(str(value))
    finally:
        con.close()
    target = paths.reference_dir() / ATTRIBUTES_FILE
    kept = {} if refresh else enrich.read_rows(target)
    todo = {pid: found for pid, found in ids.items() if pid not in kept}
    facts = enrich.fetch_wikidata([ci for found in todo.values() for ci in found])
    players = [
        (pid, next((ci for ci in found if ci in facts), found[0])) for pid, found in todo.items()
    ]
    titles = [record["enwiki"] for record in facts.values() if "enwiki" in record]
    fetched = enrich.build_rows(players, facts, enrich.fetch_wikitext(titles))
    rows = sorted([*kept.values(), *fetched], key=lambda row: row["player_id"])
    applied = enrich.apply_overrides(rows, paths.reference_dir() / OVERRIDES_FILE)
    enrich.write_rows(rows, target)
    return {
        "players": len(rows),
        "looked_up": len(todo),
        "found_on_wikidata": sum(1 for _, ci in players if ci in facts),
        "with_batting_hand": sum(1 for r in rows if r["batting_hand"]),
        "with_bowling_type": sum(1 for r in rows if r["bowling_type"]),
        "overrides_applied": applied,
    }
