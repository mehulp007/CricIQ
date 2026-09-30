"""``criciq-ml``: train, evaluate and serve the CricIQ models.

Typical use::

    criciq-ml train     # tune, evaluate, backtest; register and (if the gate passes) promote
    criciq-ml score     # score every ball with the current model into the serving database
    criciq-ml report    # model card + the Model Insights data bundled with the web app

Deployments only run ``score``: training is an explicit, reviewed step whose
artifacts are committed under ``models/``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from criciq_core import paths
from criciq_ml import registry, report, scoring
from criciq_ml.config import load_config
from criciq_ml.data import load_inputs
from criciq_ml.features import build_states
from criciq_ml.training import train_model

app = typer.Typer(help="CricIQ models.", no_args_is_help=True, add_completion=False)


def _timed[T](label: str, step: Callable[[], T]) -> T:
    started = time.perf_counter()
    typer.echo(f"> {label} ...")
    result = step()
    typer.echo(f"  done in {time.perf_counter() - started:.1f}s")
    return result


def _serving_path() -> Path:
    return paths.exports_dir() / "serving.duckdb"


def _states(warehouse: Path) -> tuple[pd.DataFrame, str]:
    """Features for every match state (also saved for notebooks and debugging)."""
    inputs = load_inputs(warehouse)
    states = build_states(inputs, load_config().feature_config())
    target = paths.data_dir() / "features" / inputs.data_version / "wp_states.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    states.to_parquet(target, index=False)
    return states, inputs.data_version


@app.command()
def features(
    warehouse: Annotated[Path | None, typer.Option(help="Warehouse to read.")] = None,
) -> None:
    """Build the leak-free match-state feature table."""
    states, version = _timed(
        "building features", lambda: _states(warehouse or paths.warehouse_path())
    )
    typer.echo(f"  {len(states):,} match states for data version {version}")


@app.command()
def train(
    promote: Annotated[bool, typer.Option(help="Make it current if the gate passes.")] = True,
    force: Annotated[bool, typer.Option(help="Overwrite an existing version.")] = False,
) -> None:
    """Tune, evaluate and backtest a new model version, then register it."""
    cfg = load_config()
    target = registry.version_dir(cfg.version)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    states, data_version = _timed("building features", lambda: _states(paths.warehouse_path()))
    result = _timed(
        "training", lambda: train_model(states, cfg, data_version=data_version, log=typer.echo)
    )
    registry.save(result.model, result.evaluation)
    test = result.evaluation["test"]
    typer.echo(
        f"  test log loss {test['model']['log_loss']:.4f} "
        f"(baseline {test['baseline']['log_loss']:.4f}), brier {test['model']['brier']:.4f}, "
        f"ECE {test['model']['ece']:.4f}"
    )
    typer.echo(f"  wrote {target}")

    current = registry.current_version()
    previous = registry.load_evaluation(current) if current and current != cfg.version else None
    problems = registry.gate(result.evaluation, previous, cfg.gate.max_log_loss_regression)
    for problem in problems:
        typer.echo(f"  [gate] {problem}")
    if problems:
        raise typer.Exit(code=1)
    if promote:
        registry.promote(cfg.version)
        typer.echo(f"  promoted {cfg.version} to current")


@app.command()
def score(
    serving: Annotated[Path | None, typer.Option(help="Serving database to update.")] = None,
    warehouse: Annotated[Path | None, typer.Option(help="Warehouse to read.")] = None,
) -> None:
    """Score every historical ball with the current model into the serving database."""
    model = registry.load_current()
    states, _ = _timed("building features", lambda: _states(warehouse or paths.warehouse_path()))
    predictions = _timed("scoring", lambda: scoring.score_states(model, states))
    target = serving or _serving_path()
    count = _timed("publishing", lambda: scoring.publish(target, predictions, model))
    typer.echo(f"  {count:,} win probabilities from model {model.version} -> {target}")


@app.command("report")
def report_cmd() -> None:
    """Write the model card and the Model Insights data for the web app."""
    version = registry.current_version()
    if version is None:
        raise typer.BadParameter("no current model; run `criciq-ml train` first")
    written = report.write_all(version, _serving_path())
    for path in written:
        typer.echo(f"wrote {path}")


@app.callback()
def main() -> None:
    """CricIQ models."""


if __name__ == "__main__":
    app()
