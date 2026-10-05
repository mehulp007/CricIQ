"""Team form and match-up expectations, shared by the API and the Analytics Lab.

A side's form is its win rate over its previous matches (``team_matches.form_won``
of ``form_decided``), shrunk toward an even record as if it had also played
``FORM_PRIOR`` matches at 50%. T20 results are noisy: on every IPL match since
2008, the shrinkage that predicts results best is about 80 matches, and even
then the side in better form wins only about 53% of the time (see the Analytics
Lab note on rivalries).
"""

from __future__ import annotations

FORM_PRIOR = 80


def form_probability(won: int, decided: int, prior: float = FORM_PRIOR) -> float:
    """Shrunk win rate from recent results."""
    return (won + prior / 2) / (decided + prior)


def log5(p_a: float, p_b: float) -> float:
    """Chance A beats B, given each side's chance of beating an average side."""
    num = p_a * (1 - p_b)
    den = num + p_b * (1 - p_a)
    return num / den if den else 0.5
