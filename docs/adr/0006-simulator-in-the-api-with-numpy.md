# ADR-0006: Run the match simulator in the API, vectorised with numpy

- **Status:** Accepted
- **Date:** 2026-10-05

## Context

V1-d adds a Monte Carlo match simulator and a what-if sandbox in the replay. Both answer
questions that cannot be precomputed: any two XIs, any batting order, any edited score at any
ball. The plan's target is 10,000 simulated matches in under 2 seconds.

ADR-0004 kept ML libraries out of the API image, and ADR-0005 made the ball-outcome model a table
of additive terms the API evaluates with plain Python, noting the simulator as the time to
revisit. A simulated match is about 240 legal balls; 10,000 matches are 2.4 million draws from
the ball model, far too many for a Python loop per ball.

## Decision

- The engine lives in `criciq_core.simulation`, shared by the API (live requests) and
  `criciq-ml` (the backtest), so what is tested is exactly what is served.
- It steps **all simulations together, one legal ball at a time**, as numpy arrays: about 240
  iterations of array operations over 10,000 rows. Logits that do not change ball to ball
  (phase, batter, bowler, matchup, era) are precomputed per side.
- `criciq-core` gains **numpy** as its only new dependency. It is a numerical library, not a
  model framework: the API still runs no trained model object, only the published additive
  terms (ADR-0005), and still never imports scikit-learn, LightGBM or pandas.
- The simulator's one tuned setting (the spread of match conditions) is registered under
  `models/simulator/<version>/` and published to the serving database by `criciq-ml score`, like
  the rating constants.

## Consequences

**Positive**
- 10,000 complete matches in about 1 second on a laptop; the simulator and the backtest share
  one implementation.
- The runtime image grows by numpy only (about 20 MB), well within the 512 MB instance.

**Negative / accepted trade-offs**
- The free instance's CPU is much slower than a laptop, so production requests can take a few
  seconds; results are cached per request and seeded from the request, so repeats are instant.
- Per-ball dynamics stay those of the additive ball model: no batting order changes, no Impact
  Player substitutions, no venue terms.

**Revisit when** the simulator needs richer per-ball dynamics than additive terms can express.
