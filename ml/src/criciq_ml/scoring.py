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

from criciq_ml.features import GROUP_KEYS, LABEL
from criciq_ml.model import WinProbabilityModel, round_points, terminal_probability
from criciq_ml.projection import LEVELS, ScoreProjectionModel, projection_frame


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


def publish(serving: Path, predictions: pd.DataFrame, model: WinProbabilityModel) -> int:
    """Add win probabilities, player WPA and model metadata to the serving database."""

    def write(con: duckdb.DuckDBPyConnection) -> int:
        con.register("predictions", predictions)
        con.execute("DROP TABLE IF EXISTS wp_predictions")
        con.execute(
            """
            CREATE TABLE wp_predictions AS
            SELECT match_id::BIGINT AS match_id, innings_no::INTEGER AS innings_no,
                   seq_no::INTEGER AS seq_no, wp_team_a::DOUBLE AS wp_team_a,
                   factors::FLOAT[] AS factors
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
