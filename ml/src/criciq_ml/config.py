"""Typed view of ``config/models/win_probability.yaml``."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from criciq_core.paths import config_dir
from criciq_ml.features import FeatureConfig


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
    splits: Splits
    features: dict[str, float | int]
    lightgbm: LightGBMConfig
    calibration_recent_seasons: int = Field(ge=1)
    gate: Gate

    def feature_config(self) -> FeatureConfig:
        return FeatureConfig(**self.features)  # type: ignore[arg-type]


def load_config(path: Path | None = None) -> WinProbabilityConfig:
    source = path or config_dir() / "models" / "win_probability.yaml"
    with source.open(encoding="utf-8") as fh:
        return WinProbabilityConfig.model_validate(yaml.safe_load(fh))
