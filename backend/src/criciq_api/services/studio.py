"""Chart Studio: run a chart's spec against the catalog, and the choices its pickers offer.

A spec is checked against the dataset it names (measures, groupings and filters must
belong to it and to the competition's format), compiled to one parameterised query
(``criciq_api.repositories.studio``) and run with a time limit, at most two at a time.
Results are cached per database, so a new data version starts afresh.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any

from criciq_api.db import Database, QueryTimeoutError, Row
from criciq_api.repositories import common
from criciq_api.repositories import studio as repo
from criciq_api.schemas.common import Coverage
from criciq_api.schemas.studio import (
    StudioCell,
    StudioChoice,
    StudioColumn,
    StudioDataset,
    StudioDimension,
    StudioGroup,
    StudioOptions,
    StudioResult,
    StudioRow,
    StudioSpec,
)
from criciq_core import stats
from criciq_core.phases import default_phase_config

TIMEOUT_SECONDS = 10.0
DASH = chr(0x2014)  # an em dash: no figure
ORDINALS = {1: "st", 2: "nd", 3: "rd"}
_QUERIES = threading.BoundedSemaphore(2)

_FILTER_NAMES = {
    "players": "players",
    "team": "team",
    "opponent": "opponent",
    "venue": "venue",
    "season_from": "season",
    "season_to": "season",
    "position": "position",
    "innings": "innings",
    "phase": "phase",
}


class StudioDataMissingError(RuntimeError):
    pass


class InvalidSpecError(ValueError):
    pass


class StudioTimeoutError(RuntimeError):
    pass


def _has_wpa(db: Database) -> bool:
    return db.has_table("player_wpa")


def _phases(db: Database) -> list[tuple[str, str]]:
    config = default_phase_config().for_format(db.match_format)
    return [(p.key, p.label) for p in config.phases]


def _column(m: repo.Measure) -> StudioColumn:
    return StudioColumn(
        key=m.key,
        label=m.label,
        kind=m.kind,
        description=m.description,
        model=m.model,
        descending=m.descending,
    )


def _check(
    db: Database, spec: StudioSpec
) -> tuple[repo.Dataset, list[repo.Measure], repo.Measure | None, bool, StudioSpec]:
    """The dataset, measures and sort a spec names, or InvalidSpecError saying what is wrong."""
    dataset = repo.DATASETS[spec.dataset]
    if not all(db.has_table(t) for t in repo.TABLES[spec.dataset]):
        raise StudioDataMissingError(f"the {dataset.label.lower()} tables are missing")
    available = {m.key: m for m in dataset.available(db.match_format, _has_wpa(db))}
    if len(set(spec.measures)) != len(spec.measures):
        raise InvalidSpecError("a measure is listed twice")
    measures: list[repo.Measure] = []
    for key in spec.measures:
        if key not in available:
            raise InvalidSpecError(f"{dataset.label} has no measure {key!r} here")
        measures.append(available[key])

    for dimension in (spec.group_by, spec.split_by):
        if dimension is not None and dimension not in dataset.dimensions:
            raise InvalidSpecError(f"{dataset.label} can't be grouped by {dimension}")
    if spec.split_by is not None:
        if spec.group_by is None:
            raise InvalidSpecError("a split needs a grouping")
        if spec.split_by == spec.group_by:
            raise InvalidSpecError("the split must differ from the grouping")
    if dataset.needs_player and "player" not in (spec.group_by, spec.split_by):
        raise InvalidSpecError(f"{dataset.label} are grouped by player")

    f = spec.filters
    for name, value in f.model_dump().items():
        if value not in (None, []) and _FILTER_NAMES[name] not in dataset.filters:
            raise InvalidSpecError(f"{dataset.label} can't be filtered by {_FILTER_NAMES[name]}")
    if f.season_from is not None and f.season_to is not None and f.season_from > f.season_to:
        raise InvalidSpecError("the first season is after the last")
    if f.phase is not None and f.phase not in {k for k, _ in _phases(db)}:
        raise InvalidSpecError(f"no phase {f.phase!r} in {db.match_format} cricket")
    if f.innings is not None and spec.dataset == "teams" and f.innings > 2:
        raise InvalidSpecError("a side bats first (1) or second (2)")

    group = repo.DIMENSIONS[spec.group_by] if spec.group_by else None
    sort_key = spec.sort
    if sort_key is None:
        sort_key = "group" if group is not None and group.natural else measures[0].key
    if sort_key == "group":
        if group is not None and not group.natural:
            raise InvalidSpecError(f"rows grouped by {group.key} are sorted by a measure")
        sort = None
        descending = spec.order == "desc"
    else:
        found = next((m for m in measures if m.key == sort_key), None)
        if found is None:
            raise InvalidSpecError("sort by one of the chosen measures")
        sort = found
        descending = found.descending if spec.order is None else spec.order == "desc"
    normal = spec.model_copy(update={"sort": sort_key, "order": "desc" if descending else "asc"})
    return dataset, measures, sort, descending, normal


# --------------------------------------------------------------------------- figures


def _figure(kind: str, raw: Any) -> tuple[float | None, str]:
    """A measure's value for a chart and its figure as written."""
    if raw is None:
        return None, DASH
    if kind == "score":
        runs, not_out = divmod(int(raw), 2)
        return float(runs), f"{runs:,}{'*' if not_out else ''}"
    if kind == "figures":
        wickets, rest = divmod(int(raw), 1000)
        return float(wickets), f"{wickets}/{999 - rest}"
    if kind == "overs":
        overs, balls = divmod(int(raw), 6)
        return round(int(raw) / 6, 2), f"{overs:,}.{balls}" if balls else f"{overs:,}"
    value = float(raw) + 0.0  # no "-0.00"
    if kind == "count":
        return value, f"{int(raw):,}"
    if kind == "pct":
        return value, f"{value:.1f}%"
    if kind == "signed":
        return value, f"{value:+,.1f}"
    if kind == "wpa":
        return value, f"{value:+.2f}"
    return value, f"{value:,.2f}"


def _figures(
    row: Row, measures: list[repo.Measure]
) -> tuple[dict[str, float | None], dict[str, str]]:
    values: dict[str, float | None] = {}
    display: dict[str, str] = {}
    for m in measures:
        values[m.key], display[m.key] = _figure(m.kind, row[f"m_{m.key}"])
    return values, display


def _ranks(rows: list[Row], sort: repo.Measure | None) -> list[tuple[int | None, bool]]:
    if sort is None:
        return [(None, False)] * len(rows)
    return list(stats.ranks(rows, lambda r: r[f"m_{sort.key}"]))


# --------------------------------------------------------------------------- labels


class _Labels:
    """Names for grouping values, looked up once per result."""

    def __init__(self, db: Database, dataset: repo.Dataset, keys: dict[str, set[Any]]) -> None:
        self.db = db
        self.dataset = dataset
        self.players: dict[str, str] = {}
        self.teams: dict[str, tuple[str, str]] = {}
        self.grounds: dict[str, str] = {}
        self.seasons: dict[int, str] = {}
        self.phases = dict(_phases(db))
        players = sorted(keys.get("player", set()))
        if players:
            self.players = {
                r["player_id"]: r["name"]
                for r in db.rows(
                    f"""SELECT player_id, coalesce(full_name, name) AS name FROM players
                        WHERE player_id IN ({", ".join("?" for _ in players)})""",
                    players,
                )
            }
        if keys.get("team") or keys.get("opponent"):
            self.teams = {
                r["franchise_id"]: (r["name"], r["primary_color"])
                for r in db.rows("SELECT franchise_id, name, primary_color FROM franchises")
            }
        if keys.get("ground"):
            self.grounds = {
                r["venue_id"]: r["name"] for r in db.rows("SELECT venue_id, name FROM venues")
            }
        if keys.get("season"):
            self.seasons = _season_labels(db)

    def group(self, dimension: str, key: Any) -> StudioGroup:
        text = str(key)
        if dimension == "player":
            return StudioGroup(key=text, label=self.players.get(text, text), player_id=text)
        if dimension in ("team", "opponent"):
            name, color = self.teams.get(text, (text, None))
            return StudioGroup(key=text, label=name, color=color)
        if dimension == "ground":
            return StudioGroup(key=text, label=self.grounds.get(text, text))
        if dimension == "season":
            return StudioGroup(key=text, label=self.seasons.get(int(key), text))
        if dimension == "position":
            return StudioGroup(key=text, label=f"No. {key}")
        if dimension == "phase":
            return StudioGroup(key=text, label=self.phases.get(text, text))
        if self.dataset.key == "teams":
            return StudioGroup(key=text, label="Batting first" if key == 1 else "Batting second")
        return StudioGroup(key=text, label=f"{_ordinal(int(key))} innings")


def _ordinal(n: int) -> str:
    return f"{n}{ORDINALS.get(n, 'th')}"


def _season_labels(db: Database) -> dict[int, str]:
    return {
        r["year"]: r["label"]
        for r in db.rows(
            "SELECT year, CASE WHEN ? THEN cricsheet_label ELSE year::VARCHAR END AS label "
            "FROM seasons",
            [db.season_spans_new_year],
        )
    }


def _shown_params(params: list[Any]) -> list[str | int]:
    shown: list[str | int] = []
    for p in params:
        if isinstance(p, bool):
            shown.append(str(p).lower())
        elif isinstance(p, int | str):
            shown.append(p)
        else:
            shown.append(str(p))
    return shown


# --------------------------------------------------------------------------- run


def run_spec(db: Database, spec: StudioSpec) -> StudioResult:
    dataset, measures, sort, descending, normal = _check(db, spec)
    key = "studio:" + hashlib.sha1(normal.model_dump_json().encode()).hexdigest()
    if key in db.cache:
        cached: StudioResult = db.cache[key]
        return cached

    phase_keys = [k for k, _ in _phases(db)]
    query = repo.compile_query(
        dataset,
        normal,
        measures,
        sort,
        descending,
        has_wpa=_has_wpa(db),
        phase_keys=phase_keys,
    )
    with _QUERIES:
        try:
            found = db.rows(query.sql, query.params, timeout=TIMEOUT_SECONDS)
        except QueryTimeoutError as error:
            raise StudioTimeoutError("this chart took too long; narrow it down") from error

    group, split = normal.group_by, normal.split_by
    if split is None:
        groups, series_rows, cell_rows = found, [], []
    else:
        groups = [r for r in found if r["any_split"] == 1]
        series_rows = [r for r in found if r["any_group"] == 1]
        cell_rows = [r for r in found if r["any_group"] == 0 and r["any_split"] == 0]
        groups = _sorted(groups, "group_key", sort, descending, group, phase_keys)
        series_rows = _sorted(
            series_rows,
            "split_key",
            None if repo.DIMENSIONS[split].natural else (sort or measures[0]),
            descending if sort is not None else measures[0].descending,
            split,
            phase_keys,
        )
    truncated = group is not None and len(groups) > normal.limit
    groups = groups[: normal.limit]
    kept = {r["group_key"] for r in groups} if group is not None else set()
    cell_rows = [r for r in cell_rows if r["group_key"] in kept]

    keys: dict[str, set[Any]] = {}
    if group is not None:
        keys.setdefault(group, set()).update(r["group_key"] for r in groups)
    if split is not None:
        keys.setdefault(split, set()).update(r["split_key"] for r in series_rows)
    labels = _Labels(db, dataset, keys)

    def row(r: Row, dimension: str | None, column: str, rank: tuple[int | None, bool]) -> StudioRow:
        values, display = _figures(r, measures)
        return StudioRow(
            group=None if dimension is None else labels.group(dimension, r[column]),
            rank=rank[0],
            tied=rank[1],
            values=values,
            display=display,
            sample=int(r["sample"] or 0),
        )

    rows = [
        row(r, group, "group_key", rank)
        for r, rank in zip(groups, _ranks(groups, sort if group else None), strict=True)
    ]
    series = [row(r, split, "split_key", (None, False)) for r in series_rows]
    cells = []
    for r in cell_rows:
        values, display = _figures(r, measures)
        cells.append(
            StudioCell(
                group=str(r["group_key"]),
                split=str(r["split_key"]),
                values=values,
                display=display,
                sample=int(r["sample"] or 0),
            )
        )

    result = StudioResult(
        coverage=Coverage(**common.coverage(db)),
        data_version=db.data_version,
        format=db.match_format,  # type: ignore[arg-type]
        spec=normal,
        dataset_label=dataset.label,
        group_label=repo.DIMENSIONS[group].label if group else None,
        split_label=repo.DIMENSIONS[split].label if split else None,
        sample_label=dataset.sample_label,
        columns=[_column(m) for m in measures],
        rows=rows,
        series=series,
        cells=cells,
        truncated=truncated,
        sql=query.sql,
        params=_shown_params(query.params),
    )
    db.cache[key] = result
    return result


def _sorted(
    rows: list[Row],
    column: str,
    sort: repo.Measure | None,
    descending: bool,
    dimension: str | None,
    phase_keys: list[str],
) -> list[Row]:
    """Rows of a grouping set in the order the query ranked them (GROUPING SETS rows come
    back unordered)."""
    if sort is None:
        if dimension == "phase":
            order = {k: i for i, k in enumerate(phase_keys)}
            return sorted(rows, key=lambda r: order.get(r[column], len(order)), reverse=descending)
        return sorted(rows, key=lambda r: r[column], reverse=descending)
    key = f"m_{sort.key}"
    present = [r for r in rows if r[key] is not None]
    missing = [r for r in rows if r[key] is None]
    present.sort(key=lambda r: str(r[column]))
    present.sort(key=lambda r: r[key], reverse=descending)
    return present + sorted(missing, key=lambda r: str(r[column]))


# --------------------------------------------------------------------------- options


def get_options(db: Database) -> StudioOptions:
    key = "studio:options"
    if key in db.cache:
        cached: StudioOptions = db.cache[key]
        return cached
    has_wpa = _has_wpa(db)
    datasets = [
        StudioDataset(
            key=d.key,
            label=d.label,
            description=d.description,
            sample_label=d.sample_label,
            measures=[_column(m) for m in d.available(db.match_format, has_wpa)],
            dimensions=[
                StudioDimension(
                    key=k, label=repo.DIMENSIONS[k].label, natural=repo.DIMENSIONS[k].natural
                )
                for k in d.dimensions
            ],
            filters=sorted(d.filters),
            default_measures=list(d.default_measures),
            needs_player=d.needs_player,
        )
        for d in repo.DATASETS.values()
        if all(db.has_table(t) for t in repo.TABLES[d.key])
    ]
    teams = [
        StudioChoice(value=r["franchise_id"], label=r["name"], color=r["primary_color"])
        for r in db.rows(
            """SELECT franchise_id, name, primary_color FROM franchises
               WHERE franchise_id IN (SELECT franchise_id FROM team_matches)
               ORDER BY name"""
        )
    ]
    grounds = [
        StudioChoice(value=r["venue_id"], label=f"{r['name']} ({r['matches']})")
        for r in db.rows(
            """SELECT v.venue_id, v.name, count(*)::INTEGER AS matches
               FROM matches m JOIN venues v USING (venue_id)
               GROUP BY ALL ORDER BY matches DESC, v.name"""
        )
    ]
    labels = _season_labels(db)
    seasons = [
        StudioChoice(value=str(r["season"]), label=labels.get(r["season"], str(r["season"])))
        for r in db.rows("SELECT DISTINCT season FROM team_matches ORDER BY season")
    ]
    found = StudioOptions(
        coverage=Coverage(**common.coverage(db)),
        data_version=db.data_version,
        format=db.match_format,  # type: ignore[arg-type]
        datasets=datasets,
        teams=teams,
        grounds=grounds,
        seasons=seasons,
        phases=[StudioChoice(value=k, label=label) for k, label in _phases(db)],
        max_series=repo.MAX_SERIES,
    )
    db.cache[key] = found
    return found
