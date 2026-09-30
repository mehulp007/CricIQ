"""Pipeline orchestration: the steps behind each ``criciq-data`` command.

Each step reads the outputs of the previous one from well-known locations
keyed by ``data_version``, so any step can be re-run on its own.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import duckdb

from criciq_core import paths
from criciq_pipelines import enrich
from criciq_pipelines.export import export_serving
from criciq_pipelines.extract import extract_archive
from criciq_pipelines.raw import RawSnapshot, latest_snapshot
from criciq_pipelines.validation import ValidationReport, validate
from criciq_pipelines.warehouse import BuildInputs, build_warehouse

ATTRIBUTES_FILE = "player_attributes.csv"
OVERRIDES_FILE = "player_attributes_overrides.csv"


def interim_dir_for(snapshot: RawSnapshot) -> Path:
    return paths.interim_dir() / snapshot.version


def run_extract(snapshot: RawSnapshot | None = None) -> dict[str, int]:
    snapshot = snapshot or latest_snapshot()
    return extract_archive(snapshot.archive, interim_dir_for(snapshot))


def run_build(
    snapshot: RawSnapshot | None = None, *, warehouse: Path | None = None
) -> dict[str, int]:
    snapshot = snapshot or latest_snapshot()
    interim = interim_dir_for(snapshot)
    if not (interim / "matches.parquet").exists():
        run_extract(snapshot)
    return build_warehouse(
        BuildInputs(
            interim_dir=interim,
            people_csv=snapshot.people,
            data_version=snapshot.version,
            attributes_csv=paths.reference_dir() / ATTRIBUTES_FILE,
        ),
        warehouse or paths.warehouse_path(),
    )


def serving_path() -> Path:
    return paths.exports_dir() / "serving.duckdb"


def run_export(*, warehouse: Path | None = None, target: Path | None = None) -> dict[str, int]:
    return export_serving(warehouse or paths.warehouse_path(), target or serving_path())


def run_validate(
    *, warehouse: Path | None = None, require_all_golden: bool = True
) -> ValidationReport:
    target = warehouse or paths.warehouse_path()
    report = validate(target, require_all_golden=require_all_golden)
    summary = {
        "passed": report.passed,
        "checks": [asdict(c) for c in report.checks],
        "golden": [asdict(g) for g in report.golden],
    }
    (target.parent / "validation.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return report


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
