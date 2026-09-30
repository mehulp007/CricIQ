"""Innings phase configuration (powerplay / middle / death).

Phases are loaded from ``config/phases.yaml`` so they stay configurable per
format instead of being hardcoded across features, models and UI.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from criciq_core.paths import config_dir


class Phase(BaseModel):
    key: str
    label: str
    first_over: int = Field(ge=1)
    last_over: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> Phase:
        if self.last_over < self.first_over:
            raise ValueError(f"phase {self.key!r}: last_over < first_over")
        return self


class FormatPhases(BaseModel):
    overs: int = Field(ge=1)
    balls_per_over: int = Field(default=6, ge=1)
    phases: list[Phase]

    @model_validator(mode="after")
    def _covers_every_over_once(self) -> FormatPhases:
        covered: list[int] = []
        for phase in self.phases:
            covered.extend(range(phase.first_over, phase.last_over + 1))
        if sorted(covered) != list(range(1, self.overs + 1)):
            raise ValueError("phases must cover every over from 1..overs exactly once")
        return self

    def phase_for_over_index(self, over_index: int) -> Phase:
        """Phase of a 0-indexed over (Cricsheet convention: over 0 is the first over)."""
        over_number = over_index + 1
        for phase in self.phases:
            if phase.first_over <= over_number <= phase.last_over:
                return phase
        raise ValueError(f"over index {over_index} is outside a {self.overs}-over innings")


class PhaseConfig(BaseModel):
    formats: dict[str, FormatPhases]

    def for_format(self, match_format: str) -> FormatPhases:
        try:
            return self.formats[match_format]
        except KeyError:
            known = ", ".join(sorted(self.formats))
            raise KeyError(
                f"no phase config for format {match_format!r} (known: {known})"
            ) from None


def load_phase_config(path: Path | None = None) -> PhaseConfig:
    source = path or config_dir() / "phases.yaml"
    with source.open(encoding="utf-8") as fh:
        return PhaseConfig.model_validate(yaml.safe_load(fh))


@cache
def default_phase_config() -> PhaseConfig:
    return load_phase_config()
