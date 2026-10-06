"""``criciq-data``: the CricIQ data pipeline command line.

Typical use::

    criciq-data run              # download -> extract -> build -> validate -> report
    criciq-data run --no-download  # rebuild from the latest local snapshot
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from criciq_core import paths
from criciq_pipelines import pipeline, raw
from criciq_pipelines import sync as sync_engine
from criciq_pipelines.report import render_report
from criciq_pipelines.validation import ValidationReport

app = typer.Typer(help="CricIQ data pipeline.", no_args_is_help=True, add_completion=False)


def _timed[T](label: str, step: Callable[[], T]) -> T:
    started = time.perf_counter()
    typer.echo(f"> {label} ...")
    result = step()
    typer.echo(f"  done in {time.perf_counter() - started:.1f}s")
    return result


def _print_counts(counts: dict[str, int]) -> None:
    width = max(len(name) for name in counts)
    for name, count in counts.items():
        typer.echo(f"  {name:<{width}}  {count:>9,}")


def _print_validation(report: ValidationReport) -> None:
    for check in report.checks:
        status = "pass" if check.passed else ("FAIL" if check.severity == "error" else "warn")
        notes = (
            "  notes: " + ", ".join(f"{k} {v}" for k, v in check.notes.items())
            if check.notes
            else ""
        )
        typer.echo(f"  [{status}] {check.id} ({check.violations}){notes}")
        if not check.passed:
            for sample in check.sample[:3]:
                typer.echo(f"         {sample}")
    for golden in report.golden:
        status = "pass" if golden.passed else "FAIL"
        typer.echo(f"  [{status}] golden {golden.match_id}: {golden.description}")
        for problem in golden.mismatches:
            typer.echo(f"         {problem}")


@app.command("paths")
def show_paths() -> None:
    """Print the data locations the pipeline reads from and writes to."""
    rows = {
        "repo root": paths.repo_root(),
        "config": paths.config_dir(),
        "reference": paths.reference_dir(),
        "raw data": paths.raw_dir(),
        "interim": paths.interim_dir(),
        "warehouse (all)": paths.cricket_warehouse_path(),
        "warehouse (IPL)": paths.warehouse_path(),
        "exports": paths.exports_dir(),
        "models": paths.models_dir(),
    }
    width = max(len(name) for name in rows)
    for name, location in rows.items():
        typer.echo(f"{name:<{width}}  {location}")


def _download() -> raw.RawSnapshot:
    archives = pipeline.archives_to_download()
    return _timed(
        f"downloading {', '.join(archives)} from cricsheet.org", lambda: raw.download(archives)
    )


@app.command()
def download() -> None:
    """Download the Cricsheet archives of the selected competitions and the register.

    Competitions come from CRICIQ_COMPETITIONS (comma separated), else all of them.
    """
    snapshot = _download()
    typer.echo(f"  data version: {snapshot.version}")


@app.command()
def snapshot(
    files: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Register local Cricsheet files as a raw snapshot (offline alternative to download).

    Pass one or more match archives (.zip) and the people register (.csv).
    """
    archives = [f for f in files if f.suffix.lower() == ".zip"]
    people = [f for f in files if f.suffix.lower() == ".csv"]
    if not archives or len(people) != 1:
        raise typer.BadParameter("pass one or more .zip archives and exactly one people .csv")
    result = raw.store_snapshot(archives, people[0])
    typer.echo(f"data version: {result.version}")


@app.command()
def extract() -> None:
    """Flatten the latest snapshot into interim Parquet tables."""
    _print_counts(_timed("extracting", pipeline.run_extract))


@app.command()
def build() -> None:
    """Build the warehouse (every selected competition) and the IPL copy the API reads."""
    _print_counts(_timed("building warehouse", pipeline.run_build))


@app.command()
def export() -> None:
    """Export the read-only serving database the API ships with."""
    _print_counts(_timed("exporting serving database", pipeline.run_export))
    typer.echo(f"  wrote {pipeline.serving_path()}")


@app.command("validate")
def validate_cmd(
    allow_missing_golden: Annotated[
        bool, typer.Option(help="Skip golden matches absent from the data (fixtures).")
    ] = False,
) -> None:
    """Run invariant checks and golden scorecards; exit non-zero on failure."""
    report = _timed(
        "validating",
        lambda: pipeline.run_validate(require_all_golden=not allow_missing_golden),
    )
    _print_validation(report)
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def report(
    output: Annotated[Path | None, typer.Option(help="Markdown file to write.")] = None,
) -> None:
    """Write the data-quality report (docs/data-quality-report.md)."""
    target = output or paths.repo_root() / "docs" / "data-quality-report.md"
    validation = pipeline.run_validate()
    target.write_text(
        render_report(paths.warehouse_path(), validation, paths.cricket_warehouse_path()),
        encoding="utf-8",
        newline="\n",
    )
    typer.echo(f"wrote {target}")


@app.command("enrich-players")
def enrich_players() -> None:
    """Refresh reference/player_attributes.csv from Wikidata + Wikipedia (needs network)."""
    _print_counts(_timed("enriching player attributes", pipeline.run_enrich_players))
    typer.echo("  rebuild the warehouse to pick up the new attributes: criciq-data build")


@app.command()
def run(
    fetch: Annotated[
        bool, typer.Option("--download/--no-download", help="Fetch fresh data first.")
    ] = True,
    report_path: Annotated[
        Path | None, typer.Option("--report", help="Where to write the data-quality report.")
    ] = None,
) -> None:
    """Full rebuild: download, extract, build, validate, report and export."""
    snapshot = _download() if fetch else raw.latest_snapshot()
    typer.echo(f"  data version: {snapshot.version}")
    _print_counts(_timed("extracting", lambda: pipeline.run_extract(snapshot)))
    _print_counts(_timed("building warehouse", lambda: pipeline.run_build(snapshot)))
    validation = _timed("validating", pipeline.run_validate)
    _print_validation(validation)
    target = report_path or paths.repo_root() / "docs" / "data-quality-report.md"
    target.write_text(
        render_report(paths.warehouse_path(), validation, paths.cricket_warehouse_path()),
        encoding="utf-8",
        newline="\n",
    )
    typer.echo(f"> wrote {target}")
    if not validation.passed:
        raise typer.Exit(code=1)
    recorded = _timed(
        "recording the ingest log",
        lambda: sync_engine.record_snapshot(
            snapshot,
            kind="full" if fetch else "rebuild",
            warehouse=paths.cricket_warehouse_path(),
        ),
    )
    _print_changes(recorded)
    _print_counts(_timed("exporting serving database", pipeline.run_export))


_FEEDS = {
    "auto": None,
    "7": sync_engine.WEEK_FEED,
    "30": sync_engine.MONTH_FEED,
    "full": sync_engine.FULL,
}


def _print_changes(result: sync_engine.SyncResult, label: str | None = None) -> None:
    """What a run took in (after any quarantine)."""
    lead = label or f"{result.checked:,} matches checked"
    typer.echo(
        f"  {lead}: {result.new:,} new, {result.corrected:,} corrected, "
        f"{result.withdrawn:,} withdrawn, {len(result.quarantined):,} quarantined"
    )
    for q in result.quarantined:
        typer.echo(f"    quarantined {q.match_id} ({q.competition_id}): {q.reason}")


@app.command("sync")
def sync_cmd(
    feed: Annotated[
        str,
        typer.Option(
            help="auto (by time since the last sync), 7 or 30 (days of Cricsheet's recent "
            "additions) or full (every archive; also finds withdrawn matches)."
        ),
    ] = "auto",
    score: Annotated[
        bool, typer.Option("--score/--no-score", help="Score new balls with the models.")
    ] = True,
    retry_quarantined: Annotated[
        bool, typer.Option(help="Try quarantined matches again (e.g. after a config fix).")
    ] = False,
) -> None:
    """Bring every competition up to date from Cricsheet, changing only what changed."""
    if feed not in _FEEDS:
        raise typer.BadParameter(f"feed must be one of {', '.join(_FEEDS)}")
    started = time.perf_counter()
    try:
        result = sync_engine.sync(
            feed=_FEEDS[feed], score=score, retry_quarantined=retry_quarantined, log=typer.echo
        )
    except sync_engine.SyncError as exc:
        typer.echo(f"sync failed, nothing changed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if result.status == "up_to_date":
        typer.echo(f"  up to date ({result.data_version})")
    else:
        _print_changes(result, "taken in")
        typer.echo(f"  data version: {result.data_version}")
        if result.serving is not None and result.serving != paths.serving_path():
            typer.echo(f"  the running API will switch to the new data ({result.serving.name})")
    typer.echo(f"  done in {time.perf_counter() - started:.0f}s")


@app.command("sync-status")
def sync_status(
    runs: Annotated[int, typer.Option(help="How many recent runs to list.")] = 10,
) -> None:
    """Show the data version, recent syncs and quarantined matches."""
    try:
        report = sync_engine.status(runs)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(f"data version: {report.data_version}")
    typer.echo("matches: " + ", ".join(f"{n:,} {s}" for s, n in report.counts.items()))
    if report.last_update:
        u = report.last_update
        typer.echo(
            f"last update: {u['started_at']:%Y-%m-%d %H:%M} UTC ({u['kind']}, {u['feed']}): "
            f"{u['new']} new, {u['corrected']} corrected, {u['withdrawn']} withdrawn"
        )
    typer.echo("recent runs:")
    for r in report.runs:
        typer.echo(
            f"  {r['started_at']:%Y-%m-%d %H:%M}  {r['kind']:<7} {r['status']:<10} "
            f"{r['new']:>4} new {r['corrected']:>3} corrected {r['withdrawn']:>3} withdrawn "
            f"{r['quarantined']:>3} quarantined  {r['seconds']:5.0f}s  {r['feed']}"
            + (f"  ({r['detail']})" if r["detail"] else "")
        )
    if report.quarantined:
        typer.echo("quarantined:")
        for q in report.quarantined:
            typer.echo(f"  {q['match_id']} {q['competition_id']} {q['match_date']}: {q['detail']}")


@app.callback()
def main() -> None:
    """CricIQ data pipeline."""


if __name__ == "__main__":
    app()
