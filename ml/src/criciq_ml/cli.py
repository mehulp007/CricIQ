"""``criciq-ml``: train, evaluate and serve the CricIQ models.

Typical use::

    criciq-ml train win_probability    # tune, evaluate, backtest; register and promote if gated
    criciq-ml train score_projection
    criciq-ml train ball_outcome
    criciq-ml score     # score every ball with the current models into the serving database
    criciq-ml report    # model cards + the Model Insights data bundled with the web app

Deployments only run ``score``: training is an explicit, reviewed step whose
artifacts are committed under ``models/``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from criciq_core import paths
from criciq_ml import ball_outcome_training, registry, report, scoring
from criciq_ml.ball_outcome import load_balls
from criciq_ml.config import load_config
from criciq_ml.data import load_inputs
from criciq_ml.features import build_states
from criciq_ml.projection_training import load_projection_config, train_projection
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


class ModelName(StrEnum):
    win_probability = "win_probability"
    score_projection = "score_projection"
    ball_outcome = "ball_outcome"


def _train_win_probability(force: bool, promote: bool) -> None:
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
    _finish(problems, promote, cfg.version, registry.NAME)


def _train_score_projection(force: bool, promote: bool) -> None:
    cfg = load_projection_config()
    target = registry.version_dir(cfg.version, registry.PROJECTION)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    states, data_version = _timed("building features", lambda: _states(paths.warehouse_path()))
    model, evaluation = _timed(
        "training",
        lambda: train_projection(states, cfg, data_version=data_version, log=typer.echo),
    )
    registry.save(model, evaluation, registry.PROJECTION)
    test = evaluation["test"]
    typer.echo(
        f"  test 80% coverage {test['model']['coverage80']:.1%}, MAE {test['model']['mae']:.2f} "
        f"(par {test['par_baseline']['mae']:.2f}), pinball {test['model']['pinball']:.3f}"
    )
    typer.echo(f"  wrote {target}")
    problems = registry.projection_gate(evaluation, cfg.gate["coverage_band"])
    _finish(problems, promote, cfg.version, registry.PROJECTION)


def _train_ball_outcome(force: bool, promote: bool) -> None:
    cfg = ball_outcome_training.load_ball_outcome_config()
    target = registry.version_dir(cfg.version, registry.BALL_OUTCOME)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    warehouse = paths.warehouse_path()
    balls = _timed("loading balls", lambda: load_balls(warehouse))
    data_version = load_inputs(warehouse).data_version
    model, evaluation = _timed(
        "training",
        lambda: ball_outcome_training.train_ball_outcome(
            balls, cfg, data_version=data_version, log=typer.echo
        ),
    )
    registry.save(model, evaluation, registry.BALL_OUTCOME)
    test = evaluation["test"]
    typer.echo(
        f"  test log loss {test['model']['log_loss']:.4f} "
        f"(baseline {test['baseline']['log_loss']:.4f}); "
        f"head-to-head prior {evaluation['matchups']['served_kappa']:.0f} balls"
    )
    typer.echo(f"  wrote {target}")
    _finish(ball_outcome_training.gate(evaluation), promote, cfg.version, registry.BALL_OUTCOME)


def _finish(problems: list[str], promote: bool, version: str, name: str) -> None:
    for problem in problems:
        typer.echo(f"  [gate] {problem}")
    if problems:
        raise typer.Exit(code=1)
    if promote:
        registry.promote(version, name)
        typer.echo(f"  promoted {name} {version} to current")


@app.command()
def train(
    model: Annotated[ModelName, typer.Argument(help="Which model to train.")],
    promote: Annotated[bool, typer.Option(help="Make it current if the gate passes.")] = True,
    force: Annotated[bool, typer.Option(help="Overwrite an existing version.")] = False,
) -> None:
    """Tune, evaluate and backtest a new model version, then register it."""
    if model is ModelName.win_probability:
        _train_win_probability(force, promote)
    elif model is ModelName.score_projection:
        _train_score_projection(force, promote)
    else:
        _train_ball_outcome(force, promote)


@app.command()
def score(
    serving: Annotated[Path | None, typer.Option(help="Serving database to update.")] = None,
    warehouse: Annotated[Path | None, typer.Option(help="Warehouse to read.")] = None,
) -> None:
    """Score every historical ball with the current models into the serving database."""
    wp_model = registry.load_current()
    projection_model = registry.load_current_projection()
    states, _ = _timed("building features", lambda: _states(warehouse or paths.warehouse_path()))
    target = serving or _serving_path()

    predictions = _timed("win probability", lambda: scoring.score_states(wp_model, states))
    count = _timed("publishing", lambda: scoring.publish(target, predictions, wp_model))
    typer.echo(f"  {count:,} win probabilities from model {wp_model.version}")

    projections = _timed(
        "score projection", lambda: scoring.score_projections(projection_model, states)
    )
    count = _timed(
        "publishing",
        lambda: scoring.publish_projections(target, projections, projection_model),
    )
    typer.echo(f"  {count:,} score projections from model {projection_model.version} -> {target}")

    ball_model = registry.load_current_ball_outcome()
    balls = _timed("loading balls", lambda: load_balls(warehouse or paths.warehouse_path()))
    cells = _timed("ball outcomes", lambda: scoring.score_matchups(ball_model, balls))
    count = _timed(
        "publishing",
        lambda: scoring.publish_ball_model(target, cells, ball_model, scoring.current_env(balls)),
    )
    typer.echo(f"  {count:,} head-to-head cells from model {ball_model.version} -> {target}")


@app.command("report")
def report_cmd() -> None:
    """Write the model cards and the Model Insights data for the web app."""
    for path in report.write_all(_serving_path()):
        typer.echo(f"wrote {path}")


@app.callback()
def main() -> None:
    """CricIQ models."""


if __name__ == "__main__":
    app()
