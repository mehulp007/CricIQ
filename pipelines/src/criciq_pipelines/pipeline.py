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
from criciq_core.publish import publish
from criciq_pipelines import enrich
from criciq_pipelines.export import export_serving
from criciq_pipelines.extract import extract_archive
from criciq_pipelines.raw import RawSnapshot, latest_snapshot
from criciq_pipelines.reference import Competition, load_competitions
from criciq_pipelines.scope import build_scope
from criciq_pipelines.validation import ValidationReport, validate
from criciq_pipelines.warehouse import BuildInputs, build_warehouse

ATTRIBUTES_FILE = "player_attributes.csv"
OVERRIDES_FILE = "player_attributes_overrides.csv"


# Competitions whose v1-shaped warehouse the export and the models read.
SCOPED = ("IPL",)


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
    """Build the full warehouse, then the v1-shaped copy of each scoped competition.

    Without arguments this builds the current data state. ``scopes`` maps a scoped
    competition to where its copy goes (default: its usual warehouse path).
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
    return counts


def scoped_competitions() -> list[str]:
    """The scoped competitions among the selected ones."""
    selected = {c.id for c in selected_competitions()}
    return [c for c in SCOPED if c in selected]


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


def run_enrich_players(*, warehouse: Path | None = None) -> dict[str, int]:
    """Refresh reference/player_attributes.csv from Wikidata + Wikipedia (network)."""
    con = duckdb.connect(str(warehouse or paths.warehouse_path()), read_only=True)
    try:
        players = [
            (str(pid), str(value))
            for pid, value in con.execute(
                "SELECT player_id, value FROM player_identifiers WHERE source = 'cricinfo'"
            ).fetchall()
        ]
    finally:
        con.close()
    facts = enrich.fetch_wikidata([cricinfo for _, cricinfo in players])
    titles = [record["enwiki"] for record in facts.values() if "enwiki" in record]
    rows = enrich.build_rows(players, facts, enrich.fetch_wikitext(titles))
    applied = enrich.apply_overrides(rows, paths.reference_dir() / OVERRIDES_FILE)
    enrich.write_rows(rows, paths.reference_dir() / ATTRIBUTES_FILE)
    return {
        "players": len(rows),
        "with_wikidata": sum(1 for _, ci in players if ci in facts),
        "with_batting_hand": sum(1 for r in rows if r["batting_hand"]),
        "with_bowling_type": sum(1 for r in rows if r["bowling_type"]),
        "overrides_applied": applied,
    }
