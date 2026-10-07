"""What every model's card and Model Insights data share.

Each model has a card for the version most competitions are served with
(``<model>.md``), and one for the IPL's (``<model>-ipl.md``) when the IPL keeps
another version. The Model Insights data is the IPL's (``<model>.json``, what the
site shows today) and the pooled T20 version's (``t20/<model>.json``), with its
results in every competition and against the IPL's own model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from criciq_core.groups import model_groups
from criciq_core.phases import model_phases
from criciq_ml import formats

IPL = "IPL"

COMPETITION_LABELS: dict[str, str] = {
    "IPL": "IPL",
    "BBL": "Big Bash League",
    "PSL": "Pakistan Super League",
    "CPL": "Caribbean Premier League",
    "SA20": "SA20",
    "T20I": "Men's T20 internationals",
    "T20": "All T20 cricket",
    "ODI": "Men's ODIs",
}


def label(competition: str) -> str:
    return COMPETITION_LABELS.get(competition, competition)


def in_order(competitions: list[str]) -> list[str]:
    """Competitions in the usual order (the IPL first, T20Is last)."""
    order = list(COMPETITION_LABELS)
    return sorted(competitions, key=lambda c: order.index(c) if c in order else len(order))


def by_competition(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-competition result lines in the usual order."""
    order = in_order([line["competition"] for line in lines])
    return sorted(lines, key=lambda line: order.index(line["competition"]))


def spans_groups(competitions: list[str]) -> bool:
    """Whether a version was fitted across model groups (the pooled T20 versions of V2-3)."""
    return not any(g.covers(competitions) for g in model_groups().groups)


def names(labels: list[str]) -> str:
    """ "A", "A and B", "A, B and C"."""
    return " and ".join([", ".join(labels[:-1]), labels[-1]]) if len(labels) > 1 else labels[0]


def fitted_on(competitions: list[str]) -> str:
    """What a version of several competitions was fitted on, for a card: "every T20
    competition" for the pooled versions, else the competitions by name."""
    if spans_groups(competitions):
        return "every T20 competition"
    return names([label(c) for c in in_order(competitions)])


def pooled_path(path: Path) -> Path:
    """Where the pooled T20 version's Model Insights data goes, beside the IPL's."""
    return path.parent / "t20" / path.name


_PHASE_NAMES = {"powerplay": "Powerplay", "middle": "Middle", "death": "Death"}


def phase_labels() -> dict[str, str]:
    """Each phase with its overs in the models' format: "Powerplay (overs 1-6)",
    "Middle (7-15)", "Death (16-20)" in a T20."""
    phases = sorted(model_phases().phases, key=lambda p: p.first_over)
    labels = {}
    for i, p in enumerate(phases):
        overs = f"{p.first_over}-{p.last_over}"
        labels[p.key] = f"{_PHASE_NAMES.get(p.key, p.label)} ({'overs ' if i == 0 else ''}{overs})"
    return labels


def match_phrase(competitions: list[str]) -> str:
    """What one model covers, as "an IPL match", "a T20 match (BBL, ...)" or "an ODI"."""
    if len(competitions) > 1:
        return "a T20 match (" + ", ".join(label(c) for c in competitions) + ")"
    only = competitions[0] if competitions else IPL
    return {IPL: "an IPL match", "ODI": "an ODI"}.get(only, f"a {label(only)} match")


def format_path(path: Path) -> Path:
    """Where the current format's version of a T20 file goes: ``odi/<name>`` beside it."""
    sub = formats.folder()
    if sub is None:
        raise ValueError("the T20 models' files keep their own places")
    return path.parent / sub / path.name


def ipl_card_path(path: Path) -> Path:
    """The IPL's own card, when it keeps another version than the pooled one."""
    return path.with_name(path.stem + "-ipl" + path.suffix)


def competitions_of(data: dict[str, Any]) -> list[str]:
    """The competitions a version was trained on (the IPL alone for v1)."""
    return in_order(list(data["trained_on"].get("competitions", [IPL])))


def pooled(data: dict[str, Any]) -> bool:
    return len(competitions_of(data)) > 1


def comparison_section(data: dict[str, Any], metric: str, digits: int = 4) -> list[str]:
    """Markdown: the pooled version against the IPL's own on the IPL's test seasons."""
    c = data.get("ipl_comparison")
    if not c:
        return []
    gain = c["v2_gain"]
    unit = "runs of pinball loss" if metric == "pinball" else "log loss"
    keeps = (
        f"**the IPL keeps {c['v1']['version']}** and the pooled version serves the other "
        "competitions."
    )
    if c.get("coverage_ok") is False:
        low, high = c["coverage_band"]
        verdict = (
            f"Its 80% range covers {c['v2']['coverage80']:.1%} of the IPL's test totals, outside "
            f"the {low:.0%}-{high:.0%} the projection's gate requires (too "
            f"{'wide' if c['v2']['coverage80'] > high else 'narrow'} for the IPL), so {keeps}"
        )
    elif c["better"]:
        verdict = "It is better there, and the IPL is served with it."
    elif c["no_worse"]:
        verdict = "It is no worse there, so the IPL is served with it."
    else:
        verdict = f"It is worse there, so {keeps}"
    with_brier = "brier" in c["v1"]
    with_range = "coverage80" in c["v1"]
    title = metric.replace("_", " ").capitalize()
    extra = " |"
    if with_brier:
        extra = " | Brier |"
    elif with_range:
        extra = " | 80% range covers | Range width |"
    lines = [
        "",
        f"## Against the IPL's own model ({c['v1']['version']})",
        "",
        "Pooling every T20 competition is only worth it for the IPL if it predicts the IPL at "
        f"least as well as {c['v1']['version']}, which was trained on the IPL alone. Both are "
        "scored on the same IPL test balls; v1's predictions are rebuilt exactly from its "
        "recorded settings. Intervals resample whole matches.",
        "",
        f"| Model | {title}{extra}",
        "|---|---|" + "---|" * (extra.count("|") - 1),
    ]
    for name, key in (("IPL only", "v1"), ("Pooled T20", "v2")):
        m = c[key]
        cells = f"{m[metric]:.{digits}f}"
        if with_brier:
            cells += f" | {m['brier']:.{digits}f}"
        elif with_range:
            cells += f" | {m['coverage80']:.1%} | {m['width80']:.1f} runs"
        lines.append(f"| {name} ({m['version']}) | {cells} |")
    lines += [
        "",
        f"Gain of the pooled version: **{gain['improvement']:+.{digits}f}** {unit} "
        f"(95% CI {gain['ci_low']:+.{digits}f} to {gain['ci_high']:+.{digits}f}). {verdict}",
    ]
    return lines


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
