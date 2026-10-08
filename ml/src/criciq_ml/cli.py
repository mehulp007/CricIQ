"""``criciq-ml``: train, evaluate and serve the CricIQ models.

Typical use::

    criciq-ml train win_probability --group leagues  # tune, evaluate, backtest; promote if gated
    criciq-ml train score_projection --group t20i
    criciq-ml train ball_outcome --group odi
    criciq-ml train ratings --group leagues    # rating shrinkage and stability (scored players)
    criciq-ml train simulator --group leagues  # backtest the match simulator on the test seasons
    criciq-ml score     # score every ball with the models serving each competition
    criciq-ml report --group t20i  # model cards + the Model Insights data bundled with the web app

Each model group (``config/model_groups.yaml``: the IPL, the other T20 leagues,
T20 internationals, ODIs) trains on its own competitions only. ``scripts/train_group.py``
(``just train-group <group>``) trains a whole group in order and writes a summary.

Deployments only run ``score``: training is an explicit, reviewed step whose
artifacts are committed under ``models/``.
"""

from __future__ import annotations

import contextlib
import functools
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import duckdb
import pandas as pd
import typer

from criciq_core import paths
from criciq_core.groups import ModelGroup, group, group_of, model_groups
from criciq_core.phases import MODEL_FORMAT, default_phase_config, model_format, use_format
from criciq_core.publish import current, publish
from criciq_ml import (
    ball_outcome_training,
    comparison,
    formats,
    players_scoring,
    ratings,
    registry,
    report,
    scoring,
    simulator,
)
from criciq_ml.ball_outcome import BallOutcomeModel, load_balls
from criciq_ml.config import load_config
from criciq_ml.data import Inputs, load_inputs
from criciq_ml.features import FeatureConfig, build_states
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


# The competition whose v1 models the pooled versions are compared with.
IPL = "IPL"
# The pooled T20 copy of the warehouse (criciq_pipelines.pipeline.POOLED).
POOLED = "T20"


def _states(
    warehouse: Path, feature_config: FeatureConfig | None = None
) -> tuple[pd.DataFrame, str]:
    """Features for every match state (also saved for notebooks and debugging)."""
    inputs = load_inputs(warehouse)
    states = build_states(inputs, feature_config or load_config().feature_config())
    name = f"{warehouse.stem}_states.parquet"
    target = paths.data_dir() / "features" / inputs.data_version / name
    target.parent.mkdir(parents=True, exist_ok=True)
    states.to_parquet(target, index=False)
    return states, inputs.data_version


def _data_version(warehouse: Path) -> str:
    """The data version of a warehouse copy (of any format)."""
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        row = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
    finally:
        con.close()
    assert row is not None
    return str(row[0])


def _for_training(states: pd.DataFrame) -> pd.DataFrame:
    """The training protocols split by ``season``: here the match's calendar year,
    so splits are date cut-offs (a BBL season spans two years). For the IPL the
    two are the same."""
    return states.assign(season=states["year"])


def _compare_ipl_win_probability(predictions: pd.DataFrame, version: str) -> dict[str, Any]:
    """The pooled version against the IPL's current one on the IPL's test balls."""
    ipl_version = registry.current_version(registry.NAME, IPL)
    assert ipl_version is not None
    ipl_model = registry.load_current(registry.NAME, IPL)
    recorded = registry.load_evaluation(ipl_version)
    ipl_states, _ = _states(paths.warehouse_path(IPL), ipl_model.feature_config)
    rebuilt = comparison.v1_win_probability(_for_training(ipl_states), load_config(), recorded)
    comparison.check_reproduced(rebuilt, recorded)
    mine = predictions[predictions["competition_id"] == IPL]
    return comparison.compare(rebuilt, mine, v1_version=ipl_version, v2_version=version)


@app.command()
def features(
    warehouse: Annotated[Path | None, typer.Option(help="Warehouse to read.")] = None,
) -> None:
    """Build the leak-free match-state feature table."""
    cfg = load_config()
    states, version = _timed(
        "building features",
        lambda: _states(warehouse or paths.warehouse_path(cfg.scope), cfg.feature_config()),
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
    states, data_version = _timed(
        "building features",
        lambda: _states(paths.warehouse_path(cfg.scope), cfg.feature_config()),
    )
    result = _timed(
        "training",
        lambda: train_model(_for_training(states), cfg, data_version=data_version, log=typer.echo),
    )
    pooled = cfg.scope != IPL and IPL in set(states["competition_id"])
    if pooled:
        assert result.predictions is not None
        predictions = result.predictions
        result.evaluation["ipl_comparison"] = _timed(
            "comparing with the IPL's current model on its test seasons",
            lambda: _compare_ipl_win_probability(predictions, cfg.version),
        )
    registry.save(result.model, result.evaluation)
    test = result.evaluation["test"]
    typer.echo(
        f"  test log loss {test['model']['log_loss']:.4f} "
        f"(baseline {test['baseline']['log_loss']:.4f}), brier {test['model']['brier']:.4f}, "
        f"ECE {test['model']['ece']:.4f}"
    )
    for line in test.get("by_competition", []):
        typer.echo(
            f"    {line['competition']:5} log loss {line['model']['log_loss']:.4f} "
            f"(baseline {line['baseline']['log_loss']:.4f}, {line['matches']} matches)"
        )
    typer.echo(f"  wrote {target}")

    current = registry.current_version()
    previous = registry.load_evaluation(current) if current and current != cfg.version else None
    problems = registry.gate(result.evaluation, previous, cfg.gate.max_log_loss_regression)
    ipl_version = registry.current_version(registry.NAME, IPL)
    _finish(problems, promote, cfg.version, registry.NAME)
    if pooled and promote:
        _serve_ipl(result.evaluation["ipl_comparison"], registry.NAME, ipl_version)


def _serve_ipl(result: dict[str, Any], name: str, ipl_version: str | None) -> None:
    """After promoting a pooled version: the IPL takes it only if it is no worse there."""
    v1, v2 = result["v1"], result["v2"]
    typer.echo(
        f"  IPL test log loss: {v2['log_loss']:.4f} pooled vs {v1['log_loss']:.4f} "
        f"({v1['version']})"
    )
    if comparison.serves_ipl(result):
        registry.release(name, IPL)
        typer.echo("  the pooled version serves the IPL too")
    elif ipl_version is not None:
        registry.promote(ipl_version, name, IPL)
        typer.echo(f"  the IPL keeps {ipl_version}")


def _train_score_projection(force: bool, promote: bool) -> None:
    cfg = load_projection_config()
    target = registry.version_dir(cfg.version, registry.PROJECTION)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    feature_config = load_config().feature_config()
    states, data_version = _timed(
        "building features", lambda: _states(paths.warehouse_path(cfg.scope), feature_config)
    )
    model, evaluation, predictions = _timed(
        "training",
        lambda: train_projection(
            _for_training(states), cfg, data_version=data_version, log=typer.echo
        ),
    )
    model.manifest["feature_config"] = asdict(feature_config)
    pooled = cfg.scope != IPL and IPL in set(states["competition_id"])
    if pooled:
        evaluation["ipl_comparison"] = _timed(
            "comparing with the IPL's current projection on its test seasons",
            lambda: _compare_ipl_projection(predictions, cfg.version),
        )
    registry.save(model, evaluation, registry.PROJECTION)
    test = evaluation["test"]
    typer.echo(
        f"  test 80% coverage {test['model']['coverage80']:.1%}, MAE {test['model']['mae']:.2f} "
        f"(par {test['par_baseline']['mae']:.2f}), pinball {test['model']['pinball']:.3f}"
    )
    for line in test.get("by_competition", []):
        typer.echo(
            f"    {line['competition']:5} pinball {line['model']['pinball']:.3f} "
            f"(par {line['par_baseline']['pinball']:.3f}), "
            f"coverage {line['model']['coverage80']:.1%}"
        )
    typer.echo(f"  wrote {target}")
    problems = registry.projection_gate(evaluation, cfg.gate["coverage_band"])
    ipl_version = registry.current_version(registry.PROJECTION, IPL)
    _finish(problems, promote, cfg.version, registry.PROJECTION)
    if pooled and promote:
        _serve_ipl_projection(evaluation["ipl_comparison"], ipl_version)


def _compare_ipl_projection(predictions: pd.DataFrame, version: str) -> dict[str, Any]:
    """The pooled projection against the IPL's current one on the IPL's test balls."""
    ipl_version = registry.current_version(registry.PROJECTION, IPL)
    assert ipl_version is not None
    ipl_model = registry.load_current_projection(IPL)
    recorded = registry.load_evaluation(ipl_version, registry.PROJECTION)
    ipl_states, _ = _states(paths.warehouse_path(IPL), ipl_model.feature_config)
    rebuilt = comparison.v1_projection(
        _for_training(ipl_states), load_projection_config(), recorded
    )
    comparison.check_projection_reproduced(rebuilt, recorded)
    mine = predictions[predictions["competition_id"] == IPL]
    band = load_projection_config().gate["coverage_band"]
    return comparison.compare_projection(
        rebuilt, mine, v1_version=ipl_version, v2_version=version, band=(band[0], band[1])
    )


def _serve_ipl_projection(result: dict[str, Any], ipl_version: str | None) -> None:
    v1, v2 = result["v1"], result["v2"]
    typer.echo(
        f"  IPL test pinball: {v2['pinball']:.3f} pooled vs {v1['pinball']:.3f} "
        f"({v1['version']}); 80% coverage {v2['coverage80']:.1%} vs {v1['coverage80']:.1%}"
    )
    if result["no_worse"]:
        registry.release(registry.PROJECTION, IPL)
        typer.echo("  the pooled projection serves the IPL too")
    elif ipl_version is not None:
        registry.promote(ipl_version, registry.PROJECTION, IPL)
        typer.echo(f"  the IPL keeps {ipl_version}")


def _train_ball_outcome(force: bool, promote: bool) -> None:
    cfg = ball_outcome_training.load_ball_outcome_config()
    target = registry.version_dir(cfg.version, registry.BALL_OUTCOME)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    warehouse = paths.warehouse_path(cfg.scope)
    balls = _timed("loading balls", lambda: _for_training(load_balls(warehouse)))
    data_version = load_inputs(warehouse).data_version
    model, evaluation, predictions = _timed(
        "training",
        lambda: ball_outcome_training.train_ball_outcome(
            balls, cfg, data_version=data_version, log=typer.echo
        ),
    )
    pooled = cfg.scope != IPL and IPL in set(balls["competition_id"])
    if pooled:
        evaluation["ipl_comparison"] = _timed(
            "comparing with the IPL's current ball model on its test seasons",
            lambda: _compare_ipl_ball_outcome(predictions, cfg.version, cfg.model.max_iter),
        )
    registry.save(model, evaluation, registry.BALL_OUTCOME)
    test = evaluation["test"]
    typer.echo(
        f"  test log loss {test['model']['log_loss']:.4f} "
        f"(baseline {test['baseline']['log_loss']:.4f}); "
        f"head-to-head prior {evaluation['matchups']['served_kappa']:.0f} balls"
    )
    for line in test.get("by_competition", []):
        typer.echo(
            f"    {line['competition']:5} log loss {line['model']['log_loss']:.4f} "
            f"(baseline {line['baseline']['log_loss']:.4f})"
        )
    typer.echo(f"  wrote {target}")
    ipl_version = registry.current_version(registry.BALL_OUTCOME, IPL)
    _finish(ball_outcome_training.gate(evaluation), promote, cfg.version, registry.BALL_OUTCOME)
    if pooled and promote:
        _serve_ipl_generic(evaluation["ipl_comparison"], registry.BALL_OUTCOME, ipl_version)


def _compare_ipl_ball_outcome(
    predictions: pd.DataFrame, version: str, max_iter: int
) -> dict[str, Any]:
    """The pooled ball model against the IPL's current one on the IPL's test balls."""
    ipl_version = registry.current_version(registry.BALL_OUTCOME, IPL)
    assert ipl_version is not None
    recorded = registry.load_evaluation(ipl_version, registry.BALL_OUTCOME)
    manifest = registry.load_current_ball_outcome(IPL).manifest
    ipl_balls = _for_training(load_balls(paths.warehouse_path(IPL)))
    rebuilt = comparison.v1_ball_outcome(ipl_balls, recorded, manifest, max_iter)
    comparison.check_ball_reproduced(rebuilt, recorded)
    mine = predictions[predictions["competition_id"] == IPL]
    return comparison.compare_ball_outcome(
        rebuilt, mine, v1_version=ipl_version, v2_version=version
    )


def _serve_ipl_generic(result: dict[str, Any], name: str, ipl_version: str | None) -> None:
    """After promoting a pooled version: the IPL takes it only if it is no worse there."""
    v1, v2 = result["v1"], result["v2"]
    typer.echo(
        f"  IPL test log loss: {v2['log_loss']:.4f} pooled vs {v1['log_loss']:.4f} "
        f"({v1['version']})"
    )
    if result["no_worse"]:
        registry.release(name, IPL)
        typer.echo("  the pooled version serves the IPL too")
    elif ipl_version is not None:
        registry.promote(ipl_version, name, IPL)
        typer.echo(f"  the IPL keeps {ipl_version}")


def _train_ratings(force: bool, promote: bool) -> None:
    cfg = ratings.load_ratings_config()
    target = registry.version_dir(cfg.version, registry.RATINGS)
    if target.exists() and not force:
        typer.echo(f"version {cfg.version} already exists; bump `version` or pass --force")
        raise typer.Exit(code=1)
    data_version = _data_version(paths.warehouse_path())
    if cfg.source == "players":
        players = current(paths.players_path())
        owner = formats.current_group()
        scopes = [
            (s["scope_id"], s["schema_name"])
            for s in players_scoring.scopes(players)
            if (
                s["scope_id"] in owner.competitions
                if owner is not None
                else s["format"] == model_format()
            )
        ]
        if not scopes:
            typer.echo("no scopes of these competitions in the players database")
            raise typer.Exit(code=1)
        # A group of several competitions borrows from its own pool, never from outside.
        pool = owner.id.upper() if owner is not None and len(owner.competitions) > 1 else None
        model, evaluation = _timed(
            "fitting ratings for every scope",
            lambda: ratings.train_scopes(
                players, scopes, cfg, data_version=data_version, log=typer.echo, pool=pool
            ),
        )
        parts = list(evaluation["scopes"].values())
    else:
        serving = _serving_path()
        model, evaluation = _timed(
            "fitting ratings",
            lambda: ratings.train_ratings(serving, cfg, data_version=data_version, log=typer.echo),
        )
        parts = [evaluation]
    registry.save(model, evaluation, registry.RATINGS)
    levels = [c["stability"] for part in parts for c in part["components"]]
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
    ball_cfg = ball_outcome_training.load_ball_outcome_config()
    data_version = _data_version(paths.warehouse_path())
    settings: dict[str, Any] = {}
    evaluations: dict[str, Any] = {}
    # Competitions served by one pooled ball model refit it on the same years: fit once.
    fitted: dict[tuple[str, int, int], BallOutcomeModel] = {}
    for competition in cfg.competitions:
        served = registry.load_current_ball_outcome(competition).manifest
        warehouse = _Sources(paths.warehouse_path(IPL), paths.warehouse_path(POOLED)).warehouse(
            served
        )
        balls = _timed(
            f"loading balls for {competition}",
            functools.partial(_training_balls, warehouse),
        )

        def fit(
            train: pd.DataFrame, served: dict[str, Any] = served, competition: str = competition
        ) -> BallOutcomeModel:
            key = (str(served["version"]), len(train), int(train["season"].max()))
            if key not in fitted:
                fitted[key] = BallOutcomeModel.fit(
                    train,
                    player_scale=float(served["player_scale"]),
                    c=float(served["c"]),
                    max_iter=ball_cfg.model.max_iter,
                    competition_terms="competition" in served.get("extra_groups", []),
                    side_terms="batting_side" in served.get("extra_groups", []),
                )
            return fitted[key].for_competition(competition)

        with tempfile.TemporaryDirectory(prefix="criciq-simulator-") as work:
            serving = _simulation_database(competition, Path(work))
            part, evaluation = _timed(
                f"backtesting {competition}",
                functools.partial(
                    simulator.run,
                    serving,
                    balls,
                    fit,
                    cfg,
                    data_version=data_version,
                    log=typer.echo,
                    competition=competition,
                ),
            )
        settings[competition] = part.manifest
        evaluations[competition] = evaluation
    if cfg.competitions == [IPL]:  # v1 layout
        model, evaluation = simulator.SimulatorSettings(settings[IPL]), evaluations[IPL]
    else:
        common = {"name": cfg.name, "version": cfg.version, "data_version": data_version}
        model = simulator.SimulatorSettings({**common, "competitions": settings})
        evaluation = {**common, "competitions": evaluations}
    registry.save(model, evaluation, registry.SIMULATOR)
    typer.echo(f"  wrote {target}")
    gates = {competition: simulator.gate(part) for competition, part in evaluations.items()}
    if cfg.competitions == [IPL]:  # v1: one competition, one pointer
        _finish(gates[IPL], promote, cfg.version, registry.SIMULATOR)
        return
    # A pooled version serves each competition whose own backtest passed; the others
    # (and the IPL, not backtested here) keep what they have.
    for competition, problems in gates.items():
        for problem in problems:
            typer.echo(f"  [gate] {competition}: {problem}")
    passed = [c for c, problems in gates.items() if not problems]
    if not passed:
        raise typer.Exit(code=1)
    if promote:
        for competition in passed:
            registry.promote(cfg.version, registry.SIMULATOR, competition)
            typer.echo(f"  promoted {registry.SIMULATOR} {cfg.version} for {competition}")


def _training_balls(warehouse: Path) -> pd.DataFrame:
    return _for_training(load_balls(warehouse))


def _simulation_database(competition: str, work: Path) -> Path:
    """A serving-shaped database of one competition: the IPL's own, or one exported by
    the pipeline (``criciq-data export-competition``; this package never imports it)."""
    if competition == IPL:
        return _serving_path()
    command = shutil.which("criciq-data")
    if command is None:
        raise typer.BadParameter("criciq-data is not installed; run `uv sync --all-packages`")
    target = work / f"{competition.lower()}-serving.duckdb"
    subprocess.run(
        [command, "export-competition", competition, "--out", str(target)],
        check=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return target


def _finish(problems: list[str], promote: bool, version: str, name: str) -> None:
    for problem in problems:
        typer.echo(f"  [gate] {problem}")
    if problems:
        raise typer.Exit(code=1)
    if promote:
        registry.promote(version, name)
        typer.echo(f"  promoted {name} {version} to current")


FormatOption = Annotated[
    str,
    typer.Option(
        "--format",
        help="Without --group: the format's models, T20 (the pooled T20 models of V2-3 in "
        "config/models/ and models/) or ODI (the odi group).",
    ),
]
GroupOption = Annotated[
    str | None,
    typer.Option(
        "--group",
        help="The model group (config/model_groups.yaml): ipl, leagues, t20i or odi. "
        "Its models train on its own competitions only.",
    ),
]


@app.command()
def train(
    model: Annotated[ModelName, typer.Argument(help="Which model to train.")],
    promote: Annotated[bool, typer.Option(help="Make it current if the gate passes.")] = True,
    force: Annotated[bool, typer.Option(help="Overwrite an existing version.")] = False,
    match_format: FormatOption = MODEL_FORMAT,
    group_id: GroupOption = None,
) -> None:
    """Tune, evaluate and backtest a new model version, then register it."""
    if group_id is not None:
        with formats.use_group(_group(group_id)):
            _train(model, force, promote)
        return
    with use_format(_format(match_format)):
        _train(model, force, promote)


def _group(value: str) -> ModelGroup:
    try:
        return group(value)
    except KeyError:
        known = ", ".join(g.id for g in model_groups().groups)
        raise typer.BadParameter(f"unknown model group {value!r} (one of {known})") from None


def _format(value: str) -> str:
    """A format's configured name, whatever its case (``odi`` -> ``ODI``)."""
    for name in default_phase_config().formats:
        if name.lower() == value.lower():
            return name
    raise typer.BadParameter(f"unknown format {value!r}")


def _train(model: ModelName, force: bool, promote: bool) -> None:
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


class _Sources:
    """Inputs, match states and balls, each built once per warehouse and settings.

    A model scores from the copy it was fitted on: its group's (the competitions its
    manifest lists, the IPL alone if none), or the pooled T20 copy for the pooled
    versions of V2-3, which span groups. ``copies`` overrides where a copy is, by its
    name (``LEAGUES``, ``T20I``, ``ODI``).
    """

    def __init__(self, ipl: Path, pooled: Path, copies: dict[str, Path] | None = None) -> None:
        self.ipl = ipl
        self.pooled = pooled
        self.copies = copies or {}
        self._inputs: dict[Path, Inputs] = {}
        self._states: dict[tuple[Path, FeatureConfig], pd.DataFrame] = {}
        self._balls: dict[Path, pd.DataFrame] = {}

    def warehouse(self, manifest: dict[str, Any]) -> Path:
        competitions = [str(c) for c in manifest.get("trained_on", {}).get("competitions", [])]
        if not competitions or competitions == [IPL]:
            return self.ipl
        owner = next((g for g in model_groups().groups if g.covers(competitions)), None)
        if owner is None:  # a pooled version, fitted across groups
            return self.pooled
        return self.copies.get(owner.copy_name) or paths.warehouse_path(owner.copy_name)

    def inputs(self, warehouse: Path) -> Inputs:
        if warehouse not in self._inputs:
            self._inputs[warehouse] = _timed(
                f"loading {warehouse.stem}", lambda: load_inputs(warehouse)
            )
        return self._inputs[warehouse]

    def states(self, warehouse: Path, cfg: FeatureConfig) -> pd.DataFrame:
        key = (warehouse, cfg)
        if key not in self._states:
            inputs = self.inputs(warehouse)
            self._states[key] = _timed(
                f"building {warehouse.stem} features", lambda: build_states(inputs, cfg)
            )
        return self._states[key]

    def balls(self, warehouse: Path) -> pd.DataFrame:
        if warehouse not in self._balls:
            self._balls[warehouse] = _timed(
                f"loading {warehouse.stem} balls", lambda: load_balls(warehouse)
            )
        return self._balls[warehouse]


def _of(frame: pd.DataFrame, competitions: set[str]) -> pd.DataFrame:
    return frame[frame["competition_id"].isin(competitions)].reset_index(drop=True)


@app.command()
def score(
    serving: Annotated[Path | None, typer.Option(help="The IPL's serving database.")] = None,
    warehouse: Annotated[Path | None, typer.Option(help="The IPL's warehouse copy.")] = None,
    pooled: Annotated[Path | None, typer.Option(help="The pooled T20 warehouse copy.")] = None,
    copy: Annotated[
        list[str] | None,
        typer.Option(
            help="A model group's warehouse copy, as NAME=PATH (LEAGUES, T20I, ODI; "
            "repeatable; by default data/warehouse/<name>.duckdb)."
        ),
    ] = None,
    players: Annotated[Path | None, typer.Option(help="Players database to update.")] = None,
    serving_db: Annotated[
        list[str] | None,
        typer.Option(
            help="Another competition's serving database, as COMPETITION=PATH (repeatable). "
            "By default every serving-<competition>.duckdb in the exports folder."
        ),
    ] = None,
) -> None:
    """Score every historical ball with the models serving each competition (its model
    group's): the IPL's serving database, every other competition's, then the players
    database."""
    sources = _Sources(
        warehouse or paths.warehouse_path(IPL),
        pooled or paths.warehouse_path(POOLED),
        _parse_serving(copy or []),
    )
    with _serving_models(IPL):
        _score_serving(serving, sources)
    others = _parse_serving(serving_db) if serving_db is not None else _exported_servings()
    for competition, path in others.items():
        with _serving_models(competition, path):
            if registry.current_version(registry.NAME, competition) is None:
                typer.echo(f"> no {model_format()} models yet: {competition} is not scored")
                continue
            _score_serving(path, sources, competition)
    target = players or paths.players_path()
    if current(target).exists():
        _score_players(target, sources)


@contextlib.contextmanager
def _serving_models(competition: str, serving: Path | None = None) -> Iterator[None]:
    """Score ``competition`` with its group's models (or, in no group, its format's)."""
    owner = group_of(competition)
    if owner is not None:
        with formats.use_group(owner, serving=True):
            yield
        return
    with use_format(_format_of(serving) if serving is not None else MODEL_FORMAT):
        yield


def _fallback_notice(name: str, competition: str) -> None:
    """Say so when a competition is scored with a pooled T20 model (its group has none yet)."""
    version = registry.fallback_version(name, competition)
    owner = formats.current_group()
    if version is not None and owner is not None:
        typer.echo(
            f"  [fallback] {competition} {name}: the pooled T20 model {version} until the "
            f"{owner.id} group has its own (just train-group {owner.id})"
        )


def _format_of(serving: Path) -> str:
    """The format of a serving database's competition (its models' format)."""
    con = duckdb.connect(str(current(serving)), read_only=True)
    try:
        row = con.execute("SELECT format FROM competitions LIMIT 1").fetchone()
    finally:
        con.close()
    return str(row[0]) if row else MODEL_FORMAT


def _parse_serving(values: list[str]) -> dict[str, Path]:
    found = {}
    for value in values:
        competition, sep, path = value.partition("=")
        if not sep or not competition or not path:
            raise typer.BadParameter(f"expected COMPETITION=PATH, got {value!r}")
        found[competition.upper()] = Path(path)
    return found


def _exported_servings() -> dict[str, Path]:
    """Every other competition's serving database in the exports folder, by competition."""
    found = {}
    for path in sorted(paths.exports_dir().glob("serving-*.duckdb*")):
        name = path.name.split(".duckdb")[0]
        competition = name.removeprefix("serving-").upper()
        if competition != IPL:
            found[competition] = paths.serving_path(competition)
    return found


def _serves_simulator(settings: simulator.SimulatorSettings, competition: str) -> bool:
    """Whether a simulator version was backtested on (and so serves) ``competition``."""
    covered = settings.manifest.get("competitions")
    return competition == IPL if covered is None else competition in covered


def _score_serving(serving: Path | None, sources: _Sources, competition: str = IPL) -> None:
    final = serving or paths.serving_path(competition)
    # Score one working copy and put it in place at the end, so a failure leaves
    # nothing half-scored and the running API can keep its database open.
    target = final.with_name(final.name + ".scoring")
    shutil.copyfile(current(final), target)
    typer.echo(f"> scoring {competition}")
    ipl = {competition}
    try:
        for name in (registry.NAME, registry.PROJECTION, registry.BALL_OUTCOME, registry.RATINGS):
            _fallback_notice(name, competition)
        wp_model = registry.load_current(registry.NAME, competition)
        wp_source = sources.warehouse(wp_model.manifest)
        states = _of(sources.states(wp_source, wp_model.feature_config), ipl)
        inputs = sources.inputs(wp_source)
        predictions = _timed("win probability", lambda: scoring.score_states(wp_model, states))
        predictions, scale = _timed(
            "pressure and momentum",
            lambda: scoring.add_pressure(wp_model, states, predictions, inputs),
        )
        count = _timed("publishing", lambda: scoring.publish(target, predictions, wp_model, scale))
        typer.echo(f"  {count:,} win probabilities from model {wp_model.version}")

        projection_model = registry.load_current_projection(competition)
        projection_states = _of(
            sources.states(
                sources.warehouse(projection_model.manifest), projection_model.feature_config
            ),
            ipl,
        )
        projections = _timed(
            "score projection",
            lambda: scoring.score_projections(projection_model, projection_states),
        )
        count = _timed(
            "publishing",
            lambda: scoring.publish_projections(target, projections, projection_model),
        )
        typer.echo(f"  {count:,} score projections from model {projection_model.version}")

        ball_model = registry.load_current_ball_outcome(competition)
        balls = _of(sources.balls(sources.warehouse(ball_model.manifest)), ipl)
        served = ball_model.for_competition(competition)
        cells = _timed("ball outcomes", lambda: scoring.score_matchups(served, balls))
        count = _timed(
            "publishing",
            lambda: scoring.publish_ball_model(target, cells, served, scoring.current_env(balls)),
        )
        typer.echo(f"  {count:,} head-to-head cells from model {ball_model.version} -> {target}")

        if registry.current_version(registry.RATINGS) is None:
            # A new format's ratings are fitted on its scored players (win probability
            # added); the next scoring publishes them.
            typer.echo(f"  no ratings for {competition} yet")
        else:
            rating_constants = registry.load_current_ratings()
            _timed(
                "publishing ratings",
                lambda: scoring.publish_ratings(target, rating_constants, competition),
            )
            typer.echo(f"  rating constants {rating_constants.version} -> {target}")

        simulator_version = registry.current_version(registry.SIMULATOR, competition)
        simulator_model = (
            None if simulator_version is None else registry.load_current_simulator(competition)
        )
        if simulator_model is not None and _serves_simulator(simulator_model, competition):
            _fallback_notice(registry.SIMULATOR, competition)
            settings = simulator_model.for_competition(competition)
            _timed(
                "publishing simulator settings",
                lambda: scoring.publish_simulator(target, settings),
            )
            typer.echo(f"  simulator settings {settings.version} -> {target}")
            if settings.manifest.get("level_window"):
                window = int(settings.manifest["level_window"])
                shifts, now = simulator.level_shifts(served, balls, window)
                _timed(
                    "publishing the recent scoring level",
                    lambda: scoring.publish_level_shifts(target, shifts, now),
                )
                typer.echo(f"  scoring level after the last match: era shift {now:+.2f}")
            else:
                scoring.drop_level_shifts(target)
        else:
            scoring.drop_level_shifts(target)
            typer.echo(f"  no simulator serves {competition} (none passed its gate there)")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    placed = publish(target, final)
    typer.echo(f"  scored database -> {placed}")


def _score_players(players: Path, sources: _Sources) -> None:
    """Win probability added and rating constants for every competition's scope, each
    with its model group's models. A scope of several competitions (all T20) keeps the
    pooled T20 ratings that were fitted on it."""
    by_group: dict[str, list[str]] = {}
    for s in players_scoring.scopes(current(players)):
        owner = group_of(str(s["scope_id"])) if len(s["competition_ids"]) == 1 else None
        if owner is not None:
            by_group.setdefault(owner.id, []).append(str(s["scope_id"]))
    frames = []
    ratings_models = []
    for group_id, competitions in by_group.items():
        with formats.use_group(group_id, serving=True):
            frames += _players_wpa(competitions, sources)
            try:
                ratings_models.append(registry.load_current_ratings())
            except FileNotFoundError:
                typer.echo(f"  no {group_id} ratings yet")
    with contextlib.suppress(FileNotFoundError):
        ratings_models.append(registry.load_current_ratings())  # the pooled T20 ratings
    placed = _timed(
        "publishing to the players database",
        lambda: players_scoring.publish(
            current(players), pd.concat(frames) if frames else None, ratings_models
        ),
    )
    typer.echo(f"  win probability added and rating constants -> {placed}")


def _players_wpa(competitions: list[str], sources: _Sources) -> list[pd.DataFrame]:
    """Win probability added in some competitions of the current format."""
    by_version: dict[str, list[str]] = {}
    for competition in competitions:
        version = registry.current_version(registry.NAME, competition)
        if version is None:
            typer.echo(f"  no win probability model for {competition} yet")
            continue
        by_version.setdefault(version, []).append(competition)
    frames = []
    for version, members in by_version.items():
        model = registry.load_current(registry.NAME, members[0])
        source = sources.warehouse(model.manifest)
        states = _of(sources.states(source, model.feature_config), set(members))
        if states.empty:
            typer.echo(f"  model {version} cannot score {', '.join(members)}: not in its data")
            continue
        predictions = _timed(
            f"win probability for {', '.join(members)}",
            functools.partial(scoring.score_states, model, states),
        )
        wpa = players_scoring.player_wpa(predictions, sources.inputs(source).deliveries)
        competition_of = states.drop_duplicates("match_id").set_index("match_id")["competition_id"]
        frames.append(wpa.assign(competition_id=wpa["match_id"].map(competition_of)))
    return frames


@app.command("report")
def report_cmd(match_format: FormatOption = MODEL_FORMAT, group_id: GroupOption = None) -> None:
    """Write the model cards and the Model Insights data for the web app."""
    if group_id is not None:
        owner = _group(group_id)
        servings = {
            c: current(p)
            for c, p in _exported_servings().items()
            if c in owner.competitions and current(p).exists()
        }
        with formats.use_group(owner):
            written = (
                report.write_all(_serving_path(), {})
                if owner.models == ""
                else report.write_format(servings)
            )
        for path in written:
            typer.echo(f"wrote {path}")
        return
    match_format = _format(match_format)
    others = {
        c: current(p)
        for c, p in _exported_servings().items()
        if current(p).exists() and _format_of(p) == match_format
    }
    with use_format(match_format):
        written = (
            report.write_all(_serving_path(), others)
            if match_format == MODEL_FORMAT
            else report.write_format(others)
        )
    for path in written:
        typer.echo(f"wrote {path}")


@app.callback()
def main() -> None:
    """CricIQ models."""


if __name__ == "__main__":
    app()
