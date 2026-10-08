"""The Test win probability model's features and arithmetic.

Shared by the models package, which fits the model, and the API, which runs it
for the fourth-innings chase what-if, so both compute exactly the same thing
with plain numpy (the API imports no ML library).

The model is a multinomial logistic regression per innings over three
outcomes for the batting side: lost, drawn, won (in that order). Its features
are the match state (the baseline's) plus groups of context known before the
match, each entered as itself and scaled by the share of the match still to
play (a side's strength matters more with more time left):

* ``teams``: the sides' rating difference from earlier Tests (Elo style).
* ``home``: +1 when the batting side is at home, -1 when the fielding side is.
* ``xis``: the XIs' Test records (batting and bowling strength differences).
* ``batting_left``: the batting still to come, beyond what wickets in hand say.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

# The batting side's outcomes, in the order of every probability triple.
OUTCOMES = ("lost", "drawn", "won")
GROUPS = ("teams", "home", "xis", "batting_left")
# Five days of 90 overs.
SCHEDULED_OVERS = 450.0
# An average batter's share of the XI's batting strength (states.bat_left).
AVERAGE_BATTER = 0.75


def _col(raw: Mapping[str, Any], name: str) -> FloatArray:
    return np.asarray(raw[name], dtype=np.float64).reshape(-1)


def state_columns(innings_no: int) -> list[str]:
    """The raw columns the match state features are built from."""
    if innings_no == 4:
        return ["runs_needed", "required_rpo", "wickets_in_hand", "overs_left", "env_rpw"]
    return ["lead", "wickets_in_hand", "overs_left", "env_rpw"]


GROUP_COLUMNS: dict[str, list[str]] = {
    "teams": ["elo_diff"],
    "home": ["home"],
    "xis": ["bat_xi_own", "bat_xi_opp", "bowl_xi_own", "bowl_xi_opp"],
    "batting_left": ["bat_left", "wickets_in_hand"],
}


def columns(innings_no: int, groups: Sequence[str]) -> list[str]:
    """Every raw column a model of these groups needs."""
    found = state_columns(innings_no) + [c for g in groups for c in GROUP_COLUMNS[g]]
    return list(dict.fromkeys(found))


def state_design(raw: Mapping[str, Any], innings_no: int) -> tuple[FloatArray, list[str]]:
    """The match state, with a few interactions (the baseline's features)."""
    wickets = _col(raw, "wickets_in_hand")
    left = _col(raw, "overs_left")
    era = _col(raw, "env_rpw")
    if innings_no == 4:
        needed = _col(raw, "runs_needed")
        cols = {
            "runs_needed": needed,
            "log_runs_needed": np.log1p(needed),
            "required_rpo": np.minimum(_col(raw, "required_rpo"), 20.0),
            "wickets_in_hand": wickets,
            "overs_left": left,
            "log_overs_left": np.log1p(left),
            "wickets_x_overs": wickets * left / 90,
            "needed_x_wickets": needed * wickets / 100,
            "era_rpw": era,
        }
    else:
        lead = _col(raw, "lead")
        cols = {
            "lead": lead,
            "wickets_in_hand": wickets,
            "overs_left": left,
            "log_overs_left": np.log1p(left),
            "lead_x_overs": lead * left / SCHEDULED_OVERS,
            "wickets_x_overs": wickets * left / 90,
            "era_rpw": era,
        }
    return np.column_stack(list(cols.values())), list(cols)


def group_design(raw: Mapping[str, Any], group: str) -> tuple[FloatArray, list[str]]:
    """One context group: each term and the term scaled by the share of time left."""
    share = _col(raw, "overs_left") / SCHEDULED_OVERS
    if group == "teams":
        terms = {"rating": _col(raw, "elo_diff") / 400}
    elif group == "home":
        terms = {"home": _col(raw, "home")}
    elif group == "xis":
        terms = {
            "batting_xi": _col(raw, "bat_xi_own") - _col(raw, "bat_xi_opp"),
            "bowling_xi": _col(raw, "bowl_xi_own") - _col(raw, "bowl_xi_opp"),
        }
    elif group == "batting_left":
        terms = {
            "batting_left": _col(raw, "bat_left") - AVERAGE_BATTER * _col(raw, "wickets_in_hand")
        }
    else:
        raise KeyError(f"unknown context group {group!r}")
    names, cols = [], []
    for name, values in terms.items():
        names += [name, f"{name}_x_time"]
        cols += [values, values * share]
    return np.column_stack(cols), names


def design(
    raw: Mapping[str, Any], innings_no: int, groups: Sequence[str]
) -> tuple[FloatArray, list[str]]:
    """The model's features: the match state, then each context group."""
    x, names = state_design(raw, innings_no)
    blocks = [x]
    for group in groups:
        g, more = group_design(raw, group)
        blocks.append(g)
        names = names + more
    return np.column_stack(blocks), names


@dataclass(frozen=True)
class InningsTerms:
    """One innings' fitted model: standardisation and multinomial coefficients."""

    innings_no: int
    groups: tuple[str, ...]
    names: tuple[str, ...]
    mean: FloatArray
    scale: FloatArray
    coef: FloatArray  # (3, features): lost, drawn, won
    intercept: FloatArray  # (3,)

    def probabilities(self, raw: Mapping[str, Any]) -> FloatArray:
        """(lost, drawn, won) for the batting side of every row of ``raw``."""
        x, names = design(raw, self.innings_no, self.groups)
        if tuple(names) != self.names:
            raise ValueError("these terms were fitted on other features")
        z = (x - self.mean) / self.scale
        logits = z @ self.coef.T + self.intercept
        logits -= logits.max(axis=1, keepdims=True)
        e = np.exp(logits)
        out: FloatArray = e / e.sum(axis=1, keepdims=True)
        return out

    def to_json(self) -> dict[str, Any]:
        return {
            "innings_no": self.innings_no,
            "groups": list(self.groups),
            "names": list(self.names),
            "mean": [round(float(v), 8) for v in self.mean],
            "scale": [round(float(v), 8) for v in self.scale],
            "coef": [[round(float(v), 8) for v in row] for row in self.coef],
            "intercept": [round(float(v), 8) for v in self.intercept],
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> InningsTerms:
        return cls(
            innings_no=int(data["innings_no"]),
            groups=tuple(data["groups"]),
            names=tuple(data["names"]),
            mean=np.asarray(data["mean"], dtype=np.float64),
            scale=np.asarray(data["scale"], dtype=np.float64),
            coef=np.asarray(data["coef"], dtype=np.float64),
            intercept=np.asarray(data["intercept"], dtype=np.float64),
        )
