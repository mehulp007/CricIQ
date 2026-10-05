"""Score every historical ball and publish the results into the serving database.

The API never runs a model: it reads these precomputed probabilities, so the
deployed service stays small and every replay is consistent with the model
card.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from criciq_ml import leverage
from criciq_ml.ball_outcome import CLASSES, ENV_WINDOW, GROUPS, RUNS, BallOutcomeModel
from criciq_ml.data import Inputs
from criciq_ml.features import GROUP_KEYS, LABEL
from criciq_ml.model import WinProbabilityModel, round_points, terminal_probability
from criciq_ml.projection import LEVELS, ScoreProjectionModel, projection_frame
from criciq_ml.ratings import RatingsModel
from criciq_ml.simulator import SimulatorSettings


def score_states(model: WinProbabilityModel, states: pd.DataFrame) -> pd.DataFrame:
    """Side-batting-first win probability (and explanation) for every state.

    Once a chase is over the rule layer takes over: the result is known, so
    the probability is exactly 1, 0 or 0.5 and there is nothing to explain.
    """
    scored = model.score(states)
    wp = scored["wp_batting"].to_numpy(dtype=float).copy()
    points = scored[[f"pts_{k}" for k in GROUP_KEYS]].to_numpy(dtype=float)
    explained = np.ones(len(states), dtype=bool)

    last = states.groupby(["match_id", "innings_no"])["seq_no"].transform("max").to_numpy()
    for i, row in enumerate(states.itertuples(index=False)):
        if row.innings_no != 2:
            continue
        fixed = terminal_probability(
            innings_no=2,
            runs=int(row.runs),
            wickets=int(row.wickets),
            legal_balls=int(row.legal_balls),
            max_balls=int(row.max_balls),
            target=int(row.target),
        )
        label = getattr(row, LABEL)
        if fixed is None and row.seq_no == last[i] and not np.isnan(label):
            fixed = float(label)  # the match ended here (e.g. a rain-shortened chase)
        if fixed is not None:
            wp[i] = fixed
            explained[i] = False

    batting_first = (states["innings_no"] == 1).to_numpy()
    out = pd.DataFrame(
        {
            "match_id": states["match_id"].to_numpy(),
            "innings_no": states["innings_no"].to_numpy(),
            "seq_no": states["seq_no"].to_numpy(),
            "wp_team_a": np.round(np.where(batting_first, wp, 1 - wp), 4),
        }
    )
    out["factors"] = [round_points(points[i]) if explained[i] else None for i in range(len(states))]
    return out


def add_pressure(
    model: WinProbabilityModel, states: pd.DataFrame, predictions: pd.DataFrame, inputs: Inputs
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Leverage, pressure (0-100) and momentum for every state (see ``criciq_ml.leverage``).

    Returns the predictions with the new columns and the pressure scale: the
    mean swing and the percentiles of swings among these states.
    """
    states = states.reset_index(drop=True)
    first = (states["innings_no"] == 1).to_numpy()
    wp_a = predictions["wp_team_a"].to_numpy(dtype=float)
    wp_batting = np.where(first, wp_a, 1 - wp_a)
    swing = leverage.expected_swing(model, states, inputs)
    scale = leverage.pressure_scale(swing)
    out = predictions.reset_index(drop=True).copy()
    out["leverage"] = np.round(swing / scale["mean_swing"], 3)
    out["pressure"] = leverage.pressure(swing, scale["quantiles"])
    out["momentum"] = np.round(leverage.momentum(states, wp_batting), 2)
    return out, scale


def score_projections(model: ScoreProjectionModel, states: pd.DataFrame) -> pd.DataFrame:
    """Quantiles of the final first-innings total after every ball still in play.

    Innings cut short by rain are not projected: the model assumes the full
    allocation of overs, which such an innings never had.
    """
    frame = projection_frame(states)
    frame = frame[frame["projectable"] & frame["complete"]]
    quantiles = np.rint(model.predict(frame)).astype(int)
    return pd.DataFrame(
        {
            "match_id": frame["match_id"].to_numpy(),
            "seq_no": frame["seq_no"].to_numpy(),
            "quantiles": [list(map(int, q)) for q in quantiles],
        }
    )


def _publish(serving: Path, write: Callable[[duckdb.DuckDBPyConnection], int]) -> int:
    """Apply ``write`` to a copy of the serving database, then swap it in atomically."""
    staging = serving.with_name(serving.name + ".scoring")
    shutil.copyfile(serving, staging)
    con = duckdb.connect(str(staging))
    try:
        count = write(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    os.replace(staging, serving)
    return count


def _register_model(
    con: duckdb.DuckDBPyConnection,
    name: str,
    version: str,
    seasons: list[int],
    info: dict[str, Any],
) -> None:
    columns = {
        name
        for (name,) in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'models'"
        ).fetchall()
    }
    if columns and "info" not in columns:
        con.execute("DROP TABLE models")  # pre-M4 layout with one model's columns
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS models (
            name VARCHAR PRIMARY KEY, version VARCHAR NOT NULL,
            trained_from INTEGER NOT NULL, trained_through INTEGER NOT NULL, info JSON NOT NULL
        )
        """
    )
    con.execute("DELETE FROM models WHERE name = ?", [name])
    con.execute(
        "INSERT INTO models VALUES (?, ?, ?, ?, ?)",
        [name, version, seasons[0], seasons[1], json.dumps(info)],
    )


# Win probability added: every ball's change in the batting side's win
# probability is credited to the batter on strike and, with the opposite sign,
# to the bowler. Changes between innings belong to nobody.
PLAYER_WPA_SQL = """
CREATE TABLE player_wpa AS
WITH batting_side AS (
    SELECT match_id, innings_no, seq_no,
           CASE WHEN innings_no = 1 THEN wp_team_a ELSE 1 - wp_team_a END AS wp
    FROM wp_predictions
),
deltas AS (
    SELECT match_id, innings_no, seq_no,
           wp - lag(wp) OVER (PARTITION BY match_id, innings_no ORDER BY seq_no) AS delta
    FROM batting_side
),
credited AS (
    SELECT d.match_id, d.innings_no, x.batter_id, x.bowler_id, d.delta
    FROM deltas d JOIN deliveries x USING (match_id, innings_no, seq_no)
    WHERE d.delta IS NOT NULL
)
SELECT batter_id AS player_id, match_id, innings_no, 'batting' AS role, sum(delta) AS wpa
FROM credited GROUP BY ALL
UNION ALL
SELECT bowler_id, match_id, innings_no, 'bowling', -sum(delta)
FROM credited GROUP BY ALL
ORDER BY player_id, match_id, innings_no, role
"""


def publish(
    serving: Path,
    predictions: pd.DataFrame,
    model: WinProbabilityModel,
    pressure_scale: dict[str, Any] | None = None,
) -> int:
    """Add win probabilities, player WPA and model metadata to the serving database.

    With ``add_pressure`` columns present, every state also carries its
    leverage, pressure index and momentum.
    """

    def write(con: duckdb.DuckDBPyConnection) -> int:
        con.register("predictions", predictions)
        con.execute("DROP TABLE IF EXISTS wp_predictions")
        extra = (
            ", leverage::FLOAT AS leverage, pressure::UTINYINT AS pressure, "
            "momentum::FLOAT AS momentum"
            if "leverage" in predictions
            else ""
        )
        con.execute(
            f"""
            CREATE TABLE wp_predictions AS
            SELECT match_id::BIGINT AS match_id, innings_no::INTEGER AS innings_no,
                   seq_no::INTEGER AS seq_no, wp_team_a::DOUBLE AS wp_team_a,
                   factors::FLOAT[] AS factors{extra}
            FROM predictions ORDER BY match_id, innings_no, seq_no
            """
        )
        con.execute("DROP TABLE IF EXISTS player_wpa")
        con.execute(PLAYER_WPA_SQL)
        manifest = model.manifest
        _register_model(
            con,
            manifest["name"],
            model.version,
            manifest["trained_on"]["seasons"],
            {
                "factor_keys": GROUP_KEYS,
                "base_innings1": manifest["base_probability"]["1"],
                "base_innings2": manifest["base_probability"]["2"],
                **({"pressure": pressure_scale} if pressure_scale else {}),
            },
        )
        return int(con.execute("SELECT count(*) FROM wp_predictions").fetchone()[0])  # type: ignore[index]

    return _publish(serving, write)


def publish_projections(
    serving: Path, projections: pd.DataFrame, model: ScoreProjectionModel
) -> int:
    """Add first-innings score projections and model metadata to the serving database."""

    def write(con: duckdb.DuckDBPyConnection) -> int:
        con.register("projections", projections)
        con.execute("DROP TABLE IF EXISTS score_projections")
        con.execute(
            """
            CREATE TABLE score_projections AS
            SELECT match_id::BIGINT AS match_id, seq_no::INTEGER AS seq_no,
                   quantiles::SMALLINT[] AS quantiles
            FROM projections ORDER BY match_id, seq_no
            """
        )
        _register_model(
            con,
            model.manifest["name"],
            model.version,
            model.manifest["trained_on"]["seasons"],
            {"levels": list(LEVELS)},
        )
        return int(con.execute("SELECT count(*) FROM score_projections").fetchone()[0])  # type: ignore[index]

    return _publish(serving, write)


def score_matchups(model: BallOutcomeModel, balls: pd.DataFrame) -> pd.DataFrame:
    """Observed and model-expected outcome counts per batter, bowler, season and phase.

    The expected counts are what the ball-outcome model predicts for those
    exact balls from the two players' overall records and the situations they
    met in, without any knowledge of their head-to-head history beyond its
    share of each player's record.
    """
    probs = model.predict(balls)
    frame = pd.DataFrame(probs, columns=[f"e_{c}" for c in CLASSES])
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(balls)), balls["outcome"].to_numpy()] = 1.0
    for k, name in enumerate(CLASSES):
        frame[f"n_{name}"] = onehot[:, k]
    for column in ("batter_id", "bowler_id", "season", "phase"):
        frame[column] = balls[column].to_numpy()
    frame["runs"] = balls["runs_batter"].to_numpy()
    frame["balls"] = 1
    cells = frame.groupby(["batter_id", "bowler_id", "season", "phase"], as_index=False).sum()
    for name in CLASSES:
        cells[f"n_{name}"] = cells[f"n_{name}"].round().astype(int)
    return cells


def current_env(balls: pd.DataFrame) -> float:
    """League runs per ball faced over the most recent matches: the era a next ball is in."""
    per_match = balls.groupby("match_order")["runs_batter"].agg(["sum", "size"]).sort_index()
    recent = per_match.tail(ENV_WINDOW)
    return float(recent["sum"].sum() / recent["size"].sum())


def publish_ball_model(
    serving: Path, cells: pd.DataFrame, model: BallOutcomeModel, env_now: float
) -> int:
    """Add head-to-head cells and the ball-outcome model's terms to the serving database."""

    def write(con: duckdb.DuckDBPyConnection) -> int:
        con.register("cells", cells)
        con.execute("DROP TABLE IF EXISTS matchup_cells")
        counts = ", ".join(f"n_{c}::INTEGER AS n_{c}" for c in CLASSES)
        expected = ", ".join(f"e_{c}::DOUBLE AS e_{c}" for c in CLASSES)
        con.execute(
            f"""
            CREATE TABLE matchup_cells AS
            SELECT batter_id, bowler_id, season::INTEGER AS season, phase,
                   balls::INTEGER AS balls, runs::INTEGER AS runs, {counts}, {expected}
            FROM cells ORDER BY batter_id, bowler_id, season, phase
            """
        )
        terms = pd.DataFrame(
            {
                "term": list(model.terms),
                "coefs": [list(map(float, v)) for v in model.terms.values()],
            }
        )
        con.register("terms", terms)
        con.execute("DROP TABLE IF EXISTS ball_model_terms")
        con.execute(
            "CREATE TABLE ball_model_terms AS "
            "SELECT term, coefs::DOUBLE[] AS coefs FROM terms ORDER BY term"
        )
        manifest = model.manifest
        _register_model(
            con,
            manifest["name"],
            model.version,
            manifest["trained_on"]["seasons"],
            {
                "classes": list(CLASSES),
                "runs": [float(r) for r in RUNS],
                "kappa": manifest["kappa"],
                "env_mean": manifest["env_mean"],
                "env_std": manifest["env_std"],
                "env_now": env_now,
                "groups": {k: list(v) for k, v in GROUPS.items()},
            },
        )
        return int(con.execute("SELECT count(*) FROM matchup_cells").fetchone()[0])  # type: ignore[index]

    return _publish(serving, write)


def publish_simulator(serving: Path, settings: SimulatorSettings) -> None:
    """Register the simulator's settings (the tuned conditions spread) for the API."""

    def write(con: duckdb.DuckDBPyConnection) -> int:
        manifest = settings.manifest
        seasons = con.execute("SELECT min(year), max(year) FROM seasons").fetchone()
        assert seasons is not None
        _register_model(con, manifest["name"], settings.version, list(seasons), manifest)
        return 1

    _publish(serving, write)


def publish_ratings(serving: Path, model: RatingsModel) -> int:
    """Register the rating constants (shrinkage per component) in the serving database."""

    def write(con: duckdb.DuckDBPyConnection) -> int:
        manifest = model.manifest
        _register_model(
            con,
            manifest["name"],
            model.version,
            manifest["trained_on"]["seasons"],
            {"components": manifest["components"]},
        )
        return sum(len(v) for v in manifest["components"].values())

    return _publish(serving, write)
