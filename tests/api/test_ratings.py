"""CricIQ Ratings and similar players in the API.

The fixture matches are too few for anyone to reach the real thresholds, so
these tests lower them to exercise the ranking and similarity logic.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from criciq_api.db import Database
from criciq_api.schemas.players import SeasonWindow
from criciq_api.services import ratings as service
from criciq_core import ratings as core
from criciq_core import style


@pytest.fixture
def db(fixture_scored_serving_db: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    lowered = tuple(
        dataclasses.replace(c, qualify=min(c.qualify, 5), show=min(c.show, 3))
        for c in core.components()
    )
    monkeypatch.setattr(core, "components", lambda: lowered)
    monkeypatch.setattr(service, "MIN_BALLS", 40)
    monkeypatch.setattr(service, "MIN_RATED_BALLS", 10)
    monkeypatch.setattr(style, "MIN_BALLS", 40)
    monkeypatch.setattr(style, "MIN_PROFILE_BALLS", 20)
    database = Database(fixture_scored_serving_db)
    yield database
    database.close()


def _window(db: Database) -> SeasonWindow:
    first, last = db.row("SELECT min(year) AS f, max(year) AS l FROM seasons").values()  # type: ignore[union-attr]
    return SeasonWindow(first=first, last=last)


def test_percentile_counts_ties_half_and_leaves_the_player_out() -> None:
    reference = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert service.percentile(5.0, reference, exclude=5.0) == 100
    assert service.percentile(1.0, reference, exclude=1.0) == 0
    assert service.percentile(3.0, reference, exclude=3.0) == 50
    assert service.percentile(3.0, reference) == 50  # not in the population: ties count half
    assert service.percentile(9.0, reference, exclude=3.0) == 100
    assert service.percentile(0.0, reference, exclude=3.0) == 0
    assert service.percentile(2.0, [2.0], exclude=2.0) is None


@pytest.mark.parametrize("role", ["batting", "bowling"])
def test_ratings_rank_qualified_players_by_their_shrunk_estimate(
    db: Database, role: core.Role
) -> None:
    window = _window(db)
    pop = service.population(db, role, window)
    assert pop is not None
    assert pop.qualified >= 5
    for component in pop.components:
        if len(component.qualified) < 2:
            continue  # nobody to rank against
        rated = []
        for player_id in component.qualified:
            group = service.ratings(db, player_id, role, window)
            assert group is not None
            item = next(i for i in group.items if i.key == component.component.key)
            assert item.rating is not None
            assert item.low is not None
            assert item.high is not None
            assert 0 <= item.low <= item.rating <= item.high <= 100
            assert item.qualified
            rated.append((component.estimates[player_id].shrunk, item.rating))
        rated.sort()
        ratings = [r for _, r in rated]
        assert ratings == sorted(ratings), component.component.key
        assert ratings[-1] == 100


def test_shrinkage_weight_follows_the_fitted_constant(db: Database) -> None:
    window = _window(db)
    pop = service.population(db, "batting", window)
    assert pop is not None
    scoring = next(c for c in pop.components if c.component.key == "scoring")
    player_id = next(iter(scoring.qualified))
    est = scoring.estimates[player_id]
    item = next(
        i
        for i in service.ratings(db, player_id, "batting", window).items  # type: ignore[union-attr]
        if i.key == "scoring"
    )
    k = scoring.constants.k
    weight = est.n / (est.n + k)
    assert item.weight == pytest.approx(weight, abs=1e-3)
    # The estimate is the record and the average, weighted by n and k.
    assert item.value == pytest.approx(
        100 * (weight * est.e / est.n + (1 - weight) * scoring.mean), abs=0.01
    )


def test_players_below_the_rated_minimum_get_no_rating(db: Database) -> None:
    window = _window(db)
    pop = service.population(db, "bowling", window)
    assert pop is not None
    occasional = next(p for p, balls in pop.role_balls.items() if 0 < balls < 10)
    group = service.ratings(db, occasional, "bowling", window)
    assert group is not None
    assert group.qualified is False
    assert all(i.rating is None for i in group.items)


def test_similar_players(db: Database) -> None:
    window = _window(db)
    pop = service._styles(db, "batting", window.first, window.last)
    assert pop is not None
    player_id = pop.candidates[0]
    group = service.similar(db, player_id, "batting", window)
    assert group is not None
    assert len(group.items) == min(service.SIMILAR, len(pop.candidates) - 1)
    assert player_id not in {p.player_id for p in group.items}
    scores = [p.similarity for p in group.items]
    assert scores == sorted(scores, reverse=True)
    assert all(-1 <= s <= 1 for s in scores)
    phrases = {t for f in style.BATTING_FEATURES for t in (f.high, f.low)}
    assert set(group.traits) <= phrases
    for p in group.items:
        assert set(p.shared) <= phrases
        # Similarity is symmetric within a window.
        back = service.similar(db, p.player_id, "batting", window)
        if back is not None and player_id in {q.player_id for q in back.items}:
            mine = next(q for q in back.items if q.player_id == player_id)
            assert mine.similarity == pytest.approx(p.similarity)


def test_style_helpers() -> None:
    rows = [{"a": 1.0, "b": 10.0}, {"a": 3.0, "b": 10.0}]
    scaler = style.Scaler.fit(rows, ["a", "b"])
    assert scaler.transform(rows[0]) == [-1.0, 0.0]
    assert style.cosine([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)
    assert style.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert style.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    z = [2.0, 0.1, -1.5, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert style.traits(z, "batting") == ["Scores fast", "Rotates the strike"]
    other = [1.0, 0.0, -0.9, 0.0, 0.0, 0.0, 0.0, -2.0]
    assert style.shared_traits(z, other, "batting") == ["Scores fast", "Rotates the strike"]
