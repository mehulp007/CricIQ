"""Typed view of ``config/models/win_probability.yaml``."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from criciq_ml import formats
from criciq_ml.features import CANDIDATES, FEATURES, FeatureConfig


class Splits(BaseModel):
    train_through: int
    validation: list[int]
    test: list[int]
    backtest_from: int


class LightGBMConfig(BaseModel):
    base: dict[str, Any]
    grid: dict[str, list[Any]]

    def candidates(self) -> list[dict[str, Any]]:
        keys = list(self.grid)
        return [
            dict(zip(keys, values, strict=True))
            for values in itertools.product(*self.grid.values())
        ]


class Gate(BaseModel):
    max_log_loss_regression: float = Field(ge=0)


class WinProbabilityConfig(BaseModel):
    name: str
    version: str
    # The warehouse copy trained on: a competition ("IPL") or the pooled T20 copy ("T20").
    scope: str = "IPL"
    splits: Splits
    features: dict[str, float | int | bool]
    # Candidate groups (``features.CANDIDATES``) served on top of the core features,
    # per innings.
    served_extras: dict[int, list[str]] = Field(default_factory=dict)
    lightgbm: LightGBMConfig
    calibration_recent_seasons: int = Field(ge=1)
    gate: Gate

    def feature_config(self) -> FeatureConfig:
        return FeatureConfig(**self.features)  # type: ignore[arg-type]

    def served_features(self) -> dict[int, list[str]]:
        """The served features per innings: the core set plus ``served_extras``."""
        return {
            number: core
            + [f for group in self.served_extras.get(number, []) for f in CANDIDATES[group][number]]
            for number, core in FEATURES.items()
        }


def load_config(path: Path | None = None) -> WinProbabilityConfig:
    source = path or formats.config_path("win_probability")
    with source.open(encoding="utf-8") as fh:
        return WinProbabilityConfig.model_validate(yaml.safe_load(fh))
