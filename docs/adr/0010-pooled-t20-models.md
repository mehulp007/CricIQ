# ADR-0010: Pooled T20 models, served per competition

- **Status:** Accepted
- **Date:** 2026-10-07

## Context

V2-3 retrains the models on every T20 competition at once (the IPL, BBL, PSL, CPL, SA20 and men's
T20Is: 6,391 matches against the IPL's 1,243), so that the T20Is and leagues get models at all and
players' records count every competition. Four questions had to be settled:

- **What the models train on.** The model code reads a v1-shaped warehouse of one competition and
  orders matches by `match_order`.
- **What the competitions share.** Players are the same people everywhere, but each competition
  scores at its own rate (T20Is about 7.6 runs an over, the IPL about 8.4), and associate nations'
  T20Is are lopsided in a way no league is.
- **How splits work** when a BBL season spans the new year.
- **Who gets the pooled model.** The rule set in advance: the pooled models must be no worse than v1 on the
  IPL's 2025-26 test seasons, or the IPL keeps v1.

## Decision

- **A pooled copy** (`data/warehouse/t20.duckdb`) holds every T20 competition in the v1 shape, with
  `match_order` running across all of them by date, so the model code reads it unchanged.
- **Competition-aware features.** Players and grounds carry their history across competitions;
  the scoring era and the chase tables are each competition's own (with the pooled death overs as a
  fallback where a competition has too few). Candidate features for international cricket and the
  competition's scoring level join the forward selection. Ratios are rounded to nine decimals so
  values equal in exact arithmetic are equal on every CPU (the Windows/Linux difference V2-0 found).
- **Splits by calendar year** of the match date, configured in the same keys; for the IPL a year
  is a season, so v1's protocol is unchanged.
- **The ball model** keeps one effect per player across competitions, adds a term per competition,
  and folds a competition's term into the intercept when serving it, so the API and the simulator
  read the same additive terms as before.
- **Every version records its features** (and feature settings) in its manifest; v1 manifests
  predate that and use the v1 defaults. Scoring builds each model's features from the data it was
  trained on (`criciq-ml score` picks the IPL copy or the pooled one from the manifest).
- **Per-competition serving pointers.** `models/<name>/CURRENT` names the version every competition
  is scored with; `CURRENT.IPL` keeps the IPL on another version. Training a pooled version rebuilds
  v1's headline test predictions exactly from its recorded settings (checked against its recorded
  score), compares both on the same IPL test balls with a match-level bootstrap, and sets the IPL's
  pointer: the pooled version serves the IPL only if it is no worse there (the projection must also
  keep its 80% range inside the gate's coverage band on the IPL).
- **Gates per competition.** A competition's test set can be 60 matches, so a version fails only
  where it is clearly worse than the baseline (the whole interval below zero); ratings gate only
  validations that follow at least 100 players (the threshold below which a competition borrows the
  all-T20 shrinkage).
- **Ratings fitted per scope** of the players database (each competition and all T20), and the
  players database gets win probability added from the model serving each competition, so the
  `/api/v2` Player Lab has ratings, similar players and WPA everywhere.
- **The simulator** is backtested per competition on a serving-shaped database of that competition
  (`criciq-data export-competition`), with the pooled ball model refit before the test years, and
  gated as in v1. A version that fails stays in the registry unserved, and its backtest is published
  in the simulator card under "Backtested, not served".

## Consequences

**Positive**
- Every T20 competition has calibrated models that beat their baselines, and the IPL's choice is
  made on the IPL's own test balls, not on pooled numbers.
- The site's IPL is unchanged wherever v1 stays better; the comparison is published in each model
  card either way.
- One code path trains and scores every competition.

**Negative / accepted trade-offs**
- Two versions of a model can serve at once (the IPL's and the rest), and their cards are separate
  (`<model>-ipl.md`).
- The gate thresholds for small competitions (the interval rule, 100 players) were set when these
  results were first seen; they are recorded here and in the cards rather than hidden.
- Training is slower (minutes to hours); the ball model's independent fits run in parallel
  processes.
- The T20I simulator (2.0.0) failed its gate: first-innings totals ran 7 runs low and its win
  chances were too close to even between unequal sides, because the ball model shrinks associate
  players with few balls toward the average player. No competition is simulated with it until the
  ball model separates weak sides better (shrinking toward a team or nation level).

**Revisit when** ODI and Test models arrive (V2-5, V2-6): they need their own format rules, and the
same pointers can carry a version per format.
