"""Fit and evaluate CricIQ Ratings and the similar-players method.

Ratings are not a trained model: each component is a player's record against
par (see ``criciq_core.ratings``). What has to be estimated is how much to
trust a record of a given size. For every component:

1. ``k``, the shrinkage constant: a record of ``n`` balls (or innings) is
   blended with ``k`` units of the qualified players' average. ``k`` is tuned
   so a player's shrunk record in one season best predicts their next season:
   a persistent skill carries over, luck does not.
2. ``sigma2``, the noise per unit of exposure, pooled from how much a
   player's innings vary within a season. It gives each rating a 90% interval.

The protocol is tested like the models: ``k`` is re-tuned on season pairs
before ``test_from`` and used to predict each later season from the one
before, against par (ignore the record) and the raw record (trust it fully).
The evaluation also reports how strongly ratings persist from one season to
the next and between odd and even seasons, and labels each component's
stability.

The similar-players method is tested by retrieval: from a player's style in
one season, how often is the nearest profile among next season's players the
same player?
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel

from criciq_core import paths, style
from criciq_core.ratings import (
    MIN_BALLS,
    Component,
    Role,
    role_balls_key,
    role_components,
    units_sql,
)

Log = Callable[[str], None]
ROLES: tuple[Role, ...] = ("batting", "bowling")


def _quiet(_: str) -> None:
    pass


# --------------------------------------------------------------------------- config


class Splits(BaseModel):
    test_from: int


class KGrid(BaseModel):
    low: float
    high: float
    points: int

    def values(self) -> np.ndarray[Any, np.dtype[np.float64]]:
        return np.geomspace(self.low, self.high, self.points)


class RatingsConfig(BaseModel):
    name: str
    version: str
    splits: Splits
    k_grid: KGrid
    stability: dict[str, float]  # label -> minimum year-to-year r, highest first
    season_factor: float
    style_min_balls: int


def load_ratings_config(path: Path | None = None) -> RatingsConfig:
    source = path or paths.config_dir() / "models" / "ratings.yaml"
    return RatingsConfig.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- the artifact


@dataclass
class RatingsModel:
    """The fitted constants: ``components[role][key] = {k, sigma2, stability}``."""

    manifest: dict[str, Any]

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    def save(self, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @classmethod
    def load(cls, target: Path) -> RatingsModel:
        return cls(json.loads((target / "manifest.json").read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- estimation


def load_units(con: duckdb.DuckDBPyConnection, role: Role) -> pd.DataFrame:
    """Per-innings evidence for every component of a role."""
    frame: pd.DataFrame = con.execute(units_sql(role, _tables(con))).df()
    return frame


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {name for (name,) in con.execute("SHOW TABLES").fetchall()}


def noise_variance(units: pd.DataFrame) -> float:
    """Variance of the evidence per unit of exposure, pooled within player-seasons.

    Innings are the units, so balls within an innings may be correlated. For
    innings j of a player-season with rate v and exposure N,
    E[(e_j - v n_j)^2] = sigma2 * n_j * (1 - n_j / N).
    With no player-season of two innings or more (a tiny dataset), it falls back
    to the variance around the overall rate, which overstates the noise.
    """
    frame = units[units["n"] > 0].copy()
    groups = frame.groupby(["player_id", "season"])
    frame["E"] = groups["e"].transform("sum")
    frame["N"] = groups["n"].transform("sum")
    residual = (frame["e"] - frame["E"] / frame["N"] * frame["n"]) ** 2
    weight = (frame["n"] * (1 - frame["n"] / frame["N"])).sum()
    if weight > 0:
        return float(residual.sum() / weight)
    rate = frame["e"].sum() / frame["n"].sum()
    return float(((frame["e"] - rate * frame["n"]) ** 2).sum() / frame["n"].sum())


def season_sums(units: pd.DataFrame, component: Component, factor: float) -> pd.DataFrame:
    """One row per player-season: evidence, exposure, balls in the role, and whether qualified.

    A single season is a short window, so its thresholds are ``factor`` times
    the window thresholds. ``mean`` is the qualified players' average.
    """
    sums = units.groupby(["component", "player_id", "season"], as_index=False).agg(
        e=("e", "sum"), n=("n", "sum")
    )
    mine = sums[(sums["component"] == component.key) & (sums["n"] > 0)].drop(columns="component")
    balls = sums[sums["component"] == role_balls_key(component.role)][
        ["player_id", "season", "n"]
    ].rename(columns={"n": "role_balls"})
    mine = mine.merge(balls, on=["player_id", "season"], how="left").fillna({"role_balls": 0})
    mine["qualified"] = (mine["role_balls"] >= factor * MIN_BALLS) & (
        mine["n"] >= factor * component.qualify
    )
    qualified = mine[mine["qualified"]]
    totals = qualified.groupby("season")[["e", "n"]].sum()
    mine["mean"] = mine["season"].map(totals["e"] / totals["n"])
    return mine.dropna(subset=["mean"]).reset_index(drop=True)


def _pairs(sums: pd.DataFrame) -> pd.DataFrame:
    """Qualified player-seasons joined to the same player's next season (any exposure)."""
    following = sums.assign(season=sums["season"] - 1)
    pairs = sums[sums["qualified"]].merge(
        following, on=["player_id", "season"], suffixes=("", "_next")
    )
    pairs["target"] = pairs["e_next"] / pairs["n_next"] - pairs["mean_next"]
    return pairs


def _loss(pairs: pd.DataFrame, k: float) -> float:
    predicted = (pairs["e"] - pairs["mean"] * pairs["n"]) / (pairs["n"] + k)
    return float(np.average((pairs["target"] - predicted) ** 2, weights=pairs["n_next"]))


def tune_k(pairs: pd.DataFrame, grid: np.ndarray[Any, np.dtype[np.float64]]) -> float:
    """The k whose shrunk season record best predicts the same player's next season.

    Records are compared with the qualified players' average in their own
    season, so a rising scoring environment does not count as skill. Each
    pair is weighted by the exposure behind the season being predicted.
    """
    if pairs.empty:
        return float(grid[-1])
    return float(grid[int(np.argmin([_loss(pairs, k) for k in grid]))])


# --------------------------------------------------------------------------- evaluation


def year_to_year(sums: pd.DataFrame, k: float) -> dict[str, Any]:
    """Correlation of a player's ratings in consecutive seasons (both qualified)."""
    rated = sums[sums["qualified"]].copy()
    rated["value"] = (rated["e"] + k * rated["mean"]) / (rated["n"] + k)
    rated["rating"] = rated.groupby("season")["value"].rank(pct=True) * 100
    following = rated.assign(season=rated["season"] - 1)
    pairs = rated.merge(following, on=["player_id", "season"], suffixes=("", "_next"))
    if len(pairs) < 10:
        return {"r": None, "pairs": len(pairs)}
    r = float(np.corrcoef(pairs["rating"], pairs["rating_next"])[0, 1])
    return {"r": round(r, 3), "pairs": len(pairs)}


def split_half(units: pd.DataFrame, component: Component) -> dict[str, Any]:
    """Correlation between a player's raw records in odd and in even seasons."""
    halves = units.assign(season=units["season"] % 2)
    sums = season_sums(halves, component, 1.0)
    sums = sums[sums["qualified"]]
    values = sums.assign(v=sums["e"] / sums["n"]).pivot(
        index="player_id", columns="season", values="v"
    )
    values = values.dropna()
    if len(values) < 10:
        return {"r": None, "players": len(values)}
    r = float(np.corrcoef(values[0], values[1])[0, 1])
    return {"r": round(r, 3), "players": len(values)}


def next_season(pairs: pd.DataFrame, k: float, scale: float) -> dict[str, Any]:
    """Predict each next season with par, the raw record, or the shrunk record."""
    if pairs.empty:
        return {"pairs": 0}
    target, weight = pairs["target"], pairs["n_next"]

    def mse(predicted: pd.Series | float) -> float:
        return float(np.average((target - predicted) ** 2, weights=weight)) * scale**2

    par = mse(0.0)
    raw = mse(pairs["e"] / pairs["n"] - pairs["mean"])
    best = mse((pairs["e"] - pairs["mean"] * pairs["n"]) / (pairs["n"] + k))
    return {
        "pairs": len(pairs),
        "mse": {"par": round(par, 6), "raw": round(raw, 6), "shrunk": round(best, 6)},
        "skill_vs_par": round(1 - best / par, 4),
        "skill_vs_raw": round(1 - best / raw, 4),
    }


def _stability(r: float | None, levels: dict[str, float]) -> str:
    for label, minimum in sorted(levels.items(), key=lambda lv: -lv[1]):
        if r is not None and r >= minimum:
            return label
    return "low"


def _weight_at(k: float, exposure: str) -> dict[str, float]:
    sizes = [100, 300, 1000, 3000] if exposure == "balls" else [10, 30, 100]
    return {str(n): round(n / (n + k), 3) for n in sizes}


def fit_component(
    units: pd.DataFrame, component: Component, cfg: RatingsConfig, log: Log = _quiet
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Served constants and the evaluation for one component."""
    mine = units[units["component"].isin({component.key, role_balls_key(component.role)})]
    sums = season_sums(mine, component, cfg.season_factor)
    pairs = _pairs(sums)
    grid = cfg.k_grid.values()
    k = tune_k(pairs, grid)
    k_test = tune_k(pairs[pairs["season"] + 1 < cfg.splits.test_from], grid)
    sigma2 = noise_variance(units[units["component"] == component.key])
    yoy = year_to_year(sums, k)
    stability = _stability(yoy["r"], cfg.stability)
    validation = next_season(
        pairs[pairs["season"] + 1 >= cfg.splits.test_from], k_test, component.scale
    )
    log(
        f"  {component.role:7s} {component.key:11s} k={k:7.0f} {component.exposure:7s} "
        f"year-to-year r={yoy['r']} next-season skill vs par "
        f"{validation.get('skill_vs_par')} vs raw {validation.get('skill_vs_raw')}"
    )
    served = {"k": round(k, 2), "sigma2": round(sigma2, 8), "stability": stability}
    evaluation = {
        "key": component.key,
        "role": component.role,
        "label": component.label,
        "description": component.description,
        "unit": component.unit,
        "exposure": component.exposure,
        "k": round(k, 2),
        "k_validation": round(k_test, 2),
        "sigma2": round(sigma2, 8),
        "weight_at": _weight_at(k, component.exposure),
        "year_to_year": yoy,
        "split_half": split_half(mine, component),
        "next_season": validation,
        "stability": stability,
    }
    return served, evaluation


# --------------------------------------------------------------------------- similar players


def style_retrieval(con: duckdb.DuckDBPyConnection, role: Role, min_balls: int) -> dict[str, Any]:
    """From a player's profile in one season, rank next season's profiles by similarity.

    Each season is standardised within its own players (at least ``min_balls``),
    exactly as the API does for a window.
    """
    keys = [f.key for f in style.features(role)]
    seasons = [int(s) for (s,) in con.execute("SELECT year FROM seasons ORDER BY year").fetchall()]
    sql = style.profile_sql(role)
    profiles: dict[int, dict[str, list[float]]] = {}
    for season in seasons:
        cursor = con.execute(sql, style.window_params(season, season))
        columns = [d[0] for d in cursor.description or []]
        rows = [dict(zip(columns, r, strict=True)) for r in cursor.fetchall()]
        rows = [r for r in rows if r["balls"] >= min_balls]
        if len(rows) < 10:
            continue
        scaler = style.Scaler.fit(rows, keys)
        profiles[season] = {r["player_id"]: scaler.transform(r) for r in rows}
    ranks: list[int] = []
    candidates: list[int] = []
    for season, current in profiles.items():
        following = profiles.get(season + 1)
        if not following:
            continue
        ids = list(following)
        for player_id, z in current.items():
            if player_id not in following:
                continue
            sims = [style.cosine(z, following[other]) for other in ids]
            mine = sims[ids.index(player_id)]
            ranks.append(1 + sum(1 for s in sims if s > mine))
            candidates.append(len(ids))
    features = [{"key": f.key, "label": f.label} for f in style.features(role)]
    if not ranks:
        return {"players": 0, "features": features}
    r = np.array(ranks)
    c = np.array(candidates)
    return {
        "players": len(r),
        "candidates_median": int(np.median(c)),
        "top1": round(float((r == 1).mean()), 3),
        "top5": round(float((r <= 5).mean()), 3),
        "chance_top1": round(float((1 / c).mean()), 3),
        "chance_top5": round(float((np.minimum(5, c) / c).mean()), 3),
        "median_rank": float(np.median(r)),
        "features": features,
    }


# --------------------------------------------------------------------------- protocol


def train_ratings(
    serving: Path, cfg: RatingsConfig, *, data_version: str, log: Log = _quiet
) -> tuple[RatingsModel, dict[str, Any]]:
    con = duckdb.connect(str(serving), read_only=True)
    try:
        components: dict[str, dict[str, Any]] = {}
        evaluations: list[dict[str, Any]] = []
        similarity: dict[str, Any] = {}
        first, last = con.execute("SELECT min(year), max(year) FROM seasons").fetchone()  # type: ignore[misc]
        for role in ROLES:
            units = load_units(con, role)
            components[role] = {}
            for component in role_components(role, _tables(con)):
                served, evaluation = fit_component(units, component, cfg, log)
                components[role][component.key] = served
                evaluations.append(evaluation)
            retrieval = style_retrieval(con, role, cfg.style_min_balls)
            similarity[role] = retrieval
            if retrieval["players"]:
                log(
                    f"  {role} similarity: own profile top-1 {retrieval['top1']:.0%} "
                    f"(chance {retrieval['chance_top1']:.0%}), top-5 {retrieval['top5']:.0%}"
                )
    finally:
        con.close()
    manifest = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "trained_on": {"seasons": [int(first), int(last)]},
        "components": components,
    }
    evaluation = {
        "version": cfg.version,
        "data_version": data_version,
        "splits": cfg.splits.model_dump(),
        "stability": cfg.stability,
        "season_factor": cfg.season_factor,
        "style_min_balls": cfg.style_min_balls,
        "min_balls": MIN_BALLS,
        "components": evaluations,
        "similarity": similarity,
    }
    return RatingsModel(manifest), evaluation


def gate(evaluation: dict[str, Any]) -> list[str]:
    """Reasons a version must not be promoted: shrunk records must beat raw ones.

    Beating par is reported, not required: a component with little
    persistent signal is labelled as such instead of being hidden.
    """
    problems = []
    for c in evaluation["components"]:
        mse = c["next_season"].get("mse")
        if mse is not None and mse["shrunk"] >= mse["raw"]:
            problems.append(
                f"{c['role']} {c['key']}: the shrunk record does not predict the next season "
                "better than the raw record"
            )
    return problems
