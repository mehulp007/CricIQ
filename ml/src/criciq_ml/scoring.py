"""Score every historical ball and publish the results into the serving database.

The API never runs a model: it reads these precomputed probabilities, so the
deployed service stays small and every replay is consistent with the model
card.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from criciq_ml.features import GROUP_KEYS, LABEL
from criciq_ml.model import WinProbabilityModel, round_points, terminal_probability


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


def publish(serving: Path, predictions: pd.DataFrame, model: WinProbabilityModel) -> int:
    """Add the predictions and model metadata to the serving database, atomically."""
    staging = serving.with_name(serving.name + ".scoring")
    shutil.copyfile(serving, staging)
    con = duckdb.connect(str(staging))
    try:
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
        con.execute("DROP TABLE IF EXISTS models")
        con.execute(
            """
            CREATE TABLE models (
                name VARCHAR PRIMARY KEY, version VARCHAR NOT NULL,
                trained_from INTEGER NOT NULL, trained_through INTEGER NOT NULL,
                factor_keys VARCHAR[] NOT NULL, base_innings1 DOUBLE NOT NULL,
                base_innings2 DOUBLE NOT NULL
            )
            """
        )
        manifest = model.manifest
        con.execute(
            "INSERT INTO models VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                manifest["name"],
                model.version,
                manifest["trained_on"]["seasons"][0],
                manifest["trained_on"]["seasons"][1],
                GROUP_KEYS,
                manifest["base_probability"]["1"],
                manifest["base_probability"]["2"],
            ],
        )
        count = int(con.execute("SELECT count(*) FROM wp_predictions").fetchone()[0])  # type: ignore[index]
        con.execute("CHECKPOINT")
    finally:
        con.close()
    os.replace(staging, serving)
    return count
