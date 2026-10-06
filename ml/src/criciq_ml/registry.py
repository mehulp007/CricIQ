"""Versioned model registry: ``models/<name>/<version>/`` plus a ``CURRENT`` pointer.

Model files are small text artifacts and are committed, so every deployment
scores with a reviewed, versioned model instead of retraining on the fly.

``CURRENT`` names the version every competition is scored with. A competition
can keep another version with its own pointer, ``CURRENT.<competition>``: the
IPL keeps v1 if the pooled T20 model is worse on the IPL's test seasons.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from criciq_core import paths
from criciq_ml.ball_outcome import BallOutcomeModel
from criciq_ml.model import WinProbabilityModel
from criciq_ml.projection import ScoreProjectionModel
from criciq_ml.ratings import RatingsModel
from criciq_ml.simulator import SimulatorSettings

NAME = "win_probability"
PROJECTION = "score_projection"
BALL_OUTCOME = "ball_outcome"
RATINGS = "ratings"
SIMULATOR = "simulator"


def root(name: str = NAME) -> Path:
    return paths.models_dir() / name


def version_dir(version: str, name: str = NAME) -> Path:
    return root(name) / version


def _pointer(name: str, competition: str | None) -> Path:
    return root(name) / ("CURRENT" if competition is None else f"CURRENT.{competition}")


def current_version(name: str = NAME, competition: str | None = None) -> str | None:
    """The version serving ``competition`` (its own pointer, else ``CURRENT``)."""
    for pointer in (_pointer(name, competition), _pointer(name, None)):
        if pointer.exists():
            return pointer.read_text(encoding="utf-8").strip()
    return None


def load_current(name: str = NAME, competition: str | None = None) -> WinProbabilityModel:
    version = current_version(name, competition)
    if version is None:
        raise FileNotFoundError(f"no current {name} model; run `criciq-ml train`")
    return WinProbabilityModel.load(version_dir(version, name))


def load_current_projection(competition: str | None = None) -> ScoreProjectionModel:
    version = current_version(PROJECTION, competition)
    if version is None:
        raise FileNotFoundError("no current score projection model; run `criciq-ml train`")
    return ScoreProjectionModel.load(version_dir(version, PROJECTION))


def load_current_ball_outcome(competition: str | None = None) -> BallOutcomeModel:
    version = current_version(BALL_OUTCOME, competition)
    if version is None:
        raise FileNotFoundError("no current ball-outcome model; run `criciq-ml train`")
    return BallOutcomeModel.load(version_dir(version, BALL_OUTCOME))


def load_current_ratings() -> RatingsModel:
    version = current_version(RATINGS)
    if version is None:
        raise FileNotFoundError("no current ratings; run `criciq-ml train ratings`")
    return RatingsModel.load(version_dir(version, RATINGS))


def load_current_simulator(competition: str | None = None) -> SimulatorSettings:
    version = current_version(SIMULATOR, competition)
    if version is None:
        raise FileNotFoundError("no current simulator; run `criciq-ml train simulator`")
    manifest = json.loads((version_dir(version, SIMULATOR) / "manifest.json").read_text("utf-8"))
    return SimulatorSettings(manifest)


def load_evaluation(version: str, name: str = NAME) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (version_dir(version, name) / "evaluation.json").read_text(encoding="utf-8")
    )
    return data


def save(
    model: WinProbabilityModel
    | ScoreProjectionModel
    | BallOutcomeModel
    | RatingsModel
    | SimulatorSettings,
    evaluation: dict[str, Any],
    name: str = NAME,
) -> Path:
    target = version_dir(model.version, name)
    model.save(target)
    (target / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return target


def promote(version: str, name: str = NAME, competition: str | None = None) -> None:
    _pointer(name, competition).write_text(version + "\n", encoding="utf-8", newline="\n")


def release(name: str, competition: str) -> None:
    """Drop a competition's own pointer: it is then scored with ``CURRENT``."""
    _pointer(name, competition).unlink(missing_ok=True)


def gate(new: dict[str, Any], current: dict[str, Any] | None, tolerance: float) -> list[str]:
    """Reasons a new version must not be promoted (empty = promote)."""
    problems = []
    test = new["test"]
    for metric in ("log_loss", "brier"):
        if test["model"][metric] >= test["baseline"][metric]:
            problems.append(f"does not beat the baseline on test {metric}")
    # Within one competition the test set can be small (60 SA20 matches), so only a
    # competition where the model is clearly worse than the baseline fails it.
    for line in test.get("by_competition", []):
        if line["vs_baseline"]["ci_high"] < 0:
            problems.append(
                f"clearly worse than the baseline on {line['competition']} test log loss"
            )
    # A pooled version is compared with the IPL's on the IPL's own test balls
    # (``ipl_comparison``), which decides whether it serves the IPL; its whole
    # test set is not comparable with an IPL-only version's.
    pooled = "ipl_comparison" in new
    if not pooled and current is not None and current["splits"]["test"] == new["splits"]["test"]:
        regression = test["model"]["log_loss"] - current["test"]["model"]["log_loss"]
        if regression > tolerance:
            problems.append(
                f"test log loss is {regression:.4f} worse than the current version "
                f"(tolerance {tolerance})"
            )
    return problems


def projection_gate(evaluation: dict[str, Any], band: list[float]) -> list[str]:
    """Reasons a score projection version must not be promoted (empty = promote)."""
    test = evaluation["test"]
    problems = []
    low, high = band
    if not low <= test["model"]["coverage80"] <= high:
        problems.append(
            f"80% range covers {test['model']['coverage80']:.1%} of test totals "
            f"(must be {low:.0%}-{high:.0%})"
        )
    for metric in ("mae", "pinball"):
        if test["model"][metric] >= test["par_baseline"][metric]:
            problems.append(f"does not beat the par baseline on test {metric}")
    return problems
