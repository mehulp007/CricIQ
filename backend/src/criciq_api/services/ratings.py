"""CricIQ Ratings and similar players for any season window.

Both need the whole population of a window (every player's evidence, or every
player's style profile), so each window is computed once and kept in a small
cache: the database is read-only, so a window's answer never changes.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from criciq_api.db import Database
from criciq_api.repositories import matches as matches_repo
from criciq_api.repositories import players as players_repo
from criciq_api.schemas.players import (
    Rating,
    RatingGroup,
    SeasonWindow,
    SimilarPlayer,
    StyleGroup,
    TeamTag,
)
from criciq_core import style
from criciq_core.ratings import (
    MIN_BALLS,
    MIN_RATED_BALLS,
    Component,
    Role,
    role_balls_key,
    role_components,
    window_sums_sql,
)

Z90 = 1.6449
WINDOWS_CACHED = 48
SIMILAR = 5


@dataclass(frozen=True)
class Constants:
    k: float
    sigma2: float
    stability: str


@dataclass(frozen=True)
class Estimate:
    e: float
    n: float
    shrunk: float
    se: float


@dataclass(frozen=True)
class ComponentPopulation:
    component: Component
    constants: Constants
    mean: float  # qualified players' average (the shrinkage target)
    estimates: dict[str, Estimate]
    qualified: frozenset[str]
    reference: list[float]  # qualified players' shrunk estimates, sorted


@dataclass(frozen=True)
class RolePopulation:
    role_balls: dict[str, float]
    qualified: int
    components: list[ComponentPopulation]


def _cached(db: Database, key: tuple[Any, ...], build: Any) -> Any:
    cache: OrderedDict[tuple[Any, ...], Any] = db.cache.setdefault("windows", OrderedDict())
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    value = build()
    cache[key] = value
    if len(cache) > WINDOWS_CACHED:
        cache.popitem(last=False)
    return value


# --------------------------------------------------------------------------- ratings


def constants(db: Database) -> dict[tuple[str, str], Constants] | None:
    """Shrinkage per (role, component), or None if the data was never scored."""
    if "rating_constants" not in db.cache:
        row = matches_repo.get_model(db, "ratings")
        db.cache["rating_constants"] = (
            None
            if row is None
            else {
                (role, key): Constants(
                    k=float(c["k"]), sigma2=float(c["sigma2"]), stability=str(c["stability"])
                )
                for role, items in row["components"].items()
                for key, c in items.items()
            }
        )
    found: dict[tuple[str, str], Constants] | None = db.cache["rating_constants"]
    return found


def _population(db: Database, role: Role, first: int, last: int) -> RolePopulation | None:
    fitted = constants(db)
    if fitted is None:
        return None
    sums: dict[str, dict[str, tuple[float, float]]] = {}
    for r in db.rows(window_sums_sql(role, db.tables), [first, last]):
        sums.setdefault(r["component"], {})[r["player_id"]] = (float(r["e"]), float(r["n"]))
    role_balls = {pid: n for pid, (_, n) in sums.get(role_balls_key(role), {}).items()}
    populations = []
    for component in role_components(role, db.tables):
        fit = fitted.get((role, component.key))
        evidence = sums.get(component.key, {})
        if fit is None or not evidence:
            continue
        qualified = frozenset(
            pid
            for pid, (_, n) in evidence.items()
            if n >= component.qualify and role_balls.get(pid, 0) >= MIN_BALLS
        )
        pool = qualified or frozenset(evidence)
        total_n = sum(evidence[p][1] for p in pool)
        if not total_n:
            continue
        mean = sum(evidence[p][0] for p in pool) / total_n
        estimates = {
            pid: Estimate(
                e=e,
                n=n,
                shrunk=(e + fit.k * mean) / (n + fit.k),
                se=math.sqrt(fit.sigma2 / (n + fit.k)),
            )
            for pid, (e, n) in evidence.items()
            if n > 0
        }
        populations.append(
            ComponentPopulation(
                component=component,
                constants=fit,
                mean=mean,
                estimates=estimates,
                qualified=qualified,
                reference=sorted(estimates[p].shrunk for p in qualified if p in estimates),
            )
        )
    qualified_players = sum(1 for n in role_balls.values() if n >= MIN_BALLS)
    return RolePopulation(
        role_balls=role_balls, qualified=qualified_players, components=populations
    )


def population(db: Database, role: Role, window: SeasonWindow) -> RolePopulation | None:
    key = ("ratings", role, window.first, window.last)
    found: RolePopulation | None = _cached(
        db, key, lambda: _population(db, role, window.first, window.last)
    )
    return found


def percentile(value: float, reference: list[float], exclude: float | None = None) -> int | None:
    """Share of the reference below ``value`` (ties count half), leaving out one ``exclude``."""
    below = bisect_left(reference, value)
    at_or_below = bisect_right(reference, value)
    size = len(reference)
    if exclude is not None:
        size -= 1
        if exclude < value:
            below -= 1
            at_or_below -= 1
        elif exclude == value:
            at_or_below -= 1
    if size <= 0:
        return None
    return round(100 * (below + 0.5 * (at_or_below - below)) / size)


def _rating(pop: ComponentPopulation, player_id: str, rated: bool) -> Rating | None:
    c = pop.component
    est = pop.estimates.get(player_id)
    if est is None:
        return None
    mine = player_id in pop.qualified
    shown = rated and est.n >= c.show and bool(pop.reference)
    exclude = est.shrunk if mine else None

    def pct(value: float) -> int | None:
        return percentile(value, pop.reference, exclude) if shown else None

    return Rating(
        key=c.key,
        label=c.label,
        description=c.description,
        rating=pct(est.shrunk),
        low=pct(est.shrunk - Z90 * est.se),
        high=pct(est.shrunk + Z90 * est.se),
        value=round(c.scale * est.shrunk, 2),
        raw=round(c.scale * est.e / est.n, 2),
        average=round(c.scale * pop.mean, 2),
        unit=c.unit,
        exposure=round(est.n),
        exposure_unit=c.exposure,
        weight=round(est.n / (est.n + pop.constants.k), 3),
        qualified=mine,
        stability=pop.constants.stability,  # type: ignore[arg-type]
    )


def ratings(db: Database, player_id: str, role: Role, window: SeasonWindow) -> RatingGroup | None:
    pop = population(db, role, window)
    if pop is None:
        return None
    balls = pop.role_balls.get(player_id, 0)
    if not balls:
        return None
    rated = balls >= MIN_RATED_BALLS
    items = [r for p in pop.components if (r := _rating(p, player_id, rated)) is not None]
    return RatingGroup(
        qualified=balls >= MIN_BALLS,
        balls=round(balls),
        min_balls=MIN_BALLS,
        population=pop.qualified,
        items=items,
    )


# --------------------------------------------------------------------------- similar players


@dataclass(frozen=True)
class StylePopulation:
    profiles: dict[str, list[float]]  # standardised, players with a profile
    balls: dict[str, int]
    candidates: list[str]  # players who can be suggested


def _styles(db: Database, role: Role, first: int, last: int) -> StylePopulation | None:
    rows = db.rows(style.profile_sql(role), style.window_params(first, last))
    reference = style.population(rows)
    if len(reference) < 2:
        return None
    keys = [f.key for f in style.features(role)]
    scaler = style.Scaler.fit(reference, keys)
    profiled = [r for r in rows if r["balls"] >= style.MIN_PROFILE_BALLS]
    return StylePopulation(
        profiles={r["player_id"]: scaler.transform(r) for r in profiled},
        balls={r["player_id"]: int(r["balls"]) for r in profiled},
        candidates=[r["player_id"] for r in reference],
    )


def _players(db: Database) -> dict[str, dict[str, Any]]:
    if "player_names" not in db.cache:
        franchises = players_repo.franchise_tags(db)
        db.cache["player_names"] = {
            r["player_id"]: {
                "name": r["name"],
                "role": r["role"],
                "team": TeamTag(
                    franchise_id=r["latest_team_id"],
                    name=franchises[r["latest_team_id"]]["name"],
                    color=franchises[r["latest_team_id"]]["color"],
                )
                if r["latest_team_id"] in franchises
                else None,
            }
            for r in db.rows("SELECT player_id, name, role, latest_team_id FROM player_index")
        }
    names: dict[str, dict[str, Any]] = db.cache["player_names"]
    return names


def similar(db: Database, player_id: str, role: Role, window: SeasonWindow) -> StyleGroup | None:
    key = ("style", role, window.first, window.last)
    pop: StylePopulation | None = _cached(
        db, key, lambda: _styles(db, role, window.first, window.last)
    )
    if pop is None or player_id not in pop.profiles:
        return None
    mine = pop.profiles[player_id]
    names = _players(db)
    scored = sorted(
        (
            (style.cosine(mine, pop.profiles[other]), other)
            for other in pop.candidates
            if other != player_id
        ),
        reverse=True,
    )[:SIMILAR]
    return StyleGroup(
        traits=style.traits(mine, role),
        population=len(pop.candidates),
        min_balls=MIN_BALLS,
        items=[
            SimilarPlayer(
                player_id=other,
                name=names[other]["name"],
                role=names[other]["role"],
                team=names[other]["team"],
                similarity=round(score, 3),
                balls=pop.balls[other],
                shared=style.shared_traits(mine, pop.profiles[other], role),
            )
            for score, other in scored
        ],
    )
