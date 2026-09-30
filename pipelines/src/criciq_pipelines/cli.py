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
        typer.echo(f"  [{status}] {check.id} ({check.violations})")
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
        "warehouse": paths.warehouse_path(),
        "exports": paths.exports_dir(),
        "models": paths.models_dir(),
    }
    width = max(len(name) for name in rows)
    for name, location in rows.items():
        typer.echo(f"{name:<{width}}  {location}")


@app.command()
def download() -> None:
    """Download the latest Cricsheet IPL archive and people register."""
    snapshot = _timed("downloading from cricsheet.org", raw.download)
    typer.echo(f"  data version: {snapshot.version}")


@app.command()
def snapshot(
    archive: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    people: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Register local Cricsheet files as a raw snapshot (offline alternative to download)."""
    result = raw.store_snapshot(archive, people)
    typer.echo(f"data version: {result.version}")


@app.command()
def extract() -> None:
    """Flatten the latest snapshot into interim Parquet tables."""
    _print_counts(_timed("extracting", pipeline.run_extract))


@app.command()
def build() -> None:
    """Build the normalized DuckDB warehouse from the latest snapshot."""
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
    target.write_text(render_report(paths.warehouse_path(), validation), encoding="utf-8")
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
    if fetch:
        snapshot = _timed("downloading from cricsheet.org", raw.download)
    else:
        snapshot = raw.latest_snapshot()
    typer.echo(f"  data version: {snapshot.version}")
    _print_counts(_timed("extracting", lambda: pipeline.run_extract(snapshot)))
    _print_counts(_timed("building warehouse", lambda: pipeline.run_build(snapshot)))
    validation = _timed("validating", pipeline.run_validate)
    _print_validation(validation)
    target = report_path or paths.repo_root() / "docs" / "data-quality-report.md"
    target.write_text(render_report(paths.warehouse_path(), validation), encoding="utf-8")
    typer.echo(f"> wrote {target}")
    if not validation.passed:
        raise typer.Exit(code=1)
    _print_counts(_timed("exporting serving database", pipeline.run_export))


@app.callback()
def main() -> None:
    """CricIQ data pipeline."""


if __name__ == "__main__":
    app()
