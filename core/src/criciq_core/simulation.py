"""Monte Carlo match simulation from the ball-outcome model.

Every simulated match is played ball by ball. All simulations step forward
together, one legal ball at a time, as numpy arrays, so 10,000 matches cost
about as much as a few hundred array operations per ball (ADR-0006).

On each legal ball:

0. **Conditions**: each simulated match first draws how good the pitch and
   ground are for batting, which the model cannot see, and keeps it for both
   innings.
1. **Extras** that come with the ball (wides and no-balls before it, byes and
   leg byes on it) are drawn from league rates for the innings and phase.
2. **The ball faced** is drawn from the ball-outcome model: its additive terms
   for the phase and innings, wickets down, how set the striker is, batter hand
   against bowler type, the chase pressure, the scoring era, the striker and the
   bowler (ADR-0005). Outcomes are a dot, 1, 2, 3, 4, 6 or the batter out.
3. **Run outs**, which the ball model counts as runs completed, are added at
   the league rate for the innings and phase; striker or non-striker equally.

Odd runs change the strike, as does the end of an over. A dismissed batter is
replaced by the next in the batting order. At the start of each over the
fielding captain picks a bowler: one who has overs left (four each) and did not
bowl the previous over, chosen in proportion to how often that bowler bowled
that over in real matches; towards the end of the innings, bowlers with more
overs left are favoured so the quota is used up. An innings ends after 120
legal balls, when the side is all out, or when the target is reached. A tie is
reported as a tie (a super over is not simulated).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from criciq_core.phases import model_phases

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]

# The ball-outcome model's classes and levels (ml/src/criciq_ml/ball_outcome.py).
CLASSES = ("dot", "one", "two", "three", "four", "six", "out")
RUNS = np.array([0, 1, 2, 3, 4, 6, 0], dtype=np.int64)
OUT = CLASSES.index("out")
WICKET_LEVELS = (("0-1", 2), ("2-3", 4), ("4-5", 6), ("6+", 99))
SETTLED_LEVELS = (("0-5", 6), ("6-15", 16), ("16-30", 31), ("31+", 10_000))
PRESSURE_LEVELS = ("none", "low", "par", "high", "extreme")
# Required rate over par at which a chase moves to the next pressure level.
PRESSURE_EDGES = (0.8, 1.1, 1.4)

OVERS = 20
BALLS_PER_OVER = 6
MAX_BALLS = OVERS * BALLS_PER_OVER
QUOTA = 4
EXTRA_RUNS = np.arange(6, dtype=np.int64)  # 0..5 extra runs with a legal ball
# From this over on, bowlers with more overs left are favoured (weight x overs left squared).
URGENT_FROM_OVER = 12
# Match conditions (pitch, ground, weather) the model cannot see: each simulated
# match draws a shift, shared by both innings, that moves logits along this
# direction (more boundaries, fewer dots and wickets when positive). Its spread is
# tuned on validation seasons so simulated totals vary as much as real ones.
CONDITIONS = np.array([-0.5, 0.0, 0.0, 0.0, 0.5, 0.5, -0.5])
CONDITIONS_SD = 0.0

_PHASE_CONFIG = model_phases()
PHASES: tuple[str, ...] = tuple(
    p.key for p in sorted(_PHASE_CONFIG.phases, key=lambda p: p.first_over)
)
OVER_PHASE = np.array(
    [PHASES.index(_PHASE_CONFIG.phase_for_over_index(o).key) for o in range(OVERS)],
    dtype=np.int64,
)


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True)
class Player:
    player_id: str
    batting_hand: str | None = None
    bowling_type: str | None = None


@dataclass(frozen=True)
class Side:
    """A team for one match: the batting order and the bowling options."""

    name: str
    batters: tuple[Player, ...]
    bowlers: tuple[Player, ...]
    # How often each bowler bowled each over (rows follow ``bowlers``; 20 columns).
    usage: FloatArray

    def __post_init__(self) -> None:
        if not 2 <= len(self.batters) <= 11:
            raise ValueError("a side bats 2 to 11 players")
        if len(self.bowlers) * QUOTA < OVERS:
            raise ValueError(f"a side needs at least {OVERS // QUOTA} bowling options")
        if self.usage.shape != (len(self.bowlers), OVERS):
            raise ValueError("usage needs one row per bowler and one column per over")


@dataclass(frozen=True)
class BallModel:
    """The ball-outcome model as additive terms per outcome (ADR-0005)."""

    terms: Mapping[str, Sequence[float]]
    era: float  # standardised log runs per ball of the scoring era

    def term(self, key: str) -> FloatArray:
        values = self.terms.get(key)
        if values is None:
            return np.zeros(len(CLASSES))
        return np.asarray(values, dtype=float)


@dataclass(frozen=True)
class LeagueRates:
    """Extras and run outs per legal ball, by innings (2) and phase (3)."""

    extras: FloatArray  # (2, 3, 6) probabilities of 0..5 extra runs
    run_out: FloatArray  # (2, 3)
    env: float = 1.3  # league runs per ball faced, for the chase pressure level


@dataclass
class InningsState:
    """Where an innings stands; the default is before the first ball."""

    runs: int = 0
    wickets: int = 0
    balls: int = 0
    striker: int = 0
    non_striker: int = 1
    next_in: int = 2
    bat_runs: list[int] = field(default_factory=list)
    bat_balls: list[int] = field(default_factory=list)
    bat_out: list[bool] = field(default_factory=list)
    bowl_overs: list[int] = field(default_factory=list)
    bowler: int | None = None  # bowler of the over in progress
    last_bowler: int | None = None  # bowler of the last completed over


@dataclass
class InningsResult:
    runs: IntArray
    wickets: IntArray
    balls: IntArray
    bat_runs: IntArray  # (n, batters)
    bat_balls: IntArray
    bat_out: BoolArray
    bowl_runs: IntArray  # (n, bowlers): runs off the bat
    bowl_balls: IntArray
    bowl_wickets: IntArray
    forced_overs: int  # overs no eligible bowler could take (a rule had to give)


# --------------------------------------------------------------------------- tables


def _level(value: IntArray, levels: tuple[tuple[str, int], ...]) -> IntArray:
    edges = np.array([edge for _, edge in levels[:-1]])
    return np.asarray(np.searchsorted(edges, value, side="right"), dtype=np.int64)


def _base_logits(model: BallModel, bat: Side, bowl: Side, innings: int) -> FloatArray:
    """Logits that do not change ball to ball: (phase, batter, bowler, outcome)."""
    era = model.era * model.term("env")
    out = np.zeros((len(PHASES), len(bat.batters), len(bowl.bowlers), len(CLASSES)))
    for p, phase in enumerate(PHASES):
        fixed = model.term("intercept") + model.term(f"phase={phase}_{innings}") + era
        for i, batter in enumerate(bat.batters):
            b = model.term(f"batter={batter.player_id}") + model.term(
                f"batter@{phase}={batter.player_id}"
            )
            for j, bowler in enumerate(bowl.bowlers):
                matchup = model.term(f"matchup={batter.batting_hand}_{bowler.bowling_type}")
                w = model.term(f"bowler={bowler.player_id}") + model.term(
                    f"bowler@{phase}={bowler.player_id}"
                )
                out[p, i, j] = fixed + b + w + matchup
    return out


def _group_terms(model: BallModel, group: str, levels: Sequence[str]) -> FloatArray:
    return np.stack([model.term(f"{group}={level}") for level in levels])


def _sample(probabilities: FloatArray, rng: np.random.Generator) -> IntArray:
    """One draw per row of a (rows, classes) probability matrix."""
    cumulative = probabilities.cumsum(axis=1)
    u = rng.random((len(probabilities), 1)) * cumulative[:, -1:]
    picked = np.minimum((cumulative < u).sum(axis=1), probabilities.shape[1] - 1)
    return np.asarray(picked, dtype=np.int64)


# --------------------------------------------------------------------------- innings


def _tally(
    rows: IntArray, slots: IntArray, values: npt.NDArray[np.generic], width: int
) -> IntArray:
    """Per-simulation totals by slot from per-ball (balls, sims) arrays."""
    flat = (rows[None, :] * width + slots).ravel()
    sums = np.bincount(flat, weights=values.ravel().astype(float), minlength=len(rows) * width)
    return np.asarray(np.rint(sums).reshape(len(rows), width), dtype=np.int64)


def _can_finish(left: IntArray, over: int) -> BoolArray:
    """Whether the remaining overs can still be covered if each bowler takes this one.

    After bowler j takes ``over``, the R overs that follow need bowlers with overs
    left and no bowler twice in a row, so nobody can cover more than half of them
    (the bowler of this over one fewer). The innings can finish only if those caps
    add up to R. Taking one over lowers that sum by at most two, so only
    simulations within two of the limit need the check bowler by bowler.
    """
    rest = OVERS - over - 1
    cap = (rest + 1) // 2
    out = np.ones(left.shape, dtype=bool)
    tight = np.minimum(left, cap).sum(axis=1) - 2 < rest
    if not tight.any():
        return out
    sub = left[tight]
    for j in range(left.shape[1]):
        after = sub.copy()
        after[:, j] -= 1
        caps = np.minimum(after, cap)
        caps[:, j] = np.minimum(after[:, j], rest // 2)
        out[tight, j] = caps.clip(min=0).sum(axis=1) >= rest
    return out


def _pick_bowlers(
    usage: FloatArray,
    over: int,
    overs_used: IntArray,
    last: IntArray,
    rng: np.random.Generator,
) -> tuple[IntArray, int]:
    """Bowler of ``over`` for each simulation, and how many had no eligible bowler."""
    n, bowlers = overs_used.shape
    left = QUOTA - overs_used
    weight = np.broadcast_to(usage[:, over], (n, bowlers)).astype(float)
    if over >= URGENT_FROM_OVER:
        weight = weight * left.astype(float) ** 2
    eligible = (left > 0) & (np.arange(bowlers) != last[:, None]) & _can_finish(left, over)
    weight = np.where(eligible, weight, 0.0)
    # Anyone eligible with no history of that over still gets a small chance.
    weight = np.where(eligible, weight + 1e-3, 0.0)
    stuck = weight.sum(axis=1) == 0
    if stuck.any():
        # Only the previous bowler has overs left: they bowl again.
        weight[stuck] = np.where(left[stuck] > 0, 1.0, 0.0)
    still = weight.sum(axis=1) == 0
    if still.any():
        weight[still] = 1.0  # every quota is used up (cannot happen with 5+ bowlers)
    return _sample(weight, rng), int(stuck.sum() + still.sum())


def simulate_innings(
    model: BallModel,
    rates: LeagueRates,
    bat: Side,
    bowl: Side,
    *,
    innings: int,
    n: int,
    rng: np.random.Generator,
    target: IntArray | None = None,
    start: InningsState | None = None,
    max_balls: int = MAX_BALLS,
    conditions: FloatArray | None = None,
) -> InningsResult:
    """Play the rest of an innings ``n`` times; ``target`` makes it a chase."""
    s = start or InningsState()
    nbat, nbowl = len(bat.batters), len(bowl.bowlers)
    nw, ns, npr = len(WICKET_LEVELS), len(SETTLED_LEVELS), len(PRESSURE_LEVELS)
    # Every combination of phase, batter, bowler and situation level is a small
    # table, so each ball is a lookup of unnormalised outcome weights, not a softmax.
    logits = (
        _base_logits(model, bat, bowl, innings)[:, :, :, None, None, None, :]
        + _group_terms(model, "wickets", [lv for lv, _ in WICKET_LEVELS])[:, None, None, :]
        + _group_terms(model, "settled", [lv for lv, _ in SETTLED_LEVELS])[:, None, :]
        + _group_terms(model, "pressure", PRESSURE_LEVELS)[:, :]
    )
    table = np.exp(logits - logits.max(axis=-1, keepdims=True)).reshape(-1, len(CLASSES))
    shift = None if conditions is None else np.exp(conditions[:, None] * CONDITIONS)
    extras_cum = rates.extras[innings - 1].cumsum(axis=1)
    run_out_p = rates.run_out[innings - 1]

    def ints(values: list[int], size: int) -> IntArray:
        row = np.zeros(size, dtype=np.int64)
        row[: len(values)] = values[:size]
        return np.tile(row, (n, 1))

    def flags(values: list[bool], size: int) -> BoolArray:
        row = np.zeros(size, dtype=np.bool_)
        row[: len(values)] = values[:size]
        return np.tile(row, (n, 1))

    runs = np.full(n, s.runs, dtype=np.int64)
    wickets = np.full(n, s.wickets, dtype=np.int64)
    balls = np.full(n, s.balls, dtype=np.int64)
    striker = np.full(n, s.striker, dtype=np.int64)
    non_striker = np.full(n, s.non_striker, dtype=np.int64)
    next_in = np.full(n, s.next_in, dtype=np.int64)
    bat_runs = ints(s.bat_runs, nbat)
    bat_balls = ints(s.bat_balls, nbat)
    bat_out = flags(s.bat_out, nbat)
    bowl_overs = ints(s.bowl_overs, nbowl)
    # Tallies not needed during the innings are kept per ball and added up at the end.
    ledger: list[tuple[IntArray, IntArray, IntArray, BoolArray, BoolArray]] = []
    current = np.full(n, -1 if s.bowler is None else s.bowler, dtype=np.int64)
    last = np.full(n, -1 if s.last_bowler is None else s.last_bowler, dtype=np.int64)
    rows = np.arange(n)
    max_wickets = nbat - 1
    done = (wickets >= max_wickets) | (balls >= max_balls)
    if target is not None:
        done |= runs >= target
    forced = 0

    for ball in range(s.balls, max_balls):
        live = ~done
        if not live.any():
            break
        over, in_over = divmod(ball, BALLS_PER_OVER)
        phase = OVER_PHASE[min(over, OVERS - 1)]
        if in_over == 0 or (live & (current < 0)).any():
            pick, stuck = _pick_bowlers(bowl.usage, min(over, OVERS - 1), bowl_overs, last, rng)
            choose = live & ((current < 0) | (in_over == 0))
            current = np.where(choose, pick, current)
            forced += int(stuck)
        u = rng.random((n, 4))

        # 1. Extras that come with this ball.
        extra = np.minimum(np.searchsorted(extras_cum[phase], u[:, 0], side="right"), 5)
        runs = np.where(live, runs + extra, runs)

        # 2. The ball faced.
        bowler = current.clip(min=0)
        settled = _level(bat_balls[rows, striker], SETTLED_LEVELS)
        wicket_level = np.minimum(wickets // 2, nw - 1)
        if target is None:
            pressure_level = 0
        else:
            left = np.maximum(max_balls - ball, 1)
            relative = (target - runs) / left / rates.env
            pressure_level = 1 + np.searchsorted(PRESSURE_EDGES, relative, side="right")
        cell = (((phase * nbat + striker) * nbowl + bowler) * nw + wicket_level) * ns + settled
        weights = table[cell * npr + pressure_level]
        if shift is not None:
            weights = weights * shift
        cumulative = weights.cumsum(axis=1)
        outcome = np.minimum(
            (cumulative < (u[:, 1] * cumulative[:, -1])[:, None]).sum(axis=1), len(CLASSES) - 1
        )
        scored = RUNS[outcome]
        bowled_out = (outcome == OUT) & live
        # 3. Run outs, at the league rate, on balls the batter survived.
        run_out = live & ~bowled_out & (u[:, 2] < run_out_p[phase])
        non_striker_out = run_out & (u[:, 3] < 0.5)

        scored = np.where(live, scored, 0)
        runs += scored
        bat_balls[rows, striker] += live
        ledger.append((striker, bowler, scored, live, bowled_out))
        balls = np.where(live, ball + 1, balls)

        out = bowled_out | run_out
        if out.any():
            out_slot = np.where(non_striker_out, non_striker, striker)
            bat_out[rows[out], out_slot[out]] = True
            wickets += out
            replacement = np.minimum(next_in, nbat - 1)
            striker = np.where(out & ~non_striker_out, replacement, striker)
            non_striker = np.where(out & non_striker_out, replacement, non_striker)
            next_in += out

        swap = live & ~out & (scored % 2 == 1)
        if in_over == BALLS_PER_OVER - 1:
            swap = swap ^ live
            ended = live
            bowl_overs[rows[ended], current[ended]] += 1
            last = np.where(ended, current, last)
            current = np.where(ended, -1, current)
        striker, non_striker = (
            np.where(swap, non_striker, striker),
            np.where(swap, striker, non_striker),
        )

        done |= live & (wickets >= max_wickets)
        if target is not None:
            done |= live & (runs >= target)
        done |= balls >= max_balls

    if ledger:
        strikers, bowlers, scores, lives, outs = (np.stack(x) for x in zip(*ledger, strict=True))
        bat_runs += _tally(rows, strikers, scores, nbat)
        bowl_runs = _tally(rows, bowlers, scores, nbowl)
        bowl_balls = _tally(rows, bowlers, lives, nbowl)
        bowl_wkts = _tally(rows, bowlers, outs, nbowl)
    else:
        bowl_runs = np.zeros((n, nbowl), dtype=np.int64)
        bowl_balls = np.zeros((n, nbowl), dtype=np.int64)
        bowl_wkts = np.zeros((n, nbowl), dtype=np.int64)
    return InningsResult(
        runs=runs,
        wickets=wickets,
        balls=balls,
        bat_runs=bat_runs,
        bat_balls=bat_balls,
        bat_out=bat_out,
        bowl_runs=bowl_runs,
        bowl_balls=bowl_balls,
        bowl_wickets=bowl_wkts,
        forced_overs=forced,
    )


# --------------------------------------------------------------------------- match


@dataclass
class MatchResult:
    first: InningsResult
    second: InningsResult
    # +1 the side batting first won, -1 the chasing side won, 0 a tie.
    outcome: IntArray

    @property
    def n(self) -> int:
        return len(self.outcome)


def simulate_match(
    model: BallModel,
    rates: LeagueRates,
    batting_first: Side,
    chasing: Side,
    *,
    n: int,
    rng: np.random.Generator,
    conditions_sd: float = CONDITIONS_SD,
) -> MatchResult:
    """``n`` complete matches with a fixed batting order of the two sides.

    Each simulated match draws its own conditions (shared by both innings).
    """
    conditions = rng.normal(0.0, conditions_sd, n) if conditions_sd > 0 else None
    first = simulate_innings(
        model, rates, batting_first, chasing, innings=1, n=n, rng=rng, conditions=conditions
    )
    target = first.runs + 1
    second = simulate_innings(
        model,
        rates,
        chasing,
        batting_first,
        innings=2,
        n=n,
        rng=rng,
        target=target,
        conditions=conditions,
    )
    outcome = np.sign(first.runs - second.runs).astype(np.int64)
    return MatchResult(first=first, second=second, outcome=outcome)


# --------------------------------------------------------------------------- setup

# A bowler's own usage pattern is shrunk toward the league's for their type,
# worth this many overs.
USAGE_STRENGTH = 8.0
# Bowlers with at least this many recent overs are bowling options by default.
MIN_BOWLING_OVERS = 4.0
MAX_BOWLING_OPTIONS = 6
MIN_BOWLING_OPTIONS = OVERS // QUOTA
# Typical batting position for a player with no batting record.
UNKNOWN_POSITION = 9.0


@dataclass(frozen=True)
class Candidate:
    """A player available for a simulated XI, with their recent record."""

    player: Player
    position: float | None  # average batting position, if they have batted
    overs_by_over: FloatArray  # recent overs bowled at each over number (20)

    @property
    def overs(self) -> float:
        return float(self.overs_by_over.sum())


def league_rates(rows: Sequence[Sequence[float | int | str]], env: float) -> LeagueRates:
    """League rates from ``sim_league_rates`` rows summed over the chosen seasons:
    (innings_no, phase, legal_balls, run_outs, x0, ..., x5)."""
    balls = np.zeros((2, len(PHASES)))
    run_outs = np.zeros((2, len(PHASES)))
    extras = np.zeros((2, len(PHASES), len(EXTRA_RUNS)))
    for innings, phase, legal, outs, *xs in rows:
        i, p = int(innings) - 1, PHASES.index(str(phase))
        balls[i, p] += float(legal)
        run_outs[i, p] += float(outs)
        extras[i, p] += np.asarray(xs, dtype=float)
    safe = np.maximum(balls, 1.0)
    probs = extras / safe[:, :, None]
    probs[balls == 0] = np.eye(len(EXTRA_RUNS))[0]  # no data: no extras
    return LeagueRates(extras=probs, run_out=run_outs / safe, env=env)


def usage_priors(rows: Sequence[tuple[str | None, int, float]]) -> dict[str, FloatArray]:
    """League shape of overs bowled by over number, per bowling type, from
    (bowling_type, over_no, overs) rows; ``"any"`` pools every type."""
    shapes: dict[str, FloatArray] = {"any": np.zeros(OVERS)}
    for kind, over, overs in rows:
        if 0 <= int(over) < OVERS:
            key = kind or "any"
            shapes.setdefault(key, np.zeros(OVERS))[int(over)] += float(overs)
            if key != "any":
                shapes["any"][int(over)] += float(overs)
    return {k: v / v.sum() if v.sum() else np.full(OVERS, 1 / OVERS) for k, v in shapes.items()}


def default_bowlers(candidates: Sequence[Candidate]) -> list[str]:
    """The XI's bowling options: regular bowlers by recent overs, topped up to five."""
    ranked = sorted(candidates, key=lambda c: -c.overs)
    chosen = [c for c in ranked if c.overs >= MIN_BOWLING_OVERS][:MAX_BOWLING_OPTIONS]
    for c in ranked:  # part-timers next, by how much they have bowled
        if len(chosen) >= MIN_BOWLING_OPTIONS:
            break
        if c not in chosen:
            chosen.append(c)
    return [c.player.player_id for c in chosen]


def typical_order(candidates: Sequence[Candidate]) -> list[Candidate]:
    """An XI in its usual batting order (average position; unknowns near the end)."""
    return sorted(
        candidates,
        key=lambda c: c.position if c.position is not None else UNKNOWN_POSITION,
    )


def build_side(
    name: str,
    batting_order: Sequence[Candidate],
    bowler_ids: Sequence[str],
    priors: Mapping[str, FloatArray],
    strength: float = USAGE_STRENGTH,
) -> Side:
    """A simulated side from an XI in batting order and its bowling options."""
    by_id = {c.player.player_id: c for c in batting_order}
    bowlers = [by_id[pid] for pid in bowler_ids]
    rows = []
    for c in bowlers:
        prior = priors.get(c.player.bowling_type or "any", priors["any"])
        rows.append(c.overs_by_over + strength * prior)
    usage = np.asarray(rows, dtype=float)
    usage = usage / usage.sum(axis=1, keepdims=True)
    return Side(
        name=name,
        batters=tuple(c.player for c in batting_order),
        bowlers=tuple(c.player for c in bowlers),
        usage=usage,
    )
