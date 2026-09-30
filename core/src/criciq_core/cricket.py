"""Basic cricket arithmetic shared by pipelines, models and the API.

All functions work on *legal* balls (wides and no-balls excluded), which is the
only safe unit: raw delivery counts break on extras and on the occasional
umpire-miscounted 7-ball over.
"""

from __future__ import annotations

import math


def overs_notation(legal_balls: int, balls_per_over: int = 6) -> str:
    """Legal balls -> scoreboard overs, e.g. 99 -> "16.3"."""
    if legal_balls < 0:
        raise ValueError("legal_balls must be non-negative")
    completed, remainder = divmod(legal_balls, balls_per_over)
    return f"{completed}.{remainder}"


def legal_balls_from_overs(overs: str | float, balls_per_over: int = 6) -> int:
    """Scoreboard overs -> legal balls, e.g. "16.3" -> 99.

    Accepts the string form to avoid float surprises ("16.3" is 16 overs and
    3 balls, not 16.3 overs).
    """
    text = str(overs)
    whole, _, part = text.partition(".")
    completed = int(whole)
    balls = int(part) if part else 0
    if completed < 0 or not 0 <= balls < balls_per_over:
        raise ValueError(f"invalid overs notation: {text!r}")
    return completed * balls_per_over + balls


def run_rate(runs: int, legal_balls: int, balls_per_over: int = 6) -> float | None:
    """Runs per over; ``None`` before the first legal ball."""
    if legal_balls <= 0:
        return None
    return runs * balls_per_over / legal_balls


def required_run_rate(
    runs_needed: int, balls_remaining: int, balls_per_over: int = 6
) -> float | None:
    """Runs per over still required; ``None`` once the chase is decided."""
    if runs_needed <= 0:
        return None
    if balls_remaining <= 0:
        return math.inf
    return runs_needed * balls_per_over / balls_remaining
