"""Matchup Lab: head-to-head records, empirical-Bayes estimates and next-ball odds.

The ball-outcome model arrives as a table of additive terms per outcome
(intercept, situation levels, scoring era, batter, bowler), so a prediction is
a sum and a softmax: no ML library at request time (ADR-0004).

Head-to-head estimates use a Dirichlet prior centred on what the model
expects for the pair's own balls, with a strength of ``kappa`` balls fitted
across every pair (empirical Bayes). Intervals are 90% normal approximations
to the posterior, which are accurate here because ``kappa`` is large.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories import matches as matches_repo
from criciq_api.repositories import matchups as repo
from criciq_api.repositories.matchups import CLASSES, RUNS, MatchupSort
from criciq_api.schemas.matchups import (
    HeadToHead,
    Interval,
    MatchupDetail,
    MatchupDismissal,
    MatchupList,
    MatchupListItem,
    MatchupNumbers,
    MatchupPlayer,
    MatchupSplitRow,
    NextBall,
    NextBallRequest,
    NextBallResponse,
    OutcomeProbability,
    Phase,
    SampleLevel,
    SampleSize,
)
from criciq_api.schemas.players import SeasonWindow, TeamTag
from criciq_api.services.players import resolve_window
from criciq_core.phases import default_phase_config

Z90 = 1.6449
OUT = CLASSES.index("out")
DOT = CLASSES.index("dot")
BOUNDARY = (CLASSES.index("four"), CLASSES.index("six"))
LABELS = {
    "dot": "Dot",
    "one": "1 run",
    "two": "2 runs",
    "three": "3 runs",
    "four": "Four",
    "six": "Six",
    "out": "Wicket",
}
# Default situation for next-ball odds: a set batter, a couple of wickets down.
DEFAULT_WICKETS = 2
DEFAULT_BATTER_BALLS = 20


class MatchupUnavailableError(LookupError):
    pass


class PlayerNotFoundError(LookupError):
    pass


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class BallModel:
    version: str
    kappa: float
    env_now: float
    env_mean: float
    env_std: float
    terms: dict[str, list[float]]

    def probabilities(
        self,
        *,
        batter_id: str,
        bowler_id: str,
        phase: str,
        innings: int,
        wickets: int,
        batter_balls: int,
        matchup: str,
        pressure: str,
    ) -> list[float]:
        logits = list(self.terms["intercept"])
        keys = [
            f"phase={phase}_{innings}",
            f"wickets={_bucket(wickets, (2, 4, 6), ('0-1', '2-3', '4-5', '6+'))}",
            f"settled={_bucket(batter_balls, (6, 16, 31), ('0-5', '6-15', '16-30', '31+'))}",
            f"matchup={matchup}",
            f"pressure={pressure if innings == 2 else 'none'}",
            f"batter={batter_id}",
            f"bowler={bowler_id}",
            f"batter@{phase}={batter_id}",
            f"bowler@{phase}={bowler_id}",
        ]
        for key in keys:
            for i, value in enumerate(self.terms.get(key, ())):
                logits[i] += value
        era = (math.log(self.env_now) - self.env_mean) / self.env_std
        for i, value in enumerate(self.terms["env"]):
            logits[i] += era * value
        top = max(logits)
        exps = [math.exp(x - top) for x in logits]
        total = sum(exps)
        return [e / total for e in exps]


def _bucket(value: int, edges: tuple[int, ...], labels: tuple[str, ...]) -> str:
    for edge, label in zip(edges, labels, strict=False):
        if value < edge:
            return label
    return labels[-1]


def ball_model(db: Database) -> BallModel | None:
    if not repo.available(db):
        return None
    if "ball_model" not in db.cache:
        row = matches_repo.get_model(db, "ball_outcome")
        if row is None:
            return None
        info: dict[str, Any] = row  # get_model merges the stored info into the row
        db.cache["ball_model"] = BallModel(
            version=row["version"],
            kappa=float(info["kappa"]),
            env_now=float(info["env_now"]),
            env_mean=float(info["env_mean"]),
            env_std=float(info["env_std"]),
            terms=repo.terms(db),
        )
    model: BallModel = db.cache["ball_model"]
    return model


# --------------------------------------------------------------------------- numbers


def _ci(mean: float, sd: float, scale: float = 1.0, digits: int = 1) -> Interval:
    return Interval(
        value=round(scale * mean, digits),
        low=round(scale * max(mean - Z90 * sd, 0.0), digits),
        high=round(scale * (mean + Z90 * sd), digits),
    )


def _balls_per(rate: float, sd: float) -> Interval:
    """Balls per dismissal (1 / rate), with the rate's interval inverted."""
    low_rate, high_rate = max(rate - Z90 * sd, 0.0), rate + Z90 * sd
    return Interval(
        value=round(1 / rate, 1) if rate > 0 else None,
        low=round(1 / high_rate, 1) if high_rate > 0 else None,
        high=round(1 / low_rate, 1) if low_rate > 0 else None,
    )


def _numbers(
    mean: list[float], effective_n: float, runs_per_ball: float | None = None
) -> MatchupNumbers:
    """Summaries of an outcome distribution whose uncertainty is worth ``effective_n`` balls.

    ``runs_per_ball`` overrides the mean when actual runs are known: the outcome
    classes count the rare five as three.
    """
    runs = sum(r * p for r, p in zip(RUNS, mean, strict=True))
    runs_sq = sum(r * r * p for r, p in zip(RUNS, mean, strict=True))
    n = max(effective_n, 1e-9)
    sr_sd = math.sqrt(max(runs_sq - runs * runs, 0.0) / n)

    def share(p: float) -> Interval:
        return _ci(p, math.sqrt(p * (1 - p) / n), 100)

    out = mean[OUT]
    return MatchupNumbers(
        strike_rate=_ci(runs if runs_per_ball is None else runs_per_ball, sr_sd, 100),
        balls_per_dismissal=_balls_per(out, math.sqrt(out * (1 - out) / n)),
        dot_pct=share(mean[DOT]),
        boundary_pct=share(sum(mean[i] for i in BOUNDARY)),
    )


def _counts(rows: list[Row]) -> tuple[list[float], list[float], int, int]:
    n = [float(sum(r[f"n_{c}"] for r in rows)) for c in CLASSES]
    e = [float(sum(r[f"e_{c}"] for r in rows)) for c in CLASSES]
    return n, e, sum(r["balls"] for r in rows), sum(r["runs"] for r in rows)


def _posterior(n: list[float], e: list[float], kappa: float) -> tuple[list[float], list[float]]:
    """Posterior mean outcome distribution, and the model's own distribution for these balls."""
    total = sum(n)
    q = [x / total for x in e]
    return [(n_c + kappa * q_c) / (total + kappa) for n_c, q_c in zip(n, q, strict=True)], q


def sample_level(balls: int) -> SampleLevel:
    if balls == 0:
        return "none"
    if balls < 30:
        return "tiny"
    if balls < 100:
        return "small"
    if balls < 300:
        return "moderate"
    return "large"


def _player(row: Row) -> MatchupPlayer:
    team = (
        TeamTag(franchise_id=row["latest_team_id"], name=row["team_name"], color=row["team_color"])
        if row["latest_team_id"]
        else None
    )
    return MatchupPlayer(
        player_id=row["player_id"],
        name=row["name"],
        full_name=row["full_name"],
        batting_hand=row["batting_hand"],
        bowling_type=row["bowling_type"],
        bowling_style=row["bowling_style"],
        team=team,
    )


def _sr(runs: float, balls: float) -> float | None:
    return round(100 * runs / balls, 1) if balls else None


def _expected_sr(e: list[float]) -> float | None:
    balls = sum(e)
    return _sr(sum(r * x for r, x in zip(RUNS, e, strict=True)), balls)


def _phase_labels() -> dict[str, str]:
    phases = sorted(default_phase_config().for_format("T20").phases, key=lambda p: p.first_over)
    return {p.key: p.label for p in phases}


def _outcomes(probs: list[float]) -> list[OutcomeProbability]:
    return [
        OutcomeProbability(outcome=c, label=LABELS[c], probability=round(p, 4))  # type: ignore[arg-type]
        for c, p in zip(CLASSES, probs, strict=True)
    ]


def _adjust(probs: list[float], ratio: list[float] | None) -> list[float]:
    if ratio is None:
        return probs
    adjusted = [p * r for p, r in zip(probs, ratio, strict=True)]
    total = sum(adjusted)
    return [a / total for a in adjusted]


def _expected_runs(probs: list[float]) -> float:
    return round(sum(r * p for r, p in zip(RUNS, probs, strict=True)), 3)


def _matchup_key(batter: Row, bowler: Row) -> str:
    return f"{batter['batting_hand']}_{bowler['bowling_type']}"


# --------------------------------------------------------------------------- detail


def get_matchup(
    db: Database,
    batter_id: str,
    bowler_id: str,
    first: int | None = None,
    last: int | None = None,
    phase: Phase | None = None,
) -> MatchupDetail:
    model = ball_model(db)
    if model is None:
        raise MatchupUnavailableError("the ball-outcome model has not been scored")
    batter, bowler = repo.player(db, batter_id), repo.player(db, bowler_id)
    if batter is None or bowler is None:
        raise PlayerNotFoundError(batter_id if batter is None else bowler_id)
    window: SeasonWindow = resolve_window(db, first, last)
    all_cells = repo.cells(db, batter_id, bowler_id, window.first, window.last)
    cells = [r for r in all_cells if phase is None or r["phase"] == phase]
    n, e, balls, runs = _counts(cells)
    kappa = model.kappa

    raw = expected = estimate = None
    ratio: list[float] | None = None
    if balls:
        raw = _numbers([x / balls for x in n], balls, runs / balls)
        posterior, q = _posterior(n, e, kappa)
        expected = _numbers(q, 1e9)
        estimate = _numbers(posterior, balls + kappa + 1)
        ratio = [m / max(p, 1e-12) for m, p in zip(posterior, q, strict=True)]

    labels = _phase_labels()
    by_phase = []
    for key, label in labels.items():
        rows = [r for r in all_cells if r["phase"] == key]
        if not rows:
            continue
        pn, pe, pb, pr = _counts(rows)
        by_phase.append(
            MatchupSplitRow(
                key=key,
                label=label,
                balls=pb,
                runs=pr,
                dismissals=int(pn[OUT]),
                strike_rate=_sr(pr, pb),
                expected_strike_rate=_expected_sr(pe),
            )
        )
    by_season = []
    for season in sorted({r["season"] for r in cells}):
        rows = [r for r in cells if r["season"] == season]
        sn, se, sb, srn = _counts(rows)
        by_season.append(
            MatchupSplitRow(
                key=str(season),
                label=str(season),
                balls=sb,
                runs=srn,
                dismissals=int(sn[OUT]),
                strike_rate=_sr(srn, sb),
                expected_strike_rate=_expected_sr(se),
            )
        )

    matchup = _matchup_key(batter, bowler)
    next_ball = []
    for key, label in labels.items():
        probs = model.probabilities(
            batter_id=batter_id,
            bowler_id=bowler_id,
            phase=key,
            innings=1,
            wickets=DEFAULT_WICKETS,
            batter_balls=DEFAULT_BATTER_BALLS,
            matchup=matchup,
            pressure="none",
        )
        adjusted = _adjust(probs, ratio)
        next_ball.append(
            NextBall(
                phase=key,  # type: ignore[arg-type]
                label=label,
                model=_outcomes(probs),
                with_history=_outcomes(adjusted),
                expected_runs=_expected_runs(probs),
                expected_runs_with_history=_expected_runs(adjusted),
            )
        )

    return MatchupDetail(
        batter=_player(batter),
        bowler=_player(bowler),
        window=window,
        phase=phase,
        head_to_head=HeadToHead(
            balls=balls,
            runs=runs,
            dismissals=int(n[OUT]),
            dots=int(n[DOT]),
            fours=int(n[CLASSES.index("four")]),
            sixes=int(n[CLASSES.index("six")]),
            average=round(runs / n[OUT], 1) if n[OUT] else None,
        ),
        raw=raw,
        expected=expected,
        estimate=estimate,
        sample=SampleSize(
            balls=balls,
            level=sample_level(balls),
            weight=round(balls / (balls + kappa), 4),
            kappa=round(kappa, 1),
        ),
        by_phase=by_phase,
        by_season=by_season,
        dismissals=[
            MatchupDismissal(**r)
            for r in repo.dismissals(db, batter_id, bowler_id, window.first, window.last, phase)
        ],
        next_ball=next_ball,
        context=(
            "First innings, two or three wickets down, the batter set on 16 to 30 balls, "
            "at the current scoring rate."
        ),
        model_version=model.version,
    )


# --------------------------------------------------------------------------- lists


def list_matchups(
    db: Database,
    *,
    batter_id: str | None,
    bowler_id: str | None,
    first: int | None,
    last: int | None,
    min_balls: int,
    sort: MatchupSort,
    page: int,
    page_size: int,
) -> MatchupList:
    model = ball_model(db)
    if model is None:
        raise MatchupUnavailableError("the ball-outcome model has not been scored")
    window = resolve_window(db, first, last)
    rows, total = repo.list_pairs(
        db,
        batter_id=batter_id,
        bowler_id=bowler_id,
        first=window.first,
        last=window.last,
        min_balls=min_balls,
        sort=sort,
        kappa=model.kappa,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    people: dict[str, MatchupPlayer] = {}

    def person(player_id: str) -> MatchupPlayer:
        if player_id not in people:
            row = repo.player(db, player_id)
            assert row is not None
            people[player_id] = _player(row)
        return people[player_id]

    items = []
    for r in rows:
        n = [float(r[f"n_{c}"]) for c in CLASSES]
        e = [float(r[f"e_{c}"]) for c in CLASSES]
        posterior, _ = _posterior(n, e, model.kappa)
        items.append(
            MatchupListItem(
                batter=person(r["batter_id"]),
                bowler=person(r["bowler_id"]),
                balls=r["balls"],
                runs=r["runs"],
                dismissals=int(n[OUT]),
                strike_rate=_sr(r["runs"], r["balls"]),
                expected_strike_rate=_expected_sr(e),
                estimated_strike_rate=round(
                    100 * sum(x * p for x, p in zip(RUNS, posterior, strict=True)), 1
                ),
                edge=round(float(r["edge"]), 1),
                weight=round(r["balls"] / (r["balls"] + model.kappa), 4),
            )
        )
    return MatchupList(items=items, total=total, kappa=round(model.kappa, 1))


# --------------------------------------------------------------------------- next ball


def predict_next_ball(db: Database, request: NextBallRequest) -> NextBallResponse:
    model = ball_model(db)
    if model is None:
        raise MatchupUnavailableError("the ball-outcome model has not been scored")
    batter, bowler = repo.player(db, request.batter_id), repo.player(db, request.bowler_id)
    if batter is None or bowler is None:
        raise PlayerNotFoundError(request.batter_id if batter is None else request.bowler_id)
    probs = model.probabilities(
        batter_id=request.batter_id,
        bowler_id=request.bowler_id,
        phase=request.phase,
        innings=request.innings,
        wickets=request.wickets,
        batter_balls=request.batter_balls,
        matchup=_matchup_key(batter, bowler),
        pressure=request.pressure or "par",
    )
    career = resolve_window(db, None, None)
    n, e, balls, _ = _counts(
        repo.cells(db, request.batter_id, request.bowler_id, career.first, career.last)
    )
    ratio = None
    if balls:
        posterior, q = _posterior(n, e, model.kappa)
        ratio = [m / max(p, 1e-12) for m, p in zip(posterior, q, strict=True)]
    adjusted = _adjust(probs, ratio)
    return NextBallResponse(
        batter=_player(batter),
        bowler=_player(bowler),
        request=request,
        model=_outcomes(probs),
        with_history=_outcomes(adjusted),
        expected_runs=_expected_runs(probs),
        expected_runs_with_history=_expected_runs(adjusted),
        history_balls=balls,
        model_version=model.version,
    )
