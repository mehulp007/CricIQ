"""The fourth-innings chase what-if and the chase calculator (Tests).

From any ball of a Test's fourth innings, change the runs needed, the wickets in
hand or the overs left, and the Test win probability model (published with the
scored data: ``models.info.terms``) gives the chasing side's chances of winning,
drawing and losing from the edited state. The context of the match (the sides'
ratings, home advantage) stays as it was. The model is plain arithmetic
(``criciq_core.test_win_probability``), so it runs here without an ML library.

The calculator sets a chase up from scratch between any two sides: their ratings
and the scoring era are as they stood after the last Test (``models.info.now``),
and context the model has no value for (the XIs) is taken as level.
"""

from __future__ import annotations

from typing import Any

from criciq_api.db import Database
from criciq_api.repositories import matches as repo
from criciq_api.schemas.matches import (
    ChaseCalculation,
    ChaseOutcome,
    ChaseSide,
    ChaseSides,
    ChaseWhatIf,
    TeamRef,
)
from criciq_core.test_win_probability import (
    AVERAGE_BATTER,
    OUTCOMES,
    SCHEDULED_OVERS,
    InningsTerms,
)


class ChaseUnavailableError(LookupError):
    """No chase what-if here: not a Test, not scored, or no such fourth-innings ball."""


def _terms(db: Database) -> InningsTerms:
    key = "chase:terms"
    if key not in db.cache:
        model = repo.get_model(db, "win_probability")
        terms = (model or {}).get("terms", {}).get("4")
        if terms is None:
            raise ChaseUnavailableError("no Test win probability model in this data")
        db.cache[key] = InningsTerms.from_json(terms)
    found: InningsTerms = db.cache[key]
    return found


def _now(db: Database) -> dict[str, Any]:
    model = repo.get_model(db, "win_probability") or {}
    now: dict[str, Any] = model.get("now") or {}
    if not now:
        raise ChaseUnavailableError("no ratings in this data")
    return now


def _version(db: Database) -> str:
    return str((repo.get_model(db, "win_probability") or {}).get("version", ""))


def sides(db: Database) -> ChaseSides:
    """The Test sides, best rated first."""
    if db.match_format != "Test":
        raise ChaseUnavailableError("the chase calculator is for Tests")
    _terms(db)
    now = _now(db)
    ratings: dict[str, float] = now.get("ratings", {})
    rows = db.rows("SELECT franchise_id, name, primary_color AS color FROM franchises")
    found = [ChaseSide(**r, rating=ratings.get(r["franchise_id"])) for r in rows]
    found.sort(key=lambda s: (s.rating is None, -(s.rating or 0), s.name))
    return ChaseSides(sides=found, as_of=now.get("as_of"), model_version=_version(db))


# Targets the calculator's curve shows the chase at.
CURVE_STEP = 10
CURVE_MAX = 600


def calculate(
    db: Database,
    batting: str,
    fielding: str,
    venue: str,
    runs_needed: int,
    wickets_in_hand: int,
    overs_left: float,
) -> ChaseCalculation:
    if db.match_format != "Test":
        raise ChaseUnavailableError("the chase calculator is for Tests")
    terms = _terms(db)
    now = _now(db)
    ratings: dict[str, float] = now.get("ratings", {})
    if batting not in ratings or fielding not in ratings or batting == fielding:
        raise ChaseUnavailableError("pick two different Test sides")
    wickets = min(max(int(wickets_in_hand), 1), 10)
    state: dict[str, Any] = {
        "runs_needed": max(int(runs_needed), 1),
        "wickets_in_hand": wickets,
        "overs_left": min(max(float(overs_left), 0.0), SCHEDULED_OVERS),
        "env_rpw": float(now["env_rpw"]),
        "elo_diff": float(ratings[batting]) - float(ratings[fielding]),
        "home": {"home": 1.0, "away": -1.0}.get(venue, 0.0),
        # The XIs are unknown: level sides, and average batting still to come.
        "bat_xi_own": 0.0,
        "bat_xi_opp": 0.0,
        "bowl_xi_own": 0.0,
        "bowl_xi_opp": 0.0,
        "bat_left": AVERAGE_BATTER * wickets,
    }
    state["required_rpo"] = state["runs_needed"] / max(state["overs_left"], 1.0)
    curve = [
        _outcome(terms, edited_state(state, needed, None, None))
        for needed in range(CURVE_STEP, CURVE_MAX + 1, CURVE_STEP)
    ]
    return ChaseCalculation(
        batting=batting,
        fielding=fielding,
        venue=venue if venue in ("home", "away") else "neutral",  # type: ignore[arg-type]
        outcome=_outcome(terms, state),
        by_runs_needed=curve,
        model_version=_version(db),
    )


def _outcome(terms: InningsTerms, state: dict[str, Any]) -> ChaseOutcome:
    raw = {k: [v] for k, v in state.items()}
    p = terms.probabilities(raw)[0]
    chances = {name: round(float(p[k]), 4) for k, name in enumerate(OUTCOMES)}
    return ChaseOutcome(
        runs_needed=int(state["runs_needed"]),
        wickets_in_hand=int(state["wickets_in_hand"]),
        overs_left=round(float(state["overs_left"]), 1),
        won=chances["won"],
        drawn=chances["drawn"],
        lost=chances["lost"],
    )


def edited_state(
    state: dict[str, Any],
    runs_needed: int | None,
    wickets_in_hand: int | None,
    overs_left: float | None,
) -> dict[str, Any]:
    """The state with the edits applied, its derived values kept consistent."""
    out = dict(state)
    if runs_needed is not None:
        out["runs_needed"] = max(int(runs_needed), 1)
    if wickets_in_hand is not None:
        wickets = min(max(int(wickets_in_hand), 1), 10)
        if "bat_left" in out:
            # Each wicket taken or given back is worth an average batter's strength.
            change = wickets - int(state["wickets_in_hand"])
            out["bat_left"] = max(float(state["bat_left"]) + AVERAGE_BATTER * change, 0.0)
        out["wickets_in_hand"] = wickets
    if overs_left is not None:
        out["overs_left"] = min(max(float(overs_left), 0.0), SCHEDULED_OVERS)
    out["required_rpo"] = out["runs_needed"] / max(float(out["overs_left"]), 1.0)
    return out


def what_if(
    db: Database,
    match_id: int,
    seq_no: int,
    runs_needed: int | None = None,
    wickets_in_hand: int | None = None,
    overs_left: float | None = None,
) -> ChaseWhatIf:
    if db.match_format != "Test" or not db.has_table("chase_states"):
        raise ChaseUnavailableError("the chase what-if is for Tests")
    terms = _terms(db)
    row = db.row(
        "SELECT * FROM chase_states WHERE match_id = ? AND innings_no = 4 AND seq_no = ?",
        [match_id, seq_no],
    )
    if row is None:
        raise ChaseUnavailableError(f"no fourth-innings ball {seq_no} in match {match_id}")
    real = {k: v for k, v in row.items() if k not in ("match_id", "innings_no", "seq_no")}
    if int(real["runs_needed"]) <= 0:
        raise ChaseUnavailableError("the target had been reached")
    batting = db.row(
        """
        SELECT t.team_season_id, f.franchise_id, t.display_name AS name, f.primary_color AS color
        FROM innings i
        JOIN team_seasons t ON t.team_season_id = i.batting_team_id
        JOIN franchises f USING (franchise_id)
        WHERE i.match_id = ? AND i.innings_no = 4
        """,
        [match_id],
    )
    assert batting is not None
    return ChaseWhatIf(
        match_id=match_id,
        seq_no=seq_no,
        batting_team=TeamRef(**batting),
        real=_outcome(terms, real),
        edited=_outcome(terms, edited_state(real, runs_needed, wickets_in_hand, overs_left)),
        model_version=str((repo.get_model(db, "win_probability") or {}).get("version", "")),
    )
