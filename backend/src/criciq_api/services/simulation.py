"""Match simulator and what-if sandbox (criciq_core.simulation, ADR-0006).

Everything the engine needs is assembled from the serving database: the ball
model's terms (published by ``criciq-ml score``), the tuned conditions spread,
league rates for extras and run outs and the league's pattern of bowling usage
over the last three seasons, and each picked player's own recent batting
position and bowling usage. A match can be played in any season: the sides come
from that season's squads (everyone who played for the franchise that year), and
the scoring era, league rates and players' records are as of then. Results are
cached by request, and a request with no seed is seeded from its own content, so
the same question always gets the same answer.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from criciq_api.db import Database, Row
from criciq_api.repositories import matches as matches_repo
from criciq_api.repositories import matchups as matchups_repo
from criciq_api.repositories import simulation as repo
from criciq_api.schemas.players import TeamTag
from criciq_api.schemas.simulation import (
    Distribution,
    SideRequest,
    SideResult,
    SimBatter,
    SimBowler,
    SimPlayer,
    SimSeason,
    SimSeasonTeam,
    SimSquad,
    SimulationRequest,
    SimulationResult,
    SimXI,
    SquadPlayer,
    StateOutcome,
    StateRequest,
    StateResult,
    StateScore,
)
from criciq_core import simulation as sim

CACHE_SIZE = 64
HISTORY = 3
# Matches in the scoring-era window (the ball model's ENV_WINDOW).
ERA_WINDOW = 60
# Simulated chances are clipped before the log-odds shift of the what-if sandbox.
CLIP = 0.005


class SimulationUnavailableError(LookupError):
    pass


class UnknownPlayerError(LookupError):
    pass


class InvalidSideError(ValueError):
    pass


class StateNotFoundError(LookupError):
    pass


class UnknownSquadError(LookupError):
    pass


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True)
class Engine:
    model: sim.BallModel
    rates: sim.LeagueRates
    priors: dict[str, Any]
    conditions_sd: float
    ball_version: str
    version: str
    # Players' batting positions and bowling usage come from seasons up to this one.
    season: int | None = None
    # The format's innings: overs, each bowler's quota and phases (T20 or ODI).
    rules: sim.FormatRules = sim.T20


def rules(db: Database) -> sim.FormatRules:
    """The simulator's rules for the database's format."""
    return sim.rules_for(db.match_format)


def engine(db: Database) -> Engine:
    if "sim_engine" not in db.cache:
        if not repo.available(db):
            raise SimulationUnavailableError("the simulator tables are missing")
        ball = matches_repo.get_model(db, "ball_outcome")
        settings = matches_repo.get_model(db, "simulator")
        if ball is None or settings is None:
            raise SimulationUnavailableError("the simulator has not been published")
        env = float(ball["env_now"])
        era = (math.log(env) - float(ball["env_mean"])) / float(ball["env_std"])
        last = repo.latest_season(db)
        first = last - HISTORY + 1
        r = rules(db)
        db.cache["sim_engine"] = Engine(
            model=sim.BallModel(terms=matchups_repo.terms(db), era=era),
            rates=sim.league_rates(repo.league_rates(db, first, last), env, r),
            priors=sim.usage_priors(repo.usage_priors(db, first, last), r),
            conditions_sd=float(settings["conditions_sd"]),
            ball_version=str(ball["version"]),
            version=str(settings["version"]),
            rules=r,
        )
    out: Engine = db.cache["sim_engine"]
    return out


def _engine_at(db: Database, key: str, match_order: int, season: int) -> Engine:
    """The engine as of a point in history: the scoring era of the matches before
    ``match_order``, and league rates and bowling patterns from the three seasons
    up to ``season``."""
    base = engine(db)
    if key not in db.cache:
        ball = matches_repo.get_model(db, "ball_outcome")
        assert ball is not None
        env = repo.era_env(db, match_order, ERA_WINDOW) or float(ball["env_now"])
        era = (math.log(env) - float(ball["env_mean"])) / float(ball["env_std"])
        first = season - HISTORY + 1
        db.cache[key] = Engine(
            model=sim.BallModel(terms=base.model.terms, era=era),
            rates=sim.league_rates(repo.league_rates(db, first, season), env, base.rules),
            priors=sim.usage_priors(repo.usage_priors(db, first, season), base.rules),
            conditions_sd=base.conditions_sd,
            ball_version=base.ball_version,
            version=base.version,
            season=season,
            rules=base.rules,
        )
    out: Engine = db.cache[key]
    return out


def era_engine(db: Database, match_id: int) -> Engine:
    """The engine as of a historical match."""
    engine(db)
    context = repo.match_context(db, match_id)
    if context is None:
        raise StateNotFoundError(f"match {match_id} not found")
    order, season = int(context["match_order"]), int(context["season"])
    return _engine_at(db, f"sim_engine:{season}:{order}", order, season)


def season_engine(db: Database, season: int) -> Engine:
    """The engine for a match played in ``season``: the scoring era at its end."""
    current = engine(db)
    if season >= repo.latest_season(db):
        return current
    end = repo.season_end(db, season)
    if end is None:
        raise UnknownSquadError(f"no season {season}")
    return _engine_at(db, f"sim_engine:season:{season}", end + 1, season)


def _cache(db: Database) -> OrderedDict[str, Any]:
    if "sim_results" not in db.cache:
        db.cache["sim_results"] = OrderedDict()
    cache: OrderedDict[str, Any] = db.cache["sim_results"]
    return cache


def _remember(db: Database, key: str, value: Any) -> None:
    cache = _cache(db)
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > CACHE_SIZE:
        cache.popitem(last=False)


def _seed(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


@dataclass(frozen=True)
class Picked:
    candidate: sim.Candidate
    row: Row

    @property
    def name(self) -> str:
        return str(self.row["full_name"] or self.row["name"])


def _picked(db: Database, ids: list[str], upto: int | None = None) -> dict[str, Picked]:
    width = rules(db).overs
    rows = {r["player_id"]: r for r in repo.candidates(db, ids, HISTORY, upto, width)}
    missing = [pid for pid in ids if pid not in rows]
    if missing:
        raise UnknownPlayerError(missing[0])
    out = {}
    for pid, r in rows.items():
        overs = np.zeros(width)
        for item in r["overs"] or []:
            overs[int(item["over_no"])] = float(item["overs"])
        out[pid] = Picked(
            candidate=sim.Candidate(
                player=sim.Player(pid, r["batting_hand"], r["bowling_type"]),
                position=None if r["position"] is None else float(r["position"]),
                overs_by_over=overs,
            ),
            row=r,
        )
    return out


def _sim_player(p: Picked) -> SimPlayer:
    return SimPlayer(
        player_id=p.candidate.player.player_id,
        name=p.name,
        role=p.row["role"],
        batting_hand=p.row["batting_hand"],
        bowling_type=p.row["bowling_type"],
        position=None if p.candidate.position is None else round(p.candidate.position, 1),
        recent_overs=round(p.candidate.overs, 1),
    )


def _team(db: Database, franchise_id: str | None) -> TeamTag | None:
    if not franchise_id:
        return None
    row = db.row(
        "SELECT franchise_id, name, primary_color AS color FROM franchises WHERE franchise_id = ?",
        [franchise_id.upper()],
    )
    return None if row is None else TeamTag(**row)


# --------------------------------------------------------------------------- XIs


def xi_for_players(db: Database, ids: list[str], team: TeamTag | None = None) -> SimXI:
    picked = _picked(db, ids)
    candidates = [picked[pid].candidate for pid in ids]
    ordered = sim.typical_order(candidates)
    return SimXI(
        team=team,
        from_match=None,
        match_date=None,
        players=[_sim_player(picked[c.player.player_id]) for c in ordered],
        bowlers=sim.default_bowlers(candidates, rules(db)),
    )


def latest_xi(db: Database, franchise_id: str) -> SimXI:
    team = _team(db, franchise_id)
    found = repo.latest_xi(db, franchise_id.upper()) if team else None
    if team is None or found is None:
        raise UnknownPlayerError(franchise_id)
    match, ids = found
    picked = _picked(db, ids)
    return SimXI(
        team=team,
        from_match=int(match["match_id"]),
        match_date=match["match_date"],
        players=[_sim_player(picked[pid]) for pid in ids],
        bowlers=sim.default_bowlers([picked[pid].candidate for pid in ids], rules(db)),
    )


# --------------------------------------------------------------------------- seasons


def seasons(db: Database) -> list[SimSeason]:
    """Every season, newest first, with the sides that played in it."""
    engine(db)
    out: dict[int, list[SimSeasonTeam]] = {}
    for r in repo.season_teams(db):
        out.setdefault(int(r["season"]), []).append(
            SimSeasonTeam(
                team=TeamTag(franchise_id=r["franchise_id"], name=r["name"], color=r["color"]),
                display_name=r["display_name"],
            )
        )
    return [SimSeason(season=s, teams=teams) for s, teams in out.items()]


def squad(db: Database, season: int, franchise_id: str) -> SimSquad:
    """A side's squad in a season, with its last XI that season as the default."""
    engine(db)
    team = _team(db, franchise_id)
    rows = repo.season_squad(db, season, franchise_id.upper()) if team else []
    if team is None or not rows:
        raise UnknownSquadError(f"{franchise_id} did not play in {season}")
    ids = [r["player_id"] for r in rows]
    picked = _picked(db, ids, season)
    found = repo.latest_xi(db, team.franchise_id, season)
    match, xi = found if found else (None, [])
    return SimSquad(
        team=team,
        season=season,
        display_name=rows[0]["display_name"],
        players=[
            SquadPlayer(**_sim_player(picked[r["player_id"]]).model_dump(), matches=r["matches"])
            for r in rows
        ],
        xi=xi,
        bowlers=sim.default_bowlers([picked[pid].candidate for pid in xi], rules(db)) if xi else [],
        from_match=None if match is None else int(match["match_id"]),
        match_date=None if match is None else match["match_date"],
    )


def _check_squad(db: Database, season: int, side: SideRequest, names: dict[str, str]) -> None:
    if not side.franchise_id:
        raise InvalidSideError(f"pick a team from the {season} season")
    rows = repo.season_squad(db, season, side.franchise_id.upper())
    if not rows:
        raise InvalidSideError(f"{side.franchise_id} did not play in {season}")
    squad_ids = {r["player_id"] for r in rows}
    for pid in side.batters:
        if pid not in squad_ids:
            raise InvalidSideError(
                f"{names.get(pid, pid)} did not play for {rows[0]['display_name']} in {season}"
            )


# --------------------------------------------------------------------------- match


def _side(e: Engine, name: str, order: list[Picked], bowler_ids: list[str] | None) -> sim.Side:
    candidates = [p.candidate for p in order]
    bowlers = bowler_ids or sim.default_bowlers(candidates, e.rules)
    ids = {c.player.player_id for c in candidates}
    if any(b not in ids for b in bowlers):
        raise InvalidSideError("bowlers must come from the same XI")
    needed = e.rules.min_bowling_options
    if len(set(bowlers)) < needed:
        raise InvalidSideError(f"pick at least {needed} bowling options")
    return sim.build_side(name, candidates, bowlers, e.priors, rules=e.rules)


def _distribution(values: np.ndarray) -> Distribution:
    q = np.percentile(values, [10, 25, 50, 75, 90])
    low = int(values.min()) // 10 * 10
    high = int(values.max()) // 10 * 10
    edges = np.arange(low, high + 20, 10)
    counts, _ = np.histogram(values, bins=edges)
    shares = counts / len(values)
    return Distribution(
        mean=round(float(values.mean()), 1),
        p10=int(q[0]),
        p25=int(q[1]),
        p50=int(q[2]),
        p75=int(q[3]),
        p90=int(q[4]),
        bins=[
            (int(e), round(float(s), 4)) for e, s in zip(edges[:-1], shares, strict=True) if s > 0
        ],
    )


def _pct(x: float) -> float:
    return round(100 * x, 1)


@dataclass
class _Tally:
    """Every simulated innings a side batted and bowled, one row per simulation."""

    batting: list[sim.InningsResult] = field(default_factory=list)
    bowling: list[sim.InningsResult] = field(default_factory=list)


def _quartiles(values: np.ndarray) -> tuple[int | None, int | None, int | None]:
    """25th, 50th and 75th percentiles as values that occurred (whole runs)."""
    if not len(values):
        return None, None, None
    q = np.quantile(values, [0.25, 0.5, 0.75], method="inverted_cdf")
    return int(q[0]), int(q[1]), int(q[2])


def _batters(t: _Tally, order: list[Picked]) -> list[SimBatter]:
    runs = np.concatenate([r.bat_runs for r in t.batting])
    balls = np.concatenate([r.bat_balls for r in t.batting])
    out = np.concatenate([r.bat_out for r in t.batting])
    batted = (balls > 0) | out
    result = []
    for i, p in enumerate(order):
        mask = batted[:, i]
        low, mid, high = _quartiles(runs[mask, i])
        faced = int(balls[:, i].sum())
        result.append(
            SimBatter(
                player_id=p.candidate.player.player_id,
                name=p.name,
                batted_pct=_pct(float(mask.mean())),
                runs=mid,
                runs_low=low,
                runs_high=high,
                balls=_quartiles(balls[mask, i])[1],
                strike_rate=round(100 * float(runs[:, i].sum()) / faced, 1) if faced else None,
                fifty_pct=_pct(float((runs[:, i] >= 50).mean())),
                out_pct=_pct(float(out[:, i].mean())),
            )
        )
    return result


def _bowlers(t: _Tally, side: sim.Side, names: dict[str, str]) -> list[SimBowler]:
    runs = np.concatenate([r.bowl_runs for r in t.bowling])
    balls = np.concatenate([r.bowl_balls for r in t.bowling])
    wickets = np.concatenate([r.bowl_wickets for r in t.bowling])
    result = []
    for j, b in enumerate(side.bowlers):
        mask = balls[:, j] > 0
        bowled = int(balls[:, j].sum())
        result.append(
            SimBowler(
                player_id=b.player_id,
                name=names[b.player_id],
                bowled_pct=_pct(float(mask.mean())),
                balls=_quartiles(balls[mask, j])[1],
                runs=_quartiles(runs[mask, j])[1],
                wickets=_quartiles(wickets[mask, j])[1],
                economy=round(6 * float(runs[:, j].sum()) / bowled, 2) if bowled else None,
                wicket_pct=_pct(float((wickets[:, j] >= 1).mean())),
                three_wicket_pct=_pct(float((wickets[:, j] >= 3).mean())),
            )
        )
    return result


def simulate(db: Database, request: SimulationRequest) -> SimulationResult:
    e = engine(db) if request.season is None else season_engine(db, request.season)
    key = request.model_dump_json()
    cached = _cache(db).get(key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    started = time.perf_counter()
    picked = _picked(db, [*request.a.batters, *request.b.batters], e.season)
    if request.season is not None:
        names = {pid: p.name for pid, p in picked.items()}
        _check_squad(db, request.season, request.a, names)
        _check_squad(db, request.season, request.b, names)

    def build(side: SideRequest) -> tuple[list[Picked], sim.Side]:
        order = [picked[pid] for pid in side.batters]
        return order, _side(e, side.franchise_id or "", order, side.bowlers)

    a_order, a_side = build(request.a)
    b_order, b_side = build(request.b)
    rng = np.random.default_rng(request.seed if request.seed is not None else _seed(key))
    n = request.simulations
    a_first = n if request.bat_first == "a" else 0 if request.bat_first == "b" else n // 2
    runs: list[tuple[str, sim.MatchResult]] = []
    if a_first:
        runs.append(
            (
                "a",
                sim.simulate_match(
                    e.model,
                    e.rates,
                    a_side,
                    b_side,
                    n=a_first,
                    rng=rng,
                    conditions_sd=e.conditions_sd,
                ),
            )
        )
    if n - a_first:
        runs.append(
            (
                "b",
                sim.simulate_match(
                    e.model,
                    e.rates,
                    b_side,
                    a_side,
                    n=n - a_first,
                    rng=rng,
                    conditions_sd=e.conditions_sd,
                ),
            )
        )

    wins = {"a": 0, "b": 0}
    ties = 0
    tallies = {"a": _Tally(), "b": _Tally()}
    first_totals: dict[str, np.ndarray] = {}
    chases: dict[str, tuple[int, int]] = {}
    margins: list[np.ndarray] = []
    for first, played in runs:
        second = "b" if first == "a" else "a"
        wins[first] += int((played.outcome == 1).sum())
        wins[second] += int((played.outcome == -1).sum())
        ties += int((played.outcome == 0).sum())
        tallies[first].batting.append(played.first)
        tallies[second].bowling.append(played.first)
        tallies[second].batting.append(played.second)
        tallies[first].bowling.append(played.second)
        first_totals[first] = played.first.runs
        chases[second] = (int((played.outcome == -1).sum()), played.n)
        won = played.outcome == 1
        if won.any():
            margins.append((played.first.runs - played.second.runs)[won])

    names = {p.candidate.player.player_id: p.name for p in picked.values()}
    sides = []
    for key_, req, order, side_, other in (
        ("a", request.a, a_order, a_side, b_side),
        ("b", request.b, b_order, b_side, a_side),
    ):
        del other
        totals = first_totals.get(key_)
        won_chases, chased = chases.get(key_, (0, 0))
        sides.append(
            SideResult(
                key=key_,  # type: ignore[arg-type]
                team=_team(db, req.franchise_id),
                win_pct=_pct((wins[key_] + 0.5 * ties) / n),
                batting_first_pct=_pct(0 if totals is None else len(totals) / n),
                first_innings=None if totals is None else _distribution(totals),
                chase_pct=_pct(won_chases / chased) if chased else None,
                batters=_batters(tallies[key_], order),
                bowlers=_bowlers(tallies[key_], side_, names),
            )
        )
    p = (wins["a"] + 0.5 * ties) / n
    result = SimulationResult(
        simulations=n,
        bat_first=request.bat_first,
        a_win_pct=_pct(wins["a"] / n),
        b_win_pct=_pct(wins["b"] / n),
        tie_pct=_pct(ties / n),
        standard_error=round(100 * math.sqrt(p * (1 - p) / n), 2),
        sides=sides,
        margin_runs=_distribution(np.concatenate(margins)) if margins else None,
        seconds=round(time.perf_counter() - started, 3),
        ball_model_version=e.ball_version,
        simulator_version=e.version,
        conditions_sd=e.conditions_sd,
    )
    _remember(db, key, result)
    return result


def warm_up(db: Database) -> None:
    """Build the engine and play a few matches, so the first request is not slow."""
    try:
        latest = seasons(db)[0]
        a, b = (squad(db, latest.season, t.team.franchise_id) for t in latest.teams[:2])
        if len(a.xi) == len(b.xi) == 11:
            simulate(
                db,
                SimulationRequest(
                    a=SideRequest(franchise_id=a.team.franchise_id, batters=a.xi),
                    b=SideRequest(franchise_id=b.team.franchise_id, batters=b.xi),
                    season=latest.season,
                    simulations=500,
                ),
            )
    except (LookupError, ValueError, IndexError):
        pass  # no simulator in this build, or too little data to play a match


# --------------------------------------------------------------------------- what-if


@dataclass
class _Position:
    batting_team: str
    bowling_team: str
    order: list[Picked]
    bowling: sim.Side
    state: sim.InningsState
    target: int | None
    finished: bool
    # The balls the innings could last: a rain-revised chase's allocation, else the
    # scheduled overs.
    max_balls: int


def _order_for(
    db: Database, e: Engine, arrived: list[str], squad: list[str]
) -> tuple[list[Picked], dict[str, Picked]]:
    picked = _picked(db, list(dict.fromkeys([*arrived, *squad])), e.season)
    rest = sim.typical_order([picked[pid].candidate for pid in squad if pid not in arrived])
    ids = [*arrived, *(c.player.player_id for c in rest)][:11]
    return [picked[pid] for pid in ids], picked


def _fielding_side(e: Engine, db: Database, squad: list[str], bowled: list[str]) -> sim.Side:
    picked = _picked(db, squad, e.season)
    candidates = [picked[pid].candidate for pid in squad]
    ids = list(dict.fromkeys([*bowled, *sim.default_bowlers(candidates, e.rules)]))
    for c in sorted(candidates, key=lambda c: -c.overs):  # top up to enough options
        if len(ids) >= e.rules.min_bowling_options:
            break
        if c.player.player_id not in ids:
            ids.append(c.player.player_id)
    order = sim.typical_order(candidates)[:11]
    for pid in ids:  # every bowler must be in the side passed to the engine
        if all(c.player.player_id != pid for c in order):
            order.append(picked[pid].candidate)
    return sim.build_side("", order, ids, e.priors, rules=e.rules)


def _position(db: Database, e: Engine, request: StateRequest) -> _Position:
    m, inn, seq = request.match_id, request.innings_no, request.seq_no
    teams = db.row(
        "SELECT i.batting_team_id, i.bowling_team_id, i.target_runs, "
        "coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over) AS max_balls "
        "FROM innings i JOIN matches m USING (match_id) "
        "WHERE i.match_id = ? AND i.innings_no = ? AND NOT i.is_super_over",
        [m, inn],
    )
    if teams is None:
        raise StateNotFoundError(f"match {m} has no innings {inn}")
    bat_team, bowl_team = teams["batting_team_id"], teams["bowling_team_id"]
    balls = repo.innings_so_far(db, m, inn, seq) if seq > 0 else []
    if seq > 0 and not balls:
        raise StateNotFoundError(f"no ball {seq} in innings {inn} of match {m}")
    nxt = repo.next_ball(db, m, inn, seq)
    finished = nxt is None and seq > 0

    arrived: list[str] = []
    for b in balls:
        for pid in (b["batter_id"], b["non_striker_id"]):
            if pid not in arrived:
                arrived.append(pid)
    pair = [nxt["batter_id"], nxt["non_striker_id"]] if nxt else arrived[-2:]
    for pid in pair:
        if pid not in arrived:
            arrived.append(pid)
    bat_squad = repo.squad(db, m, bat_team)
    order, _ = _order_for(db, e, arrived, bat_squad)
    ids = [p.candidate.player.player_id for p in order]
    out = set(repo.dismissed(db, m, inn, seq))

    bat_runs = [0] * len(ids)
    bat_balls = [0] * len(ids)
    for b in balls:
        if b["batter_id"] in ids:
            i = ids.index(b["batter_id"])
            bat_runs[i] += int(b["runs_batter"])
            bat_balls[i] += int(b["extras_wides"] == 0)

    # Overs bowled so far: each over belongs to whoever bowled most of its legal balls.
    overs: dict[int, dict[str, int]] = {}
    for b in balls:
        overs.setdefault(int(b["over_no"]), {})
        overs[int(b["over_no"])][b["bowler_id"]] = overs[int(b["over_no"])].get(
            b["bowler_id"], 0
        ) + int(b["is_legal"])
    legal = int(balls[-1]["legal_ball_no"]) if balls else 0
    owners = {o: max(c, key=lambda k: c[k]) for o, c in overs.items()}
    complete = legal // 6
    bowled = list(dict.fromkeys(owners.values()))
    bowling = _fielding_side(e, db, repo.squad(db, m, bowl_team), bowled)
    bowler_ids = [p.player_id for p in bowling.bowlers]
    bowl_overs = [0] * len(bowler_ids)
    for o in range(complete):
        if o in owners:
            bowl_overs[bowler_ids.index(owners[o])] += 1
    in_progress = legal % 6 != 0 and complete in owners
    state = sim.InningsState(
        runs=int(balls[-1]["team_runs"]) if balls else 0,
        wickets=int(balls[-1]["team_wickets"]) if balls else 0,
        balls=legal,
        striker=ids.index(pair[0]) if len(pair) == 2 else 0,
        non_striker=ids.index(pair[1]) if len(pair) == 2 else 1,
        next_in=max(len(arrived), 2),
        bat_runs=bat_runs,
        bat_balls=bat_balls,
        bat_out=[pid in out for pid in ids],
        bowl_overs=bowl_overs,
        bowler=bowler_ids.index(owners[complete]) if in_progress else None,
        last_bowler=bowler_ids.index(owners[complete - 1])
        if complete > 0 and (complete - 1) in owners
        else None,
    )
    return _Position(
        batting_team=bat_team,
        bowling_team=bowl_team,
        order=order,
        bowling=bowling,
        state=state,
        target=teams["target_runs"],
        finished=finished,
        max_balls=min(int(teams["max_balls"] or e.rules.max_balls), e.rules.max_balls),
    )


def _edited(state: sim.InningsState, runs: int | None, wickets: int | None) -> sim.InningsState:
    s = sim.InningsState(**{**state.__dict__, "bat_out": list(state.bat_out)})
    if runs is not None:
        s.runs = runs
    extra = 0 if wickets is None else max(0, wickets - s.wickets)
    for _ in range(extra):  # the striker is out, the next batter comes in
        if s.next_in >= len(s.bat_out):
            break
        s.bat_out[s.striker] = True
        s.striker = s.next_in
        s.next_in += 1
        s.wickets += 1
    return s


def _play_from(
    e: Engine,
    pos: _Position,
    chasing: sim.Side | None,
    state: sim.InningsState,
    innings: int,
    n: int,
    seed: int,
) -> tuple[float, np.ndarray]:
    """Batting side's chance of winning from ``state``, and its final totals."""
    rng = np.random.default_rng(seed)
    conditions = rng.normal(0.0, e.conditions_sd, n) if e.conditions_sd > 0 else None
    candidates = [p.candidate for p in pos.order]
    # The batting side's own bowlers only matter when it bowls the second innings.
    batting = sim.build_side(
        "", candidates, sim.default_bowlers(candidates, e.rules), e.priors, rules=e.rules
    )
    target = None if innings == 1 or pos.target is None else np.full(n, int(pos.target))
    current = sim.simulate_innings(
        e.model,
        e.rates,
        batting,
        pos.bowling,
        innings=innings,
        n=n,
        rng=rng,
        target=target,
        start=state,
        max_balls=pos.max_balls,
        conditions=conditions,
    )
    if innings == 2:
        assert pos.target is not None
        won = (current.runs >= pos.target).astype(float)
        tied = (current.runs == pos.target - 1).astype(float)
        return float(np.mean(won + 0.5 * tied)), current.runs
    assert chasing is not None
    second = sim.simulate_innings(
        e.model,
        e.rates,
        chasing,
        batting,
        innings=2,
        n=n,
        rng=rng,
        target=current.runs + 1,
        conditions=conditions,
    )
    outcome = np.sign(current.runs - second.runs)
    return float(np.mean(outcome == 1) + 0.5 * np.mean(outcome == 0)), current.runs


def _logit(p: float) -> float:
    q = min(max(p, CLIP), 1 - CLIP)
    return math.log(q / (1 - q))


def _tag(db: Database, team_season_id: str) -> TeamTag:
    row = db.row(
        """
        SELECT f.franchise_id, f.name, f.primary_color AS color
        FROM team_seasons t JOIN franchises f USING (franchise_id) WHERE t.team_season_id = ?
        """,
        [team_season_id],
    )
    assert row is not None
    return TeamTag(**row)


def what_if(db: Database, request: StateRequest) -> StateResult:
    e = era_engine(db, request.match_id)
    key = request.model_dump_json()
    cached = _cache(db).get(key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    started = time.perf_counter()
    pos = _position(db, e, request)
    if pos.finished:
        raise StateNotFoundError("the innings is over at this ball")
    chasing = None
    if request.innings_no == 1:
        fielding = repo.squad(db, request.match_id, pos.bowling_team)
        picked = _picked(db, fielding, e.season)
        cands = [picked[pid].candidate for pid in fielding]
        chasing = sim.build_side(
            "",
            sim.typical_order(cands)[:11],
            sim.default_bowlers(cands, e.rules),
            e.priors,
            rules=e.rules,
        )
    edited_state = _edited(pos.state, request.runs, request.wickets)
    seed = _seed(f"{request.match_id}:{request.innings_no}:{request.seq_no}")
    n = request.simulations
    p_actual, totals_actual = _play_from(e, pos, chasing, pos.state, request.innings_no, n, seed)
    p_edited, totals_edited = _play_from(e, pos, chasing, edited_state, request.innings_no, n, seed)

    wp_a = repo.win_probability(db, request.match_id, request.innings_no, request.seq_no)
    model_wp = None if wp_a is None else (wp_a if request.innings_no == 1 else 1 - wp_a)
    if model_wp is None:
        whatif = p_edited
    else:
        shift = _logit(p_edited) - _logit(p_actual)
        whatif = 1 / (1 + math.exp(-(_logit(model_wp) + shift)))

    def outcome(state: sim.InningsState, p: float, totals: np.ndarray) -> StateOutcome:
        return StateOutcome(
            score=StateScore(runs=state.runs, wickets=state.wickets, balls=state.balls),
            simulated_win_pct=_pct(p),
            total=_distribution(totals),
        )

    result = StateResult(
        batting=_tag(db, pos.batting_team),
        bowling=_tag(db, pos.bowling_team),
        innings_no=request.innings_no,
        target=pos.target if request.innings_no == 2 else None,
        model_win_pct=None if model_wp is None else _pct(model_wp),
        actual=outcome(pos.state, p_actual, totals_actual),
        edited=outcome(edited_state, p_edited, totals_edited),
        whatif_win_pct=_pct(whatif),
        simulations=n,
        seconds=round(time.perf_counter() - started, 3),
    )
    _remember(db, key, result)
    return result
