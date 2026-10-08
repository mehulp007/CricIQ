"""Versioned model registry: ``models/<group>/<name>/<version>/`` plus pointers.

Model files are small text artifacts and are committed, so every deployment
scores with a reviewed, versioned model instead of retraining on the fly.

Each model group (``criciq_core.groups``) has its own registry
(``criciq_ml.formats.models_root``). ``CURRENT`` names the version its
competitions are scored with; a competition can have its own pointer,
``CURRENT.<competition>`` (each competition's simulator, which passes or fails
its own backtest). The IPL's versions share ``models/`` with the pooled T20
models of V2-3 and are marked by ``CURRENT.IPL``.

While scoring (``use_group(..., serving=True)``), a T20 group that has no current
version of a model yet is scored with the pooled T20 one, so its competitions keep
their predictions until the group's own models are trained; a group with a
simulator of its own never borrows the pooled simulator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from criciq_core.phases import MODEL_FORMAT, model_format
from criciq_ml import formats
from criciq_ml.ball_outcome import BallOutcomeModel
from criciq_ml.model import WinProbabilityModel
from criciq_ml.projection import ScoreProjectionModel
from criciq_ml.ratings import RatingsModel
from criciq_ml.simulator import SimulatorSettings
from criciq_ml.test_match.projection import TestProjectionModel
from criciq_ml.test_match.win_probability import TestWinProbabilityModel

NAME = "win_probability"
PROJECTION = "score_projection"
BALL_OUTCOME = "ball_outcome"
RATINGS = "ratings"
SIMULATOR = "simulator"


def root(name: str = NAME) -> Path:
    return formats.models_root() / name


def version_dir(version: str, name: str = NAME) -> Path:
    return root(name) / version


def _pointer(name: str, competition: str | None) -> Path:
    """The pointer a promotion writes: the competition's, else the group's own."""
    owner = competition or formats.default_pointer()
    return root(name) / ("CURRENT" if owner is None else f"CURRENT.{owner}")


def _pointer_names(competition: str | None, group_pointer: str | None) -> list[str]:
    owners = [c for c in (competition, group_pointer) if c is not None]
    return [f"CURRENT.{c}" for c in dict.fromkeys(owners)] + ["CURRENT"]


def _read(base: Path, names: list[str]) -> str | None:
    for pointer in names:
        if (base / pointer).exists():
            return (base / pointer).read_text(encoding="utf-8").strip()
    return None


def trained_versions(name: str = NAME) -> list[str]:
    """Every version of a model saved in the current group's registry."""
    base = root(name)
    if not base.exists():
        return []
    return sorted(d.name for d in base.iterdir() if (d / "evaluation.json").exists())


def _resolve(name: str, competition: str | None) -> tuple[Path, str] | None:
    """The version serving ``competition`` and the registry holding it."""
    base = root(name)
    version = _read(base, _pointer_names(competition, formats.default_pointer()))
    if version is not None:
        return base, version
    if not _falls_back(name):
        return None
    legacy = formats.legacy_root() / name
    version = _read(legacy, _pointer_names(competition, None))
    return None if version is None else (legacy, version)


def _falls_back(name: str) -> bool:
    """Whether scoring may borrow the pooled T20 version (see the module docstring)."""
    if not formats.serving() or formats.folder() is None or model_format() != MODEL_FORMAT:
        return False
    return name != SIMULATOR or not trained_versions(name)


def current_version(name: str = NAME, competition: str | None = None) -> str | None:
    """The version serving ``competition`` (its own pointer, else the group's)."""
    found = _resolve(name, competition)
    return None if found is None else found[1]


def fallback_version(name: str = NAME, competition: str | None = None) -> str | None:
    """The pooled T20 version serving ``competition`` because its group has none yet."""
    found = _resolve(name, competition)
    if found is None or found[0] == root(name):
        return None
    return found[1]


def current_dir(name: str = NAME, competition: str | None = None) -> Path | None:
    """The folder of the version serving ``competition``."""
    found = _resolve(name, competition)
    return None if found is None else found[0] / found[1]


def _current_dir(name: str, competition: str | None, missing: str) -> Path:
    found = current_dir(name, competition)
    if found is None:
        raise FileNotFoundError(missing)
    return found


def load_current(name: str = NAME, competition: str | None = None) -> WinProbabilityModel:
    return WinProbabilityModel.load(
        _current_dir(name, competition, f"no current {name} model; run `criciq-ml train`")
    )


def load_current_projection(competition: str | None = None) -> ScoreProjectionModel:
    return ScoreProjectionModel.load(
        _current_dir(
            PROJECTION, competition, "no current score projection model; run `criciq-ml train`"
        )
    )


def load_current_ball_outcome(competition: str | None = None) -> BallOutcomeModel:
    return BallOutcomeModel.load(
        _current_dir(
            BALL_OUTCOME, competition, "no current ball-outcome model; run `criciq-ml train`"
        )
    )


def load_current_ratings() -> RatingsModel:
    return RatingsModel.load(
        _current_dir(RATINGS, None, "no current ratings; run `criciq-ml train ratings`")
    )


def load_current_simulator(competition: str | None = None) -> SimulatorSettings:
    folder = _current_dir(
        SIMULATOR, competition, "no current simulator; run `criciq-ml train simulator`"
    )
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    return SimulatorSettings(manifest)


def load_current_test_win_probability(
    competition: str | None = None,
) -> TestWinProbabilityModel:
    """The Test group's win probability model (three outcomes)."""
    return TestWinProbabilityModel.load(
        _current_dir(NAME, competition, f"no current Test {NAME} model; run `criciq-ml train`")
    )


def load_current_test_projection(competition: str | None = None) -> TestProjectionModel:
    """The Test group's innings projection."""
    return TestProjectionModel.load(
        _current_dir(PROJECTION, competition, "no current Test projection; run `criciq-ml train`")
    )


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
    | SimulatorSettings
    | TestWinProbabilityModel
    | TestProjectionModel,
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
