"""Model outputs for the players database (``criciq_pipelines.player_db``).

The players database holds the Player Lab tables of every T20 competition, one
schema of views per scope. Two things there come from the models:

- ``player_wpa``: win probability added, from every ball's win probability
  scored by the model serving that competition, credited as in the serving
  database (``scoring.PLAYER_WPA_SQL``). It goes in ``main`` with a
  ``competition_id``, and each scope gets a view.
- a ``models`` table in each scope's schema with that scope's rating constants,
  which the API's ratings read through the scope's ``search_path``.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from criciq_core.publish import publish as place
from criciq_ml.ratings import RatingsModel
from criciq_ml.scoring import PLAYER_WPA_QUERY


def player_wpa(predictions: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """Win probability added per player, innings and role, from scored states."""
    con = duckdb.connect()
    try:
        states = predictions[["match_id", "innings_no", "seq_no", "wp_team_a"]]
        con.register("wp_predictions", states)
        con.register(
            "deliveries", deliveries[["match_id", "innings_no", "seq_no", "batter_id", "bowler_id"]]
        )
        frame: pd.DataFrame = con.execute(PLAYER_WPA_QUERY).df()
    finally:
        con.close()
    return frame


def scopes(players: Path) -> list[dict[str, Any]]:
    con = duckdb.connect(str(players), read_only=True)
    try:
        cursor = con.execute("SELECT * FROM main.scopes ORDER BY display_order")
        columns = [d[0] for d in cursor.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()


def publish(
    players: Path,
    wpa: pd.DataFrame | None,
    ratings: RatingsModel | Sequence[RatingsModel] | None,
) -> Path:
    """Write ``wpa`` (with ``competition_id``) and each scope's rating constants (from
    whichever ratings fitted it: each format has its own) into a copy of the players
    database, then put it in place (beside it while the API has it open); returns where
    it went."""
    models = [] if ratings is None else [ratings] if isinstance(ratings, RatingsModel) else ratings
    staging = players.with_name(players.name + ".scoring")
    shutil.copyfile(players, staging)
    con = duckdb.connect(str(staging))
    try:
        rows = con.execute(
            "SELECT scope_id, schema_name, competition_ids FROM main.scopes"
        ).fetchall()
        if wpa is not None:
            con.register("wpa", wpa)
            con.execute("DROP TABLE IF EXISTS main.player_wpa CASCADE")
            con.execute(
                """
                CREATE TABLE main.player_wpa AS
                SELECT competition_id, player_id, match_id::BIGINT AS match_id,
                       innings_no::INTEGER AS innings_no, role, wpa::DOUBLE AS wpa
                FROM wpa ORDER BY competition_id, player_id, match_id, innings_no, role
                """
            )
            for _, schema, members in rows:
                within = ", ".join(f"'{m}'" for m in members)
                con.execute(
                    f"""
                    CREATE OR REPLACE VIEW {schema}.player_wpa AS
                    SELECT * EXCLUDE (competition_id) FROM main.player_wpa
                    WHERE competition_id IN ({within})
                    """
                )
        for scope_id, schema, _ in rows:
            fitted_by = [(m, f) for m in models if (f := m.for_scope(scope_id)) is not None]
            if not fitted_by:
                continue
            model, fitted = fitted_by[0]
            con.execute(f"DROP TABLE IF EXISTS {schema}.models")
            con.execute(
                f"""
                CREATE TABLE {schema}.models (
                    name VARCHAR PRIMARY KEY, version VARCHAR NOT NULL,
                    trained_from INTEGER NOT NULL, trained_through INTEGER NOT NULL,
                    info JSON NOT NULL
                )
                """
            )
            first, last = fitted["trained_on"]["seasons"]
            con.execute(
                f"INSERT INTO {schema}.models VALUES (?, ?, ?, ?, ?)",
                [
                    model.manifest["name"],
                    model.version,
                    int(first),
                    int(last),
                    json.dumps({"components": fitted["components"]}),
                ],
            )
        con.execute("CHECKPOINT")
    except BaseException:
        con.close()
        staging.unlink(missing_ok=True)
        raise
    con.close()
    return place(staging, players)
