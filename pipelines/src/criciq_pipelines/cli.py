"""``criciq-data`` command line entry point.

Pipeline steps (download, extract, normalize, validate, features, export) are
added here milestone by milestone; see docs/PLAN.md section 4.4.
"""

from __future__ import annotations

import typer

from criciq_core import paths

app = typer.Typer(help="CricIQ data pipeline.", no_args_is_help=True)


@app.command("paths")
def show_paths() -> None:
    """Print the data locations the pipeline reads from and writes to."""
    rows = {
        "repo root": paths.repo_root(),
        "config": paths.config_dir(),
        "raw data": paths.raw_dir(),
        "interim": paths.interim_dir(),
        "warehouse": paths.warehouse_path(),
        "exports": paths.exports_dir(),
        "models": paths.models_dir(),
    }
    width = max(len(name) for name in rows)
    for name, location in rows.items():
        typer.echo(f"{name:<{width}}  {location}")


@app.callback()
def main() -> None:
    """CricIQ data pipeline."""


if __name__ == "__main__":
    app()
