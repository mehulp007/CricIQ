"""Test cricket's own models (V2-6).

A Test is not a long limited-overs match: it has four innings, declarations and
follow-ons, and a third result, the draw, that comes from running out of time.
The limited-overs features, chase tables and simulator do not apply, so the
Test models are built here from Test matches only (the ``test`` model group):

- :mod:`.states`: every ball's match state, with the context known before the
  match (the scoring era, the sides' ratings and the XIs' Test records).
- :mod:`.win_probability`: three outcomes (the batting side wins, the match is
  drawn, the batting side loses) per innings, against a state-only baseline.
- :mod:`.projection`: where the current innings will finish.
- :mod:`.scoring` and :mod:`.report`: the serving database's tables and the
  model cards.

The ball-outcome model and the ratings are the limited-overs ones, fitted on
Test balls (``criciq_ml.ball_outcome``, ``criciq_ml.ratings``).
"""
