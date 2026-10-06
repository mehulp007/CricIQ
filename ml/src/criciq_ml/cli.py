"""``criciq-ml``: train, evaluate and serve the CricIQ models.

Typical use::

    criciq-ml train win_probability    # tune, evaluate, backtest; register and promote if gated
    criciq-ml train score_projection
    criciq-ml train ball_outcome
    criciq-ml train ratings    # rating shrinkage and stability (reads the scored serving database)
    criciq-ml train simulator  # backtest the match simulator on the test seasons
    criciq-ml score     # score every ball with the current models into the serving database
    criciq-ml report    # model cards + the Model Insights data bundled with the web app

Deployments only run ``score``: training is an explicit, reviewed step whose
artifacts are committed under ``models/``.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from criciq_core import paths
from criciq_core.publish import current, publish
from criciq_ml import ball_outcome_training, ratings, registry, report, scoring, simulator
from criciq_ml.ball_outcome import BallOutcomeModel, load_balls
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
    """The newest serving database (one waiting for the running API to swap it in, if any)."""
    return current(paths.serving_path())


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
    ratings = "ratings"
    simulator = "simulator"


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


def _train_ratings(force: bool, promote: bool) -> None:
    cfg = ratings.load_ratings_config()
    target = registry.version_dir(cfg.version, registry.RATINGS)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    serving = _serving_path()
    data_version = load_inputs(paths.warehouse_path()).data_version
    model, evaluation = _timed(
        "fitting ratings",
        lambda: ratings.train_ratings(serving, cfg, data_version=data_version, log=typer.echo),
    )
    registry.save(model, evaluation, registry.RATINGS)
    levels = [c["stability"] for c in evaluation["components"]]
    typer.echo(
        "  stability: " + ", ".join(f"{levels.count(s)} {s}" for s in ("high", "moderate", "low"))
    )
    typer.echo(f"  wrote {target}")
    _finish(ratings.gate(evaluation), promote, cfg.version, registry.RATINGS)


def _train_simulator(force: bool, promote: bool) -> None:
    cfg = simulator.load_simulator_config()
    target = registry.version_dir(cfg.version, registry.SIMULATOR)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    warehouse = paths.warehouse_path()
    balls = _timed("loading balls", lambda: load_balls(warehouse))
    data_version = load_inputs(warehouse).data_version
    served = registry.load_current_ball_outcome().manifest
    ball_cfg = ball_outcome_training.load_ball_outcome_config()

    def fit(train: pd.DataFrame) -> BallOutcomeModel:
        return BallOutcomeModel.fit(
            train,
            player_scale=float(served["player_scale"]),
            c=float(served["c"]),
            max_iter=ball_cfg.model.max_iter,
        )

    settings, evaluation = _timed(
        "backtesting",
        lambda: simulator.run(
            _serving_path(), balls, fit, cfg, data_version=data_version, log=typer.echo
        ),
    )
    registry.save(settings, evaluation, registry.SIMULATOR)
    typer.echo(f"  wrote {target}")
    _finish(simulator.gate(evaluation), promote, cfg.version, registry.SIMULATOR)


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
    elif model is ModelName.ball_outcome:
        _train_ball_outcome(force, promote)
    elif model is ModelName.simulator:
        _train_simulator(force, promote)
    else:
        _train_ratings(force, promote)


@app.command()
def score(
    serving: Annotated[Path | None, typer.Option(help="Serving database to update.")] = None,
    warehouse: Annotated[Path | None, typer.Option(help="Warehouse to read.")] = None,
) -> None:
    """Score every historical ball with the current models into the serving database."""
    wp_model = registry.load_current()
    projection_model = registry.load_current_projection()
    inputs = _timed("loading", lambda: load_inputs(warehouse or paths.warehouse_path()))
    states = _timed(
        "building features", lambda: build_states(inputs, load_config().feature_config())
    )
    final = serving or paths.serving_path()
    # Score one working copy and put it in place at the end, so a failure leaves
    # nothing half-scored and the running API can keep its database open.
    target = final.with_name(final.name + ".scoring")
    shutil.copyfile(serving or _serving_path(), target)

    try:
        predictions = _timed("win probability", lambda: scoring.score_states(wp_model, states))
        predictions, scale = _timed(
            "pressure and momentum",
            lambda: scoring.add_pressure(wp_model, states, predictions, inputs),
        )
        count = _timed("publishing", lambda: scoring.publish(target, predictions, wp_model, scale))
        typer.echo(f"  {count:,} win probabilities from model {wp_model.version}")

        projections = _timed(
            "score projection", lambda: scoring.score_projections(projection_model, states)
        )
        count = _timed(
            "publishing",
            lambda: scoring.publish_projections(target, projections, projection_model),
        )
        typer.echo(f"  {count:,} score projections from model {projection_model.version}")

        ball_model = registry.load_current_ball_outcome()
        balls = _timed("loading balls", lambda: load_balls(warehouse or paths.warehouse_path()))
        cells = _timed("ball outcomes", lambda: scoring.score_matchups(ball_model, balls))
        count = _timed(
            "publishing",
            lambda: scoring.publish_ball_model(
                target, cells, ball_model, scoring.current_env(balls)
            ),
        )
        typer.echo(f"  {count:,} head-to-head cells from model {ball_model.version} -> {target}")

        rating_constants = registry.load_current_ratings()
        _timed("publishing ratings", lambda: scoring.publish_ratings(target, rating_constants))
        typer.echo(f"  rating constants {rating_constants.version} -> {target}")

        settings = registry.load_current_simulator()
        _timed("publishing simulator settings", lambda: scoring.publish_simulator(target, settings))
        typer.echo(f"  simulator settings {settings.version} -> {target}")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    placed = publish(target, final)
    typer.echo(f"  scored database -> {placed}")


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
