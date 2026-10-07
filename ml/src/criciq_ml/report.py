"""Model card and Model Insights data, generated from the registry.

Numbers are never copied by hand: the model card (docs/model-cards) and the
data behind the web app's Model Insights page both come from the evaluation
stored with the model version.

Which cards and data files each model gets is described in
``criciq_ml.report_common``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from criciq_core import paths
from criciq_ml import (
    ball_outcome_report,
    lab,
    projection_report,
    ratings_report,
    registry,
    simulator_report,
)
from criciq_ml.report_common import (
    IPL,
    by_competition,
    comparison_section,
    competitions_of,
    fitted_on,
    format_path,
    ipl_card_path,
    match_phrase,
    phase_labels,
    pooled_path,
    write_json,
    write_text,
)
from criciq_ml.report_common import label as competition_label

FEATURE_LABELS: dict[str, str] = {
    "legal_balls": "Legal balls bowled",
    "runs": "Runs scored",
    "wickets": "Wickets lost",
    "runs_vs_par": "Runs above the era's par for this stage",
    "runs_last_12": "Runs in the last 12 legal balls",
    "wickets_last_12": "Wickets in the last 12 legal balls",
    "balls_remaining": "Balls remaining",
    "runs_needed": "Runs needed",
    "required_rate": "Required run rate",
    "chase_ratio": "Runs needed vs balls left (log ratio)",
    "required_rate_rel": "Required rate relative to the era's scoring rate",
    "chase_dp": "Chance of the chase from a ball-by-ball dynamic programme",
    "opp_bat_strength": "Opposition batting strength (the XI's career averages)",
    "own_bowl_strength": "Own bowling strength (the main bowlers' career economy)",
    "international": "International cricket (rather than a league)",
    "crease_sr_idx": "Batters at the crease: career strike rate",
    "crease_avg_idx": "Batters at the crease: career average",
    "crease_balls": "Batters at the crease: balls faced so far",
    "depth_avg_sum": "Batting still to come (career averages)",
    "bowl_left_econ_idx": "Bowling still to come (career economy)",
    "venue_idx": "Venue scoring index",
    "env_rpb": "The competition's scoring rate (the era)",
    "target_vs_par": "Target relative to the era's par",
}

CANDIDATE_LABELS: dict[str, str] = {
    "served": "Served features",
    "+crease": "+ Batters at the crease (career strike rate, average, balls faced)",
    "+depth": "+ Batting still to come (career averages)",
    "+bowling": "+ Bowling still to come (career economy, 4-over quotas)",
    "+squads": "+ Squad strength (opposition batting, own bowling)",
    "+venue": "+ Venue scoring index",
    "+target_size": "+ Target relative to the era's par",
    "+era": "+ The competition's scoring rate",
    "+international": "+ International cricket",
}

GROUP_LABELS: dict[str, str] = {
    "situation": "Score for the stage / chase equation",
    "wickets": "Wickets in hand",
    "recent": "Last two overs",
    "teams": "Who is playing (the XIs' records, international cricket)",
}


INSIGHTS_PATH = paths.repo_root() / "frontend" / "data" / "models" / "win-probability.json"
MODEL_CARD_PATH = paths.repo_root() / "docs" / "model-cards" / "win-probability.md"
SWINGS_SQL = """
WITH w AS (
    SELECT match_id, innings_no, seq_no, wp_team_a,
           wp_team_a - lag(wp_team_a) OVER (
               PARTITION BY match_id, innings_no ORDER BY seq_no) AS delta
    FROM wp_predictions
),
ranked AS (
    SELECT w.*, row_number() OVER (PARTITION BY match_id ORDER BY abs(delta) DESC) AS rank
    FROM w WHERE seq_no > 0 AND delta IS NOT NULL
)
SELECT r.match_id, r.innings_no, r.seq_no, r.delta, r.wp_team_a,
       d.ball_label, d.runs_batter, d.runs_total, d.is_four, d.is_six, d.extras_wides,
       d.extras_noballs, wk.kind AS wicket_kind, wk.is_dismissal,
       pb.name AS batter, pw.name AS bowler, po.name AS player_out,
       ms.season, ms.match_date, ms.team_a_short, ms.team_b_short, ms.team_a_name,
       ms.team_b_name, ms.result_text, ms.stage
FROM ranked r
JOIN deliveries d USING (match_id, innings_no, seq_no)
JOIN match_summaries ms USING (match_id)
JOIN players pb ON pb.player_id = d.batter_id
JOIN players pw ON pw.player_id = d.bowler_id
LEFT JOIN wickets wk ON wk.match_id = d.match_id AND wk.innings_no = d.innings_no
    AND wk.seq_no = d.seq_no AND wk.wicket_no = 1
LEFT JOIN players po ON po.player_id = wk.player_out_id
WHERE r.rank = 1 AND ms.win_method IS NULL
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
    if row["extras_wides"]:
        return f"{who}: wide"
    runs = int(row["runs_total"])
    return f"{who}: {'no run' if runs == 0 else f'{runs} run' + ('s' if runs > 1 else '')}"


def biggest_swings(serving: Path, limit: int = 10) -> list[dict[str, Any]]:
    """The single biggest win-probability swing in each match, largest first."""
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
        swings.append(
            {
                "match_id": int(r["match_id"]),
                "innings_no": int(r["innings_no"]),
                "seq_no": int(r["seq_no"]),
                "ball_label": r["ball_label"],
                "season": int(r["season"]),
                "date": r["match_date"].isoformat(),
                "stage": r["stage"],
                "teams": f"{r['team_a_short']} vs {r['team_b_short']}",
                "result": r["result_text"],
                "description": _describe(r),
                "team": r["team_a_short"] if benefited_a else r["team_b_short"],
                "swing": round(abs(float(r["delta"])) * 100, 1),
                "wp_after": round(
                    (float(r["wp_team_a"]) if benefited_a else 1 - float(r["wp_team_a"])) * 100, 1
                ),
            }
        )
    return swings


def insights(version: str, serving: Path, *, swings: bool = True) -> dict[str, Any]:
    evaluation = registry.load_evaluation(version)
    manifest = json.loads(
        (registry.version_dir(version) / "manifest.json").read_text(encoding="utf-8")
    )
    return {
        "name": manifest["name"],
        "version": version,
        "data_version": evaluation["data_version"],
        "trained_on": manifest["trained_on"],
        "splits": evaluation["splits"],
        "features": {
            number: [{"key": f, "label": FEATURE_LABELS[f]} for f in features]
            for number, features in manifest["features"].items()
        },
        "calibration": {
            **evaluation["calibration"],
            "served": manifest["calibration"],
        },
        "test": evaluation["test"],
        "importance": [
            {"group": g, "label": GROUP_LABELS[g], "share": share}
            for g, share in sorted(evaluation["importance"].items(), key=lambda kv: -kv[1])
        ],
        "feature_selection": [
            {**row, "label": CANDIDATE_LABELS.get(row["variant"], row["variant"])}
            for row in evaluation["feature_selection"]
        ],
        "backtest": evaluation["backtest"],
        "swings": biggest_swings(serving) if swings else [],
        **(
            {"ipl_comparison": evaluation["ipl_comparison"]}
            if "ipl_comparison" in evaluation
            else {}
        ),
    }


# ---------------------------------------------------------------- model card


def _f(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _seasons(values: list[int]) -> str:
    return f"{values[0]}-{values[-1]}" if len(values) > 1 else str(values[0])


METHOD_LABELS = {
    "none": "no calibration (trained on every earlier season)",
    "platt": "Platt scaling on the two most recent seasons",
    "isotonic": "isotonic calibration on the two most recent seasons",
}


def model_card(data: dict[str, Any]) -> str:
    test, splits = data["test"], data["splits"]
    calibration = data["calibration"]["method"]
    vs_base, vs_state = test["vs_baseline"], test["vs_state_only"]
    first_test = min(splits["test"])
    trained = data["trained_on"]
    competitions = competitions_of(data)
    pooled = len(competitions) > 1
    # Pooled versions split by calendar year (a BBL season spans two).
    period = "years" if pooled else "seasons"
    covers = match_phrase(competitions)

    def method(key: str) -> str:
        return METHOD_LABELS[key].replace("season", period[:-1])

    lines = [
        "# Model card: win probability",
        "",
        "<!-- Generated by `criciq-ml report` from the model registry. Do not edit by hand. -->",
        "",
        f"**Version** {data['version']} · **data** {data['data_version']} · served model "
        f"trained on {_seasons(trained['seasons'])} ({trained['matches']:,} matches, "
        f"{trained['rows']:,} match states)",
        "",
        "## What it does",
        "",
        f"Estimates each side's chance of winning {covers} after every delivery"
        + (", with one model fitted on all of them at once. " if pooled else ". ")
        + "Two gradient-boosted tree models (LightGBM) cover the two innings: the first estimates "
        "the chance that the side batting first wins, the second the chance that the chasing "
        "side wins. Outputs are **model estimates of historical patterns**, shown in replays "
        "of completed matches. They are not predictions of future matches and must not be "
        "used for betting.",
        "",
        "## Evaluation protocol",
        "",
        f"- **Tune** on {_seasons(splits['validation'])}: every grid candidate is trained on "
        f"{_seasons(splits['train'])} with early stopping on those {period}.",
        f"- **Choose calibration** with a rolling origin over the {period} before "
        f"{first_test} (see below).",
        f"- **Test** on {_seasons(splits['test'])}, touched once, with a model trained only "
        f"on earlier {period}.",
        *(
            [
                "- Splits are calendar years of the match date (cut-offs on 1 January), so a "
                "BBL season that spans the new year falls on both sides of one."
            ]
            if pooled
            else []
        ),
        "- A match's balls never cross splits. Matches without a result are excluded, and "
        "ties count as half a win.",
        "- The final ball of a finished chase is excluded from scoring. The probability there "
        "comes from the rules (target reached, all out or overs used up), not from the model.",
        "- Uncertainty intervals resample whole matches (paired bootstrap), because balls "
        "within a match are strongly correlated.",
        "",
        f"## Test results ({test['matches']} matches, {test['model']['rows']:,} match states)",
        "",
        "| Model | Log loss | Brier | ECE | AUC |",
        "|---|---|---|---|---|",
    ]
    rows = [(f"**CricIQ win probability**: {method(calibration)}", test["model"])]
    rows += [(f"Same model, {method(a['key'])}", a) for a in test["alternatives"]]
    rows += [
        ("Boosted trees on the match state only", test["state_only"]),
        ("Logistic regression on the match state (baseline)", test["baseline"]),
    ]
    for label, m in rows:
        lines.append(
            f"| {label} | {_f(m['log_loss'])} | {_f(m['brier'])} | {_f(m['ece'])} | "
            f"{_f(m['auc'], 3)} |"
        )
    lines += [
        "",
        f"- Log-loss improvement over the logistic baseline: **{vs_base['improvement']:+.4f}** "
        f"(95% CI {vs_base['ci_low']:+.4f} to {vs_base['ci_high']:+.4f}).",
        f"- Over boosted trees on the match state only: **{vs_state['improvement']:+.4f}** "
        f"(95% CI {vs_state['ci_low']:+.4f} to {vs_state['ci_high']:+.4f}).",
        "",
    ]
    if test.get("by_competition"):
        lines += [
            "### By competition (test)",
            "",
            "| Competition | Matches | Log loss (model) | Log loss (baseline) | Gain (95% CI) |",
            "|---|---|---|---|---|",
        ]
        for r in by_competition(test["by_competition"]):
            g = r["vs_baseline"]
            lines.append(
                f"| {competition_label(r['competition'])} | "
                f"{r['matches']} | {_f(r['model']['log_loss'])} | {_f(r['baseline']['log_loss'])} "
                f"| {g['improvement']:+.4f} ({g['ci_low']:+.4f} to {g['ci_high']:+.4f}) |"
            )
        lines += [
            "",
            "A competition's test set can be small (60-150 matches outside T20Is), so the "
            "promotion gate only fails a competition where the model is clearly worse than the "
            "baseline (the whole interval below zero).",
        ]
        lines += comparison_section(data, "log_loss")
        lines.append("")
    lines += [
        "### By innings and phase (test)",
        "",
        "| Innings | Phase | Balls | Log loss (model) | Log loss (baseline) | Brier (model) | "
        "Brier (baseline) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in test["by_phase"]:
        lines.append(
            f"| {r['innings_no']} | {phase_labels()[r['phase']]} | {r['rows']:,} | "
            f"{_f(r['model_log_loss'])} | {_f(r['baseline_log_loss'])} | "
            f"{_f(r['model_brier'])} | {_f(r['baseline_brier'])} |"
        )
    lines += [
        "",
        (
            "Before a ball is bowled, the squads' records separate lopsided matches (T20Is "
            "between full members and associates); between balanced sides the start of a match "
            "stays close to a coin flip."
            if pooled
            else "The start of the first innings is close to a coin flip for every model: before a "
            "ball is bowled, nothing in the data separates the sides reliably."
        ),
        "",
        "## Rolling-origin backtest",
        "",
        f"For each {period[:-1]} *s*, the model is trained with {method(calibration)} on "
        f"{period} before *s* and tested on *s*, with the tuned settings frozen. The baseline "
        f"is trained on the same {period}.",
        "",
        f"| {period[:-1].capitalize()} | Matches | Log loss (model) | Log loss (baseline) | "
        "Brier (model) | Brier (baseline) |",
        "|---|---|---|---|---|---|",
    ]
    wins = 0
    for r in data["backtest"]:
        wins += r["model_log_loss"] < r["baseline_log_loss"]
        lines.append(
            f"| {r['season']} | {r['matches']} | {_f(r['model_log_loss'])} | "
            f"{_f(r['baseline_log_loss'])} | {_f(r['model_brier'])} | {_f(r['baseline_brier'])} |"
        )
    lines += [
        "",
        f"The model has the lower log loss in {wins} of {len(data['backtest'])} {period}. "
        + (
            "Early years hold few matches, so their differences are noisy."
            if pooled
            else "A season is only 57-74 matches, so single-season differences are noisy."
        ),
        "",
        "## Features",
        "",
    ]
    for number, title in (("1", "First innings"), ("2", "Chase")):
        lines.append(
            f"**{title}:** " + "; ".join(f["label"] for f in data["features"][number]) + "."
        )
        lines.append("")
    lines += [
        "- **Monotonic constraints** enforce cricket common sense. More runs or fewer wickets "
        "lost never lower the batting side's chance, and in a chase neither do fewer runs "
        "needed or more balls left.",
        "- **The scoring era** is a rolling scoring rate over the competition's previous 60 "
        "matches. It keeps scores comparable across seasons, when average totals rose "
        "sharply" + (", and across competitions that score at different rates." if pooled else "."),
        "- **The chase dynamic programme** is a WASP-style recursion. It gives the exact "
        "chance of a chase for a simplified game in which each ball is drawn from "
        "death-over outcome rates of the three previous seasons"
        + (
            " (each competition's own, or every competition's where one has too few)"
            if pooled
            else ""
        )
        + ". It is sharp where "
        "the trees are coarse: the last few balls, where data is thin. It also knows that "
        "13 off the last ball is impossible.",
        "- **Team identity is never a feature**, because squads change every season.",
        *(
            [
                "- **Players carry their records across competitions**: a career average in "
                f"the squad and crease features counts {fitted_on(competitions)}, shrunk "
                "toward the average player.",
                "- **Ratios are rounded** to nine decimals in training and scoring, so values "
                "that are equal in exact arithmetic are equal on every CPU and a tree split "
                "cannot fall between them.",
            ]
            if pooled
            else []
        ),
        "",
        "### Feature selection",
        "",
    ]
    better = [
        r
        for r in data["feature_selection"]
        if r["variant"] != "served"
        and r["log_loss"]
        < next(
            s["log_loss"]
            for s in data["feature_selection"]
            if s["variant"] == "served" and s["innings_no"] == r["innings_no"]
        )
    ]
    seasons = data["feature_selection"][0]["seasons"]
    lines += [
        "Player, venue and squad features were built leak-free: each uses only matches "
        "played earlier, with empirical-Bayes shrinkage toward the league average. Each "
        "group was then tested by adding it to the served features, using the rolling-origin "
        f"protocol on {_seasons(seasons)} and never the test {period}.",
        "",
        *(
            [
                "Pooled, they were chosen by forward selection: the squads' records and "
                "international cricket helped in the first step, the batters at the crease (first "
                "innings only) in the second, and nothing gained 0.002 in a third. The table "
                "shows the last step, against the served features.",
                "",
            ]
            if pooled
            else []
        ),
        (
            "None improved log loss, so the served model leaves them out. That is itself a "
            "finding: once the match is under way, the score, wickets and balls left carry the "
            "signal, and career records add noise."
            if not better
            else "Groups that still improved log loss: "
            + ", ".join(f"{r['label']} (innings {r['innings_no']})" for r in better)
            + (
                ", each by less than the 0.002 a step needs, so they are left out."
                if pooled
                else "."
            )
        ),
        "",
        "| Innings | Variant | Log loss | Brier |",
        "|---|---|---|---|",
    ]
    for r in data["feature_selection"]:
        lines.append(
            f"| {r['innings_no']} | {r['label']} | {_f(r['log_loss'])} | {_f(r['brier'])} |"
        )
    selection = data["calibration"]["selection"]
    lines += [
        "",
        "## Calibration",
        "",
        "Calibrating on the most recent seasons tracks drift in the scoring era, but it costs "
        "those seasons as training data. A season-specific shift, such as dew or the toss, "
        "can also overshoot. So each training run measures the choice with the rolling "
        f"origin on {_seasons(seasons)}:",
        "",
        "| Method | Log loss | Brier |",
        "|---|---|---|",
    ]
    for r in selection:
        lines.append(f"| {method(r['method'])} | {_f(r['log_loss'])} | {_f(r['brier'])} |")
    lines += [
        "",
        f"This version uses **{method(calibration)}**. The test table above shows the "
        "alternatives for comparison.",
        "",
        "## Explanations",
        "",
        "Each estimate is explained with TreeSHAP contributions, computed exactly by "
        "LightGBM on the model's log-odds (and scaled by the calibration slope if there is "
        "one). They are converted to percentage points relative to the model's average "
        f"prediction and grouped into {len(data['importance'])} concepts:",
        "",
        "| Concept | Share of explanation (test) |",
        "|---|---|",
    ]
    for item in data["importance"]:
        lines.append(f"| {item['label']} | {item['share'] * 100:.0f}% |")
    lines += [
        "",
        "## Limitations",
        "",
        (
            "- Associate nations' T20Is are lopsided and their players' records are short, "
            "which is where the squads' records help most. Outside T20Is a competition's test "
            "set is 60-150 matches, so its own results are noisy."
            if pooled
            else f"- About {round(data['trained_on']['matches'], -2):,} matches is a small sample. "
            + (
                "Gains over a strong baseline are real but modest"
                if vs_base["ci_low"] > 0
                else "On the test matches the model is ahead of a strong baseline, but the 95% "
                "interval includes no gain"
            )
            + ", and single-season results are noisy."
        ),
        "- Rain-revised targets are only known in their final form, so the few interrupted "
        "chases use the revised target from the first ball.",
        "- Weather, pitch reports, injuries and team news are not in the data.",
        "- Super overs are not modelled. A tie shows 50% at the end of regulation play.",
        "",
    ]
    return "\n".join(lines)


def write_format(servings: dict[str, Path]) -> list[Path]:
    """Model cards and Model Insights data of a model group's models (the current one,
    ``criciq_ml.formats.use_group``, or another format's): ``docs/model-cards/<group>/``
    and ``frontend/data/models/<group>/``. ``servings`` are its competitions' serving
    databases, whose replays give the biggest swings (each competition's, for a group
    of several)."""
    written = [
        *projection_report.write_format(),
        *ball_outcome_report.write_format(),
        *ratings_report.write_format(),
        *simulator_report.write_format(),
    ]
    version = registry.current_version()
    if version is None or not servings:
        return written
    if len(servings) == 1:
        data = insights(version, next(iter(servings.values())))
    else:
        data = {
            **insights(version, next(iter(servings.values())), swings=False),
            "swings_by_competition": {
                c: biggest_swings(path) for c, path in sorted(servings.items())
            },
        }
    return [
        write_json(format_path(INSIGHTS_PATH), data),
        write_text(format_path(MODEL_CARD_PATH), model_card(data)),
        *written,
    ]


def write_all(serving: Path, others: dict[str, Path] | None = None) -> list[Path]:
    """Model cards and Model Insights data for every current model. ``others`` are the
    other competitions' serving databases, whose biggest swings go with the pooled data."""
    written = [
        *projection_report.write_all(),
        *ball_outcome_report.write_all(),
        *ratings_report.write_all(),
        *simulator_report.write_all(),
        *lab.write_all(serving),
    ]
    default = registry.current_version()
    ipl = registry.current_version(registry.NAME, IPL)
    if default is None or ipl is None:
        return written
    # The site's Model Insights shows the IPL's model; swings come from its replays.
    ipl_data = insights(ipl, serving)
    out = [write_json(INSIGHTS_PATH, ipl_data)]
    data = ipl_data if default == ipl else insights(default, serving, swings=False)
    out.append(write_text(MODEL_CARD_PATH, model_card(data)))
    if default != ipl:
        out.append(write_text(ipl_card_path(MODEL_CARD_PATH), model_card(ipl_data)))
    if len(competitions_of(data)) > 1:
        swings = {c: biggest_swings(path) for c, path in sorted((others or {}).items())}
        out.append(
            write_json(pooled_path(INSIGHTS_PATH), {**data, "swings_by_competition": swings})
        )
    return [*out, *written]
