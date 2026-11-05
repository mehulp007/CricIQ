"""Chart Studio: a chart's spec (what to count, grouped how) and the figures it returns.

The spec names datasets, measures and groupings from a fixed catalog
(``criciq_api.repositories.studio``); the client never sends SQL.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from criciq_api.schemas.common import Coverage

DatasetKey = Literal["batting", "bowling", "phase_batting", "phase_bowling", "careers", "teams"]
DimensionKey = Literal[
    "player", "team", "season", "opponent", "ground", "position", "phase", "innings"
]
MeasureKind = Literal["count", "rate", "pct", "score", "figures", "overs", "signed", "wpa"]

_ID = r"^[A-Za-z0-9_.\-]{1,80}$"
_MEASURE = r"^[a-z][a-z0-9_]{0,31}$"
PlayerId = Annotated[str, Field(pattern=_ID)]
MeasureKey = Annotated[str, Field(pattern=_MEASURE)]


class StudioFilters(BaseModel):
    """What to count: every filter is optional, and each dataset takes some of them."""

    model_config = ConfigDict(extra="forbid")

    players: list[PlayerId] = Field(
        default_factory=list,
        max_length=6,
        description="Up to six player ids (players' datasets only).",
    )
    team: str | None = Field(default=None, pattern=_ID, description="A franchise id.")
    opponent: str | None = Field(default=None, pattern=_ID)
    venue: str | None = Field(default=None, pattern=_ID, description="A venue id.")
    season_from: int | None = Field(default=None, ge=2000, le=2100)
    season_to: int | None = Field(default=None, ge=2000, le=2100)
    position: int | None = Field(
        default=None, ge=1, le=11, description="Batting position (batting only)."
    )
    innings: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="The innings of the match (teams: 1 batting first, 2 batting second).",
    )
    phase: str | None = Field(
        default=None, pattern=r"^[a-z_]{1,32}$", description="A phase key (phase datasets)."
    )


class StudioSpec(BaseModel):
    """A chart's data: a dataset, up to six measures, a grouping and an optional split."""

    model_config = ConfigDict(extra="forbid")

    dataset: DatasetKey
    measures: list[MeasureKey] = Field(min_length=1, max_length=6)
    group_by: DimensionKey | None = Field(
        default="player", description="One row per value (none: a single overall row)."
    )
    split_by: DimensionKey | None = Field(
        default=None, description="A second grouping: one series per value (players by season)."
    )
    filters: StudioFilters = Field(default_factory=StudioFilters)
    sort: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]{0,31}$",
        description='A measure key, or "group" for the grouping\'s own order (seasons in turn).',
    )
    order: Literal["asc", "desc"] | None = None
    min_sample: int = Field(
        default=0, ge=0, le=1_000_000, description="The dataset's sample (balls or matches)."
    )
    limit: int = Field(default=15, ge=1, le=50, description="Rows (groups) to return.")
    series: int = Field(
        default=8, ge=1, le=8, description="With a split: the series to return (at most 8)."
    )


class StudioColumn(BaseModel):
    key: str
    label: str
    kind: MeasureKind
    description: str
    model: bool = Field(description='A model estimate (labelled "Model estimate").')
    descending: bool = Field(description="Ranked highest first by default.")


class StudioGroup(BaseModel):
    """One value of a grouping: a player, a season, a ground..."""

    key: str
    label: str
    color: str | None = Field(default=None, description="A team's colour.")
    player_id: str | None = None


class StudioRow(BaseModel):
    group: StudioGroup | None = Field(description="None for the overall row.")
    rank: int | None = Field(description="Its place by the sort measure (equal figures share).")
    tied: bool = False
    values: dict[str, float | None]
    display: dict[str, str] = Field(description='Each figure as written ("75*", "5/27", "42.1%").')
    sample: int


class StudioCell(BaseModel):
    """A group's figures within one series (Kohli in 2016)."""

    group: str
    split: str
    values: dict[str, float | None]
    display: dict[str, str]
    sample: int


class StudioResult(BaseModel):
    coverage: Coverage
    data_version: str
    format: Literal["T20", "ODI", "Test"]
    spec: StudioSpec = Field(description="The spec as run, with its sort and order filled in.")
    dataset_label: str
    group_label: str | None
    split_label: str | None
    sample_label: str = Field(description='What the sample counts ("balls faced").')
    columns: list[StudioColumn]
    rows: list[StudioRow] = Field(description="One per group, ranked; the series' totals.")
    series: list[StudioRow] = Field(description="With a split: each series' totals.")
    cells: list[StudioCell] = Field(description="With a split: each group within each series.")
    truncated: bool = Field(description="More groups qualified than the limit returned.")
    sql: str = Field(description="The query that computed the figures, with ? for each value.")
    params: list[str | int] = Field(description="The query's values, in order.")


class StudioDimension(BaseModel):
    key: DimensionKey
    label: str
    natural: bool = Field(description="Has an order of its own (seasons, positions, phases).")


class StudioDataset(BaseModel):
    key: DatasetKey
    label: str
    description: str
    sample_label: str
    measures: list[StudioColumn]
    dimensions: list[StudioDimension]
    filters: list[str]
    default_measures: list[str]
    needs_player: bool = Field(description="A player must be the grouping or the split.")


class StudioChoice(BaseModel):
    value: str
    label: str
    color: str | None = None


class StudioOptions(BaseModel):
    coverage: Coverage
    data_version: str
    format: Literal["T20", "ODI", "Test"]
    datasets: list[StudioDataset]
    teams: list[StudioChoice]
    grounds: list[StudioChoice]
    seasons: list[StudioChoice]
    phases: list[StudioChoice]
    max_series: int
