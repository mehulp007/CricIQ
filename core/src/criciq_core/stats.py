"""Cricket statistics, defined once for the API, the records and the chart studio.

The definitions the About page states: batting average is runs per dismissal,
strike rate is runs per 100 balls faced, economy is runs per six legal balls,
bowling average is runs conceded per wicket and bowling strike rate is legal balls
per wicket. A rate with nothing to divide by (no dismissals, no balls) is ``None``,
never zero or infinity. Rates are rounded to two decimals, percentages to one.

The ``sql_*`` builders give the same definitions as DuckDB expressions over summed
columns, so a figure computed in SQL equals the one computed here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

RATE_DIGITS = 2
PERCENT_DIGITS = 1


def ratio(
    num: float | None, den: float | None, scale: float = 1.0, digits: int = RATE_DIGITS
) -> float | None:
    """``scale * num / den`` rounded, or ``None`` without a denominator."""
    if num is None or not den:
        return None
    return round(scale * num / den, digits)


def batting_average(runs: float | None, outs: float | None) -> float | None:
    return ratio(runs, outs)


def strike_rate(runs: float | None, balls: float | None) -> float | None:
    return ratio(runs, balls, 100)


def economy(runs: float | None, balls: float | None) -> float | None:
    return ratio(runs, balls, 6)


def bowling_average(runs: float | None, wickets: float | None) -> float | None:
    return ratio(runs, wickets)


def bowling_strike_rate(balls: float | None, wickets: float | None) -> float | None:
    return ratio(balls, wickets)


def balls_per_wicket(balls: float | None, wickets: float | None) -> float | None:
    return ratio(balls, wickets)


def percent(count: float | None, balls: float | None) -> float | None:
    """A share of balls (dots, boundaries) as a percentage."""
    return ratio(count, balls, 100, PERCENT_DIGITS)


def run_rate(runs: float | None, balls: float | None) -> float | None:
    """Runs per six legal balls (an innings' or a phase's scoring rate)."""
    return ratio(runs, balls, 6)


def per(total: float | None, count: float | None) -> float | None:
    """An average per innings, match or over (runs per innings, wickets per innings)."""
    return ratio(total, count)


# --------------------------------------------------------------------------- SQL


def sql_ratio(num: str, den: str, scale: float = 1.0, digits: int = RATE_DIGITS) -> str:
    """The DuckDB form of ``ratio``: NULL without a denominator."""
    factor = "" if scale == 1.0 else f"{scale:g} * "
    return f"round({factor}({num}) / nullif({den}, 0), {digits})"


def sql_batting_average(runs: str = "runs", outs: str = "outs") -> str:
    return sql_ratio(runs, outs)


def sql_strike_rate(runs: str = "runs", balls: str = "balls") -> str:
    return sql_ratio(runs, balls, 100)


def sql_economy(runs: str = "runs", balls: str = "balls") -> str:
    return sql_ratio(runs, balls, 6)


def sql_bowling_average(runs: str = "runs", wickets: str = "wickets") -> str:
    return sql_ratio(runs, wickets)


def sql_bowling_strike_rate(balls: str = "balls", wickets: str = "wickets") -> str:
    return sql_ratio(balls, wickets)


def sql_percent(count: str, balls: str = "balls") -> str:
    return sql_ratio(count, balls, 100, PERCENT_DIGITS)


def sql_run_rate(runs: str = "runs", balls: str = "balls") -> str:
    return sql_ratio(runs, balls, 6)


# --------------------------------------------------------------------------- ranks


def ranks[T](rows: Sequence[T], value: Callable[[T], float | int | None]) -> list[tuple[int, bool]]:
    """Each row's rank in already-sorted ``rows``, and whether it is shared.

    Equal values share a rank and the next one skips ("1, 2, 2, 4"), as record
    tables are read. Rows without a value never tie with each other.
    """
    found: list[tuple[int, bool]] = []
    for index, row in enumerate(rows):
        current = value(row)
        if index and current is not None and current == value(rows[index - 1]):
            found.append((found[-1][0], True))
        else:
            found.append((index + 1, False))
    # The first row of a tie is shared too.
    for index in range(len(found) - 1):
        if found[index + 1][1] and found[index + 1][0] == found[index][0]:
            found[index] = (found[index][0], True)
    return found
