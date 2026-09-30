"""Scoring into the serving database, and the generated model card and insights."""

import json
from pathlib import Path

import duckdb
import pandas as pd

from criciq_ml import registry, report


def test_every_state_is_scored_and_published(
    fixture_scored_serving_db: Path, fixture_states: pd.DataFrame
) -> None:
    con = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    try:
        count = con.execute("SELECT count(*) FROM wp_predictions").fetchone()
        starts = con.execute("SELECT count(*) FROM wp_predictions WHERE seq_no = 0").fetchone()
        model = con.execute("SELECT version, factor_keys FROM models").fetchone()
        ends = con.execute(
            """
            SELECT m.outcome_type, m.winner_id = i.batting_team_id AS chaser_won, p.wp_team_a
            FROM wp_predictions p
            JOIN innings i USING (match_id, innings_no)
            JOIN matches m USING (match_id)
            WHERE p.innings_no = 2 AND p.seq_no = (
                SELECT max(seq_no) FROM wp_predictions q
                WHERE q.match_id = p.match_id AND q.innings_no = 2)
            """
        ).fetchall()
    finally:
        con.close()
    assert count == (len(fixture_states),)
    assert starts == (fixture_states.groupby(["match_id", "innings_no"]).ngroups,)
    assert model == (registry.current_version(), ["situation", "wickets", "recent"])
    for outcome, chaser_won, wp_team_a in ends:
        if outcome == "tie":
            assert wp_team_a == 0.5
        elif outcome == "win":
            assert wp_team_a == (0.0 if chaser_won else 1.0)
    assert not list(fixture_scored_serving_db.parent.glob("*.scoring"))


def test_model_card_renders_from_the_registry(fixture_scored_serving_db: Path) -> None:
    version = registry.current_version()
    assert version is not None
    data = report.insights(version, fixture_scored_serving_db)
    card = report.model_card(data)
    evaluation = registry.load_evaluation(version)
    assert f"{evaluation['test']['model']['log_loss']:.4f}" in card
    assert "## Rolling-origin backtest" in card
    assert all(s["swing"] > 0 for s in data["swings"])


def test_bundled_insights_match_the_current_model() -> None:
    """The web app's Model Insights page ships this file; it must describe the served model."""
    bundled = json.loads(report.INSIGHTS_PATH.read_text(encoding="utf-8"))
    version = registry.current_version()
    assert version is not None
    evaluation = registry.load_evaluation(version)
    assert bundled["version"] == version
    assert bundled["test"]["model"] == evaluation["test"]["model"]
    assert bundled["backtest"] == evaluation["backtest"]
    assert len(bundled["swings"]) == 10
