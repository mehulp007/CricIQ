# ADR-0005: Serve the ball-outcome model as a table of additive terms

- **Status:** Accepted
- **Date:** 2026-10-01

## Context

M6 needs live predictions for the first time. The Matchup Lab shows next-ball odds for any batter
against any bowler, including pairs that never met, and `POST /predict/next-ball` takes a
user-chosen situation. Neither can be precomputed: there are about 500,000 possible pairs before
the situation is even chosen.

ADR-0004 keeps ML libraries out of the API image, which runs on a 512 MB free instance. The plan
had suggested multiclass LightGBM for this model.

## Decision

- The ball-outcome model is a **multinomial logistic regression**: one intercept per outcome, plus
  additive terms for the situation levels, the scoring era, each batter and each bowler. Player
  terms are ridge-penalised (a random-effects-style estimate of skill).
- `criciq-ml score` publishes the fitted terms to `ball_model_terms` in `serving.duckdb`. The API
  loads them once and computes a prediction as a sum of a few vectors and a softmax, in plain
  Python.
- A test checks that the API's arithmetic matches the fitted model to 1e-9.

## Consequences

**Positive**
- Live predictions with no ML dependency and no model file in the runtime image.
- Every term is interpretable: a batter's six coefficient is their six-hitting relative to an
  average player in the same situation.
- Pairs that never met, and newcomers, fall back to sensible averages by construction.

**Negative / accepted trade-offs**
- No interactions between situation and player beyond what the terms encode. Separate per-phase
  player effects were tested and gained less than the 0.1% bar (see the model card).
- Gradient-boosted trees might gain a little more log loss. On single balls the signal is small,
  and the gain from players over the situation alone is already under half a percent.

**Revisit when** the V1 simulator needs richer per-ball dynamics (bowler fatigue, batting order),
which may justify a model that the API can only run with an ML library.
