"""Score every Test ball and publish the results into the Test serving database.

* ``wp_predictions``: after every ball (and before every innings, ``seq_no = 0``),
  the chance that the side batting first wins (``wp_team_a``) and that the match
  is drawn (``wp_draw``). A match's last ball carries its result exactly.
* ``player_wpa``: the change in the batting side's expected result over each
  ball (a win counts 1, a draw a half), credited to the batter and, with the
  opposite sign, to the bowler.
* ``innings_projections``: quantiles of every innings' final total.
* ``chase_states``: the fourth-innings states the chase what-if starts from.
* ``models``: each model's version and the facts the API needs (the win probability
  model's terms, the sides' ratings and the scoring era now).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from criciq_core.test_win_probability import columns
from criciq_ml.scoring import _publish, _register_model
from criciq_ml.test_match.projection import LEVELS, TestProjectionModel, projection_frame
from criciq_ml.test_match.states import DRAWN, LABEL, LOST, WON, final_rows
from criciq_ml.test_match.win_probability import TestWinProbabilityModel


def score_wp(model: TestWinProbabilityModel, states: pd.DataFrame) -> pd.DataFrame:
    """The side batting first's chance of winning and the chance of a draw, per state."""
    states = states.reset_index(drop=True)
    p = model.predict(states)
    # A match's last state is its result (where it has one).
    final = final_rows(states)
    label = states[LABEL].to_numpy()
    settled = final & ~np.isnan(label)
    known = np.zeros_like(p)
    known[settled, label[settled].astype(int)] = 1.0
    p = np.where(settled[:, None], known, p)
    first = states["batted_first"].to_numpy() == 1.0
    return pd.DataFrame(
        {
            "match_id": states["match_id"].to_numpy(),
            "innings_no": states["innings_no"].to_numpy(),
            "seq_no": states["seq_no"].to_numpy(),
            "wp_team_a": np.round(np.where(first, p[:, WON], p[:, LOST]), 4),
            "wp_draw": np.round(p[:, DRAWN], 4),
        }
    )


# The batting side's expected result: team A's is P(A wins) + P(draw) / 2, and the
# other side's is one minus that.
PLAYER_WPA_SQL = """
CREATE TABLE player_wpa AS
WITH batting_side AS (
    SELECT p.match_id, p.innings_no, p.seq_no,
           CASE WHEN i.batting_team_id = s.team_a_id THEN p.wp_team_a + p.wp_draw / 2
                ELSE 1 - p.wp_team_a - p.wp_draw / 2 END AS wp
    FROM wp_predictions p
    JOIN innings i USING (match_id, innings_no)
    JOIN match_summaries s USING (match_id)
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


def publish_wp(
    serving: Path,
    predictions: pd.DataFrame,
    model: TestWinProbabilityModel,
    chase: pd.DataFrame | None = None,
    now: dict[str, Any] | None = None,
) -> int:
    """Win and draw probabilities, player WPA, the chase states and the model's facts
    (``now``: the sides' ratings and the scoring era after the last Test, for the chase
    calculator)."""

    def write(con: duckdb.DuckDBPyConnection) -> int:
        con.register("predictions", predictions)
        con.execute("DROP TABLE IF EXISTS wp_predictions")
        con.execute(
            """
            CREATE TABLE wp_predictions AS
            SELECT match_id::BIGINT AS match_id, innings_no::INTEGER AS innings_no,
                   seq_no::INTEGER AS seq_no, wp_team_a::DOUBLE AS wp_team_a,
                   wp_draw::DOUBLE AS wp_draw, NULL::FLOAT[] AS factors
            FROM predictions ORDER BY match_id, innings_no, seq_no
            """
        )
        con.unregister("predictions")
        con.execute("DROP TABLE IF EXISTS player_wpa")
        con.execute(PLAYER_WPA_SQL)
        con.execute("DROP TABLE IF EXISTS chase_states")
        if chase is not None:
            con.register("chase", chase)
            con.execute("CREATE TABLE chase_states AS SELECT * FROM chase ORDER BY ALL")
            con.unregister("chase")
        manifest = model.manifest
        _register_model(
            con,
            manifest["name"],
            model.version,
            manifest["trained_on"]["seasons"],
            {"outcomes": 3, **model.serving_info(), **({"now": now} if now else {})},
        )
        return int(con.execute("SELECT count(*) FROM wp_predictions").fetchone()[0])  # type: ignore[index]

    return _publish(serving, write)


def player_wpa(
    predictions: pd.DataFrame, states: pd.DataFrame, deliveries: pd.DataFrame
) -> pd.DataFrame:
    """Expected result added per player, innings and role (for the players database),
    credited as ``PLAYER_WPA_SQL`` does in the serving database."""
    keys = ["match_id", "innings_no", "seq_no"]
    frame = predictions.merge(states[[*keys, "batted_first"]], on=keys).sort_values(keys)
    team_a = frame["wp_team_a"] + frame["wp_draw"] / 2
    frame["value"] = np.where(frame["batted_first"] == 1.0, team_a, 1 - team_a)
    frame["delta"] = frame.groupby(["match_id", "innings_no"])["value"].diff()
    balls = frame.dropna(subset=["delta"]).merge(
        deliveries[[*keys, "batter_id", "bowler_id"]], on=keys
    )
    batting = (
        balls.groupby(["batter_id", "match_id", "innings_no"], as_index=False)["delta"]
        .sum()
        .rename(columns={"batter_id": "player_id", "delta": "wpa"})
        .assign(role="batting")
    )
    bowling = (
        balls.groupby(["bowler_id", "match_id", "innings_no"], as_index=False)["delta"]
        .sum()
        .rename(columns={"bowler_id": "player_id", "delta": "wpa"})
        .assign(role="bowling", wpa=lambda f: -f["wpa"])
    )
    columns = ["player_id", "match_id", "innings_no", "role", "wpa"]
    return pd.concat([batting[columns], bowling[columns]], ignore_index=True)


def chase_states(states: pd.DataFrame, model: TestWinProbabilityModel) -> pd.DataFrame:
    """The fourth-innings states, with every column the model reads (the what-if's start)."""
    fourth = states[states["innings_no"] == 4]
    needed = columns(4, model.terms[4].groups)
    keep = ["match_id", "innings_no", "seq_no", "runs", "wickets", "legal_balls", *needed]
    return fourth[list(dict.fromkeys(keep))].reset_index(drop=True)


def score_projections(model: TestProjectionModel, states: pd.DataFrame) -> pd.DataFrame:
    """Quantiles of every innings' final total after each ball still in play."""
    frame = projection_frame(states)
    frame = frame[frame["projectable"]]
    quantiles = np.rint(model.predict(frame)).astype(int)
    return pd.DataFrame(
        {
            "match_id": frame["match_id"].to_numpy(),
            "innings_no": frame["innings_no"].to_numpy(),
            "seq_no": frame["seq_no"].to_numpy(),
            "quantiles": [list(map(int, q)) for q in quantiles],
        }
    )


def publish_projections(
    serving: Path, projections: pd.DataFrame, model: TestProjectionModel
) -> int:
    def write(con: duckdb.DuckDBPyConnection) -> int:
        con.register("projections", projections)
        con.execute("DROP TABLE IF EXISTS innings_projections")
        con.execute(
            """
            CREATE TABLE innings_projections AS
            SELECT match_id::BIGINT AS match_id, innings_no::INTEGER AS innings_no,
                   seq_no::INTEGER AS seq_no, quantiles::SMALLINT[] AS quantiles
            FROM projections ORDER BY match_id, innings_no, seq_no
            """
        )
        con.unregister("projections")
        info: dict[str, Any] = {"levels": list(LEVELS)}
        seasons = model.manifest["trained_on"]["seasons"]
        _register_model(con, model.manifest["name"], model.version, seasons, info)
        return int(con.execute("SELECT count(*) FROM innings_projections").fetchone()[0])  # type: ignore[index]

    return _publish(serving, write)
