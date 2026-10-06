"""Innings phase configuration (powerplay / middle / death).

Phases are loaded from ``config/phases.yaml`` so they stay configurable per
format instead of being hardcoded across features, models and UI.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from criciq_core.paths import config_dir


class Phase(BaseModel):
    key: str
    label: str
    first_over: int = Field(ge=1)
    # None: open-ended (the last phase of a format without an over limit).
    last_over: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> Phase:
        if self.last_over is not None and self.last_over < self.first_over:
            raise ValueError(f"phase {self.key!r}: last_over < first_over")
        return self

    def covers(self, over_number: int) -> bool:
        return self.first_over <= over_number and (
            self.last_over is None or over_number <= self.last_over
        )


class FormatPhases(BaseModel):
    # None: no over limit (Test cricket).
    overs: int | None = Field(default=None, ge=1)
    balls_per_over: int = Field(default=6, ge=1)
    phases: list[Phase]

    @model_validator(mode="after")
    def _covers_every_over_once(self) -> FormatPhases:
        ordered = sorted(self.phases, key=lambda p: p.first_over)
        if self.overs is None:
            open_ended = [p for p in ordered if p.last_over is None]
            if open_ended != ordered[-1:]:
                raise ValueError("an unlimited format needs exactly one, final, open phase")
            bounded = ordered[:-1]
            covered: list[int] = []
            for phase in bounded:
                assert phase.last_over is not None
                covered.extend(range(phase.first_over, phase.last_over + 1))
            if covered != list(range(1, ordered[-1].first_over)):
                raise ValueError("phases must cover every over from 1 onwards exactly once")
            return self
        covered = []
        for phase in ordered:
            if phase.last_over is None:
                raise ValueError(f"phase {phase.key!r} needs a last_over in a limited format")
            covered.extend(range(phase.first_over, phase.last_over + 1))
        if sorted(covered) != list(range(1, self.overs + 1)):
            raise ValueError("phases must cover every over from 1..overs exactly once")
        return self

    @property
    def limit(self) -> int:
        """The over limit of a limited-overs format (Tests have none)."""
        if self.overs is None:
            raise ValueError("this format has no over limit")
        return self.overs

    def phase_for_over_index(self, over_index: int) -> Phase:
        """Phase of a 0-indexed over (Cricsheet convention: over 0 is the first over)."""
        over_number = over_index + 1
        for phase in self.phases:
            if phase.covers(over_number):
                return phase
        raise ValueError(f"over index {over_index} is outside a {self.overs}-over innings")

    def sql_case(self, over_index_column: str) -> str:
        """SQL ``CASE`` expression giving the phase key of a 0-indexed over column."""
        ordered = sorted(self.phases, key=lambda p: p.first_over)
        whens = " ".join(
            f"WHEN {over_index_column} + 1 <= {p.last_over} THEN '{p.key}'"
            for p in ordered
            if p.last_over is not None
        )
        # Overs beyond the format's length (miscounted innings) belong to the last phase.
        return f"CASE {whens} ELSE '{ordered[-1].key}' END"


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

    def sql_case(self, over_index_column: str, format_column: str) -> str:
        """SQL ``CASE`` giving the phase key of a 0-indexed over in each row's own format.

        ``format_column`` holds the match format (``competitions.format``), so one query
        can phase T20, ODI and Test deliveries side by side."""
        whens = " ".join(
            f"WHEN '{name}' THEN ({phases.sql_case(over_index_column)})"
            for name, phases in sorted(self.formats.items())
        )
        return f"CASE {format_column} {whens} END"


def load_phase_config(path: Path | None = None) -> PhaseConfig:
    source = path or config_dir() / "phases.yaml"
    with source.open(encoding="utf-8") as fh:
        return PhaseConfig.model_validate(yaml.safe_load(fh))


@cache
def default_phase_config() -> PhaseConfig:
    return load_phase_config()


# The format the v1 models (win probability, projection, ball outcome, ratings,
# similar players) and the simulator are built for. Data code phases each match by
# its own format; model code uses this one until per-format models arrive.
MODEL_FORMAT = "T20"


def model_phases() -> FormatPhases:
    return default_phase_config().for_format(MODEL_FORMAT)


def check_model_format(formats: Iterable[str]) -> None:
    """Fail loudly instead of feeding another format's balls to a T20 model."""
    other = sorted(set(formats) - {MODEL_FORMAT})
    if other:
        raise ValueError(
            f"the models are {MODEL_FORMAT} models but the data holds {', '.join(other)} matches"
        )
