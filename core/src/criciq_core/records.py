"""Record qualifications (``config/records.yaml``): what a player needs to appear in the
Records hub's average and rate lists, by format."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from criciq_core.paths import config_dir


class Qualification(BaseModel):
    batting_innings: int = Field(ge=1)
    career_balls_faced: int = Field(ge=1)
    innings_balls_faced: int = Field(ge=1)
    bowling_wickets: int = Field(ge=1)
    career_balls_bowled: int = Field(ge=1)
    # None: the format has no economy-in-an-innings list.
    innings_balls_bowled: int | None = Field(default=None, ge=1)


# Everyone qualifies (a small dataset).
EVERYONE = Qualification(
    batting_innings=1,
    career_balls_faced=1,
    innings_balls_faced=1,
    bowling_wickets=1,
    career_balls_bowled=1,
    innings_balls_bowled=1,
)


class RecordsConfig(BaseModel):
    small_data_matches: int = Field(ge=0)
    formats: dict[str, Qualification]

    def qualification(self, match_format: str, matches: int) -> Qualification:
        """The format's qualification; everyone's when the competition has few matches."""
        found = self.formats[match_format]
        if matches >= self.small_data_matches:
            return found
        return EVERYONE.model_copy(
            update={"innings_balls_bowled": 1 if found.innings_balls_bowled else None}
        )


def load_records_config(path: Path | None = None) -> RecordsConfig:
    source = path or config_dir() / "records.yaml"
    with source.open(encoding="utf-8") as fh:
        return RecordsConfig.model_validate(yaml.safe_load(fh))


@cache
def default_records_config() -> RecordsConfig:
    return load_records_config()
