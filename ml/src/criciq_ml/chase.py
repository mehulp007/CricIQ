"""A WASP-style dynamic programme for the end of a chase.

``V[w, b, r]`` is the chasing side's chance of winning (a tie counts as half)
when it needs ``r`` runs from ``b`` legal balls with ``w`` wickets in hand, if
every ball is drawn from the same outcome distribution: a wide or no-ball (one
run, ball bowled again), 0, 1, 2, 3, 4 or 6 runs, or a wicket. It is exact for
that simplified game, so it is sharp exactly where tree models are coarse (the
last few balls, where data is thin) and it knows that 13 off the last ball is
impossible.

The outcome rates come from the death overs (16-20) of the previous seasons
only, so the table used for a season never sees that season.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.signal import lfilter

RUN_OUTCOMES = (0, 1, 2, 3, 4, 6)
MAX_RUNS = 300
MAX_BALLS = 120
# Wickets in hand -> rate bucket: tail-enders score slower and get out more.
BUCKETS = ((1, 2), (3, 4), (5, 10))

Table = NDArray[np.float32]


@dataclass(frozen=True)
class OutcomeRates:
    extra: float
    wicket: float
    runs: dict[int, float]

    def normalized(self) -> OutcomeRates:
        total = self.extra + self.wicket + sum(self.runs.values())
        return OutcomeRates(
            self.extra / total, self.wicket / total, {k: v / total for k, v in self.runs.items()}
        )


# Used before any IPL history exists (typical T20 death-over rates).
PRIOR = OutcomeRates(
    extra=0.06,
    wicket=0.08,
    runs={0: 0.28, 1: 0.33, 2: 0.08, 3: 0.005, 4: 0.10, 6: 0.065},
).normalized()


def estimate_rates(deliveries: pd.DataFrame) -> dict[int, OutcomeRates]:
    """Outcome rates per wickets-in-hand bucket from death-over deliveries.

    Expects ``over_no`` (0-based), ``is_legal``, ``runs_batter``, ``team_wickets``
    and ``out_ids`` columns. Buckets with little data fall back to the prior.
    """
    death = deliveries[deliveries["over_no"] >= 15]
    outs = death["out_ids"].map(len).to_numpy()
    in_hand = 10 - (death["team_wickets"].to_numpy() - outs)
    legal = death["is_legal"].to_numpy()
    runs = np.minimum(death["runs_batter"].to_numpy(), 6)
    runs = np.where(runs == 5, 4, runs)
    rates = {}
    for low, high in BUCKETS:
        mask = (in_hand >= low) & (in_hand <= high)
        n = int(mask.sum())
        if n < 500:
            rates[low] = PRIOR
            continue
        extra = float((~legal[mask]).sum()) / n
        wicket_mask = mask & legal & (outs > 0)
        wicket = float(wicket_mask.sum()) / n
        scoring = mask & legal & (outs == 0)
        by_runs = {k: float((scoring & (runs == k)).sum()) / n for k in RUN_OUTCOMES}
        rates[low] = OutcomeRates(extra, wicket, by_runs).normalized()
    return rates


def _rates_for(rates: dict[int, OutcomeRates], wickets_in_hand: int) -> OutcomeRates:
    for low, high in BUCKETS:
        if low <= wickets_in_hand <= high:
            return rates[low]
    raise ValueError(wickets_in_hand)


def solve(rates: dict[int, OutcomeRates]) -> Table:
    """``V[w, b, r]`` for w in 0..10, b in 0..MAX_BALLS, r in 0..MAX_RUNS."""
    r = np.arange(MAX_RUNS + 1)
    terminal = np.where(r == 0, 1.0, np.where(r == 1, 0.5, 0.0))
    table = np.zeros((11, MAX_BALLS + 1, MAX_RUNS + 1))
    table[0, :, :] = terminal
    table[:, 0, :] = terminal
    for w in range(1, 11):
        rw = _rates_for(rates, w)
        for b in range(1, MAX_BALLS + 1):
            prev = table[w, b - 1]
            fall = table[w - 1, b - 1]
            s = rw.wicket * fall
            for k, p in rw.runs.items():
                s = s + p * prev[np.maximum(r - k, 0)]
            # V[r] = extra * V[r-1] + s[r] for r >= 1, with V[0] = 1: a first-order recurrence.
            v = np.empty(MAX_RUNS + 1)
            v[0] = 1.0
            v[1:], _ = lfilter([1.0], [1.0, -rw.extra], s[1:], zi=[rw.extra * 1.0])
            table[w, b] = v
    return table.astype(np.float32)


def lookup(table: Table, runs_needed: int, balls_left: int, wickets_lost: int) -> float:
    w = min(max(10 - wickets_lost, 0), 10)
    b = min(max(balls_left, 0), MAX_BALLS)
    r = min(max(runs_needed, 0), MAX_RUNS)
    return float(table[w, b, r])


class SeasonTables:
    """One DP table per season, from the death overs of the previous three seasons."""

    def __init__(self, deliveries: pd.DataFrame, seasons: pd.Series, window: int = 3) -> None:
        self._deliveries = deliveries.assign(season=seasons.to_numpy())
        self._window = window
        self._cache: dict[int, Table] = {}

    def for_season(self, season: int) -> Table:
        if season not in self._cache:
            d = self._deliveries
            history = d[(d["season"] < season) & (d["season"] >= season - self._window)]
            if len(history) < 5_000:
                rates = {low: PRIOR for low, _ in BUCKETS}
            else:
                rates = estimate_rates(history)
            self._cache[season] = solve(rates)
        return self._cache[season]
