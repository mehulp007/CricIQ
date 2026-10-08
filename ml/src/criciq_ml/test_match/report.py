"""The Test models' cards (``docs/model-cards/test/``) and Model Insights data
(``frontend/data/models/test/``).

Win probability and the innings projection are Test models of their own; the
ball-outcome model and the ratings are written by their own reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from criciq_ml import ball_outcome_report, ratings_report, registry
from criciq_ml.report import INSIGHTS_PATH as WP_INSIGHTS
from criciq_ml.report import MODEL_CARD_PATH as WP_CARD
from criciq_ml.report_common import format_path, write_json, write_text
from criciq_ml.test_match.projection import LEVELS

PROJECTION_INSIGHTS = WP_INSIGHTS.with_name("score-projection.json")
PROJECTION_CARD = WP_CARD.with_name("score-projection.md")

GROUP_LABELS = {
    "teams": "The sides' ratings from earlier Tests",
    "home": "Home advantage",
    "xis": "The XIs' Test records",
    "batting_left": "The batting still to come",
}

# The biggest swing of each Test in the batting side's expected result (a win 1, a
# draw a half), largest first.
SWINGS_SQL = """
WITH w AS (
    SELECT p.match_id, p.innings_no, p.seq_no, p.wp_team_a, p.wp_draw,
           p.wp_team_a + p.wp_draw / 2 AS value_a,
           p.wp_team_a + p.wp_draw / 2
               - lag(p.wp_team_a + p.wp_draw / 2)
                 OVER (PARTITION BY p.match_id ORDER BY p.innings_no, p.seq_no) AS delta,
           row_number() OVER (PARTITION BY p.match_id ORDER BY p.innings_no DESC, p.seq_no DESC)
               AS from_end
    FROM wp_predictions p
),
ranked AS (
    SELECT *, row_number() OVER (PARTITION BY match_id ORDER BY abs(delta) DESC) AS rank
    FROM w
    -- A match's last ball carries its result, not the model's estimate.
    WHERE seq_no > 0 AND delta IS NOT NULL AND from_end > 1
)
SELECT r.match_id, r.innings_no, r.seq_no, r.delta, r.wp_team_a, r.wp_draw,
       d.ball_label, d.runs_total, d.is_four, d.is_six, d.extras_wides,
       wk.kind AS wicket_kind, wk.is_dismissal,
       pb.name AS batter, pw.name AS bowler, po.name AS player_out,
       ms.season, ms.match_date, ms.team_a_short, ms.team_b_short, ms.result_text
FROM ranked r
JOIN deliveries d USING (match_id, innings_no, seq_no)
JOIN match_summaries ms USING (match_id)
JOIN players pb ON pb.player_id = d.batter_id
JOIN players pw ON pw.player_id = d.bowler_id
LEFT JOIN wickets wk ON wk.match_id = d.match_id AND wk.innings_no = d.innings_no
    AND wk.seq_no = d.seq_no AND wk.wicket_no = 1
LEFT JOIN players po ON po.player_id = wk.player_out_id
WHERE r.rank = 1
ORDER BY abs(r.delta) DESC
LIMIT ?
"""


def _describe(row: dict[str, Any]) -> str:
    who = f"{row['bowler']} to {row['batter']}"
    if row["wicket_kind"] and row["is_dismissal"]:
        return f"{who}: OUT, {row['player_out']} {row['wicket_kind']}"
    if row["is_six"]:
        return f"{who}: SIX"
    if row["is_four"]:
        return f"{who}: FOUR"
    runs = int(row["runs_total"])
    return f"{who}: {'no run' if runs == 0 else f'{runs} run' + ('s' if runs > 1 else '')}"


def biggest_swings(serving: Path, limit: int = 10) -> list[dict[str, Any]]:
    con = duckdb.connect(str(serving), read_only=True)
    try:
        cursor = con.execute(SWINGS_SQL, [limit])
        columns = [c[0] for c in cursor.description or []]
        rows = [dict(zip(columns, r, strict=True)) for r in cursor.fetchall()]
    finally:
        con.close()
    swings = []
    for r in rows:
        benefited_a = r["delta"] > 0
        win_a, draw = float(r["wp_team_a"]), float(r["wp_draw"])
        swings.append(
            {
                "match_id": int(r["match_id"]),
                "innings_no": int(r["innings_no"]),
                "seq_no": int(r["seq_no"]),
                "ball_label": r["ball_label"],
                "season": int(r["season"]),
                "date": r["match_date"].isoformat(),
                "teams": f"{r['team_a_short']} vs {r['team_b_short']}",
                "result": r["result_text"],
                "description": _describe(r),
                "team": r["team_a_short"] if benefited_a else r["team_b_short"],
                "swing": round(abs(float(r["delta"])) * 100, 1),
                "win_after": round((win_a if benefited_a else 1 - win_a - draw) * 100, 1),
                "draw_after": round(draw * 100, 1),
            }
        )
    return swings


def _manifest(name: str, version: str) -> dict[str, Any]:
    path = registry.version_dir(version, name) / "manifest.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def wp_insights(version: str, serving: Path | None) -> dict[str, Any]:
    evaluation = registry.load_evaluation(version)
    manifest = _manifest(registry.NAME, version)
    return {
        "name": manifest["name"],
        "kind": "test",
        "version": version,
        "data_version": evaluation["data_version"],
        "trained_on": manifest["trained_on"],
        "splits": evaluation["splits"],
        "groups": {
            n: [{"key": g, "label": GROUP_LABELS[g]} for g in groups]
            for n, groups in evaluation["groups"].items()
        },
        "selection": evaluation["selection"],
        "selection_years": evaluation["selection_years"],
        "alternatives": evaluation["alternatives"],
        "test": evaluation["test"],
        "backtest": evaluation["backtest"],
        "swings": biggest_swings(serving) if serving is not None else [],
    }


def projection_insights(version: str) -> dict[str, Any]:
    evaluation = registry.load_evaluation(version, registry.PROJECTION)
    manifest = _manifest(registry.PROJECTION, version)
    return {
        "name": manifest["name"],
        "kind": "test",
        "version": version,
        "data_version": evaluation["data_version"],
        "trained_on": manifest["trained_on"],
        "splits": evaluation["splits"],
        "levels": list(LEVELS),
        "test": evaluation["test"],
        "backtest": evaluation["backtest"],
    }


# ---------------------------------------------------------------- cards


def _years(values: list[int]) -> str:
    return f"{values[0]}-{values[-1]}" if len(values) > 1 else str(values[0])


INNINGS_NAMES = {
    "1": "First innings",
    "2": "Second innings",
    "3": "Third innings",
    "4": "Fourth innings",
}


def wp_card(data: dict[str, Any]) -> str:
    test, splits = data["test"], data["splits"]
    gain = test["vs_baseline"]
    trained = data["trained_on"]
    m, b = test["model"], test["baseline"]
    better = gain["ci_low"] > 0
    level = gain["ci_high"] >= 0 and not better
    verdict = (
        "clearly better than the baseline"
        if better
        else "level with the baseline (the interval includes zero)"
        if level
        else "worse than the baseline"
    )
    lines = [
        f"# Model card: Test win probability ({data['version']})",
        "",
        "For any moment of a men's Test: the chance that the side batting first wins, that "
        "the match is drawn, and that the other side wins. Trained on Tests only.",
        "",
        "## What it is",
        "",
        "- **Three outcomes.** A Test can be won, lost or drawn: a draw is what happens when "
        "time runs out. Every probability on the site is a triple that adds up to 100%.",
        "- **A multinomial regression per innings** (four of them), on the match state: the "
        "lead (in the fourth innings, the runs needed and the rate they need), wickets in "
        "hand, the overs left and the scoring era (runs per wicket over the previous 40 "
        "Tests).",
        "- **Context known before the match**, where it earned its place (below): each enters "
        "as itself and scaled by the share of the match still to play, since a stronger side "
        "has more time to show it.",
        "- **Time left is estimated.** Cricsheet has no session or time-of-day data, so the "
        "overs left are five days of 90 overs less the overs bowled. That ignores rain, bad "
        "light and the breaks between innings: drawn Tests in the data averaged 361 overs, not "
        "450. The model learns how much of the nominal time is really left from history, but "
        "it cannot know about a washed-out day.",
        "- **A match's last ball carries its result**, not an estimate.",
        "",
        "## Data",
        "",
        f"- {trained['matches']:,} men's Tests from {trained['seasons'][0]} to "
        f"{trained['seasons'][1]} (Cricsheet). Ties and awarded matches have no outcome to "
        "learn from.",
        f"- **Test:** fitted on every Test before {min(splits['test'])}, scored once on "
        f"{_years(splits['test'])} ({test['matches']} Tests: "
        f"{test['outcomes']['won']} won by the side batting at the time of the last ball, "
        f"{test['outcomes']['drawn']} drawn). The test years were never used for any choice.",
        f"- **Choices** were made on a rolling origin over {_years(data['selection_years'])}: "
        "each year predicted from a fit on every earlier year. About 40 Tests are played a "
        "year, so a single pair of validation years is too few to choose on.",
        "",
        "## Context it uses",
        "",
        "| Innings | Context added to the match state |",
        "|---|---|",
    ]
    for number, groups in data["groups"].items():
        added = ", ".join(g["label"] for g in groups) or "none (the match state alone)"
        lines.append(f"| {INNINGS_NAMES[number]} | {added} |")
    lines += [
        "",
        "Each group was added while it lowered the rolling-origin log loss. The XIs' records "
        "and the batting still to come were tried in every innings.",
        "",
        "## Results on the test years",
        "",
        "| | Log loss | Brier | ECE (win / draw / loss) |",
        "|---|---|---|---|",
    ]
    for name, s in (("Model", m), ("Baseline (match state only)", b)):
        e = s["ece"]
        lines.append(
            f"| {name} | {s['log_loss']:.4f} | {s['brier']:.4f} | "
            f"{e['won']:.3f} / {e['drawn']:.3f} / {e['lost']:.3f} |"
        )
    lines += [
        "",
        f"Improvement over the baseline: **{gain['improvement']:+.4f}** log loss (95% CI "
        f"{gain['ci_low']:+.4f} to {gain['ci_high']:+.4f}, resampling whole Tests): {verdict}.",
        "",
        "| Innings | Model log loss | Baseline |",
        "|---|---|---|",
    ]
    for row in test["by_innings"]:
        lines.append(
            f"| {INNINGS_NAMES[str(row['innings_no'])]} | {row['model']['log_loss']:.4f} | "
            f"{row['baseline']['log_loss']:.4f} |"
        )
    lines += ["", "| Day (estimated) | Model log loss | Baseline |", "|---|---|---|"]
    for row in test["by_day"]:
        lines.append(
            f"| {row['day']} | {row['model_log_loss']:.4f} | {row['baseline_log_loss']:.4f} |"
        )
    wins = sum(r["model_log_loss"] < r["baseline_log_loss"] for r in data["backtest"])
    lines += [
        "",
        "## Backtest",
        "",
        f"Each year fitted on every earlier year. Better than the baseline in {wins} of "
        f"{len(data['backtest'])} years.",
        "",
        "| Year | Tests | Model log loss | Baseline |",
        "|---|---|---|---|",
    ]
    for r in data["backtest"]:
        lines.append(
            f"| {r['season']} | {r['matches']} | {r['model_log_loss']:.4f} | "
            f"{r['baseline_log_loss']:.4f} |"
        )
    if data["alternatives"]:
        lines += [
            "",
            "## Why not boosted trees",
            "",
            "The limited-overs models are boosted trees. For Tests they were fitted on the same "
            "features and rolling origin:",
            "",
            "| Model | Rolling-origin log loss |",
            "|---|---|",
        ]
        for row in data["alternatives"]:
            lines.append(f"| {row['model'].capitalize()} | {row['log_loss']:.4f} |")
        lines += [
            "",
            "Every ball of a Test shares one result and there are only about 800 Tests, so trees "
            "split on the context that is the same for a whole match and memorise individual "
            "Tests. A regression cannot.",
        ]
    lines += [
        "",
        "## Limits",
        "",
        "- About 40 Tests a year: year-to-year results move a lot, and one surprising match "
        "weighs heavily.",
        "- No pitch, weather or session data (out of scope): a turning pitch or a forecast of "
        "rain is invisible.",
        "- Declarations are not modelled as decisions: the model only knows how such states "
        "turned out before.",
        "- Not betting advice.",
        "",
    ]
    return "\n".join(lines)


def projection_card(data: dict[str, Any]) -> str:
    test, splits = data["test"], data["splits"]
    m, p = test["model"], test["par_baseline"]
    lines = [
        f"# Model card: Test innings projection ({data['version']})",
        "",
        "Where the innings being played will finish, as a range: the 5th to 95th "
        "percentiles of its final total. Every innings of a Test is projected. Trained on "
        "Tests only.",
        "",
        "## What it is",
        "",
        "- One LightGBM quantile model per level predicts the runs still to come, from the "
        "score, wickets in hand, the innings so far and the last ten overs, the lead, the "
        "overs left in the match (estimated: five days of 90 overs less the overs bowled), "
        "the innings number, the scoring era, the batting still to come and the fielding "
        "side's bowling strength.",
        "- An innings ends when the side is bowled out, declares, reaches a fourth-innings "
        "target or runs out of time; the model learns all of these from history.",
        f"- Conformal shifts per level, measured on held-out years ({_years(splits['calibrate'])} "
        "for the test), make about the stated share of totals fall below each level.",
        "",
        "## Results on the test years",
        "",
        f"Fitted on Tests before {min(splits['test']) - 2}, calibrated on "
        f"{_years(splits['calibrate'])}, scored once on {_years(splits['test'])} "
        f"({test['innings']} innings).",
        "",
        "| | Pinball loss (runs) | Mean abs. error of the median | 80% range covers | Range width |",
        "|---|---|---|---|---|",
    ]
    for name, s in (("Model", m), ("Par (by innings and wickets)", p)):
        lines.append(
            f"| {name} | {s['pinball']:.2f} | {s['mae']:.1f} runs | {s['coverage80']:.1%} | "
            f"{s['width80']:.0f} runs |"
        )
    lines += ["", "| Innings | Model MAE | Par MAE | 80% range covers |", "|---|---|---|---|"]
    for row in test["by_innings"]:
        lines.append(
            f"| {INNINGS_NAMES[str(row['innings_no'])]} | {row['model']['mae']:.1f} | "
            f"{row['par_baseline']['mae']:.1f} | {row['model']['coverage80']:.1%} |"
        )
    wins = sum(r["model_pinball"] < r["par_pinball"] for r in data["backtest"])
    lines += [
        "",
        "## Backtest",
        "",
        f"Each year: fitted on the years before the previous two, calibrated on those two. "
        f"Better than par in {wins} of {len(data['backtest'])} years.",
        "",
        "| Year | Pinball (model) | Pinball (par) | 80% range covers |",
        "|---|---|---|---|",
    ]
    for r in data["backtest"]:
        lines.append(
            f"| {r['season']} | {r['model_pinball']:.2f} | {r['par_pinball']:.2f} | "
            f"{r['coverage80']:.1%} |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Declarations depend on the captain and the match situation; the model only knows "
        "how such innings ended before.",
        "- No pitch or weather data.",
        "",
    ]
    return "\n".join(lines)


def write_test(servings: dict[str, Path]) -> list[Path]:
    """The Test group's cards and Model Insights data (``use_group("test")``)."""
    written = [*ball_outcome_report.write_format(), *ratings_report.write_format()]
    serving = next(iter(servings.values()), None)
    version = registry.current_version(registry.NAME)
    if version is not None:
        data = wp_insights(version, serving)
        written += [
            write_json(format_path(WP_INSIGHTS), data),
            write_text(format_path(WP_CARD), wp_card(data)),
        ]
    projection = registry.current_version(registry.PROJECTION)
    if projection is not None:
        data = projection_insights(projection)
        written += [
            write_json(format_path(PROJECTION_INSIGHTS), data),
            write_text(format_path(PROJECTION_CARD), projection_card(data)),
        ]
    return written
