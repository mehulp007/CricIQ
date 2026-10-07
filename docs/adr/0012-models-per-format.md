# ADR-0012: Each format has its own models

- **Status:** Accepted
- **Date:** 2026-10-07

## Context

V2-5 adds men's ODIs (2,576 matches from 2002). Until now every model, the simulator and the
ratings were T20 models: `criciq_core.phases.MODEL_FORMAT = "T20"` named the format, and some
code assumed it outright (the chase table's 120 balls, the simulator's 20 overs and four-over
quota, the projection's baseline buckets, phase lookups capped at over 40). Three questions had
to be settled:

- **Pool ODIs with T20 or not.** A 50-over innings paces itself differently (the death starts at
  over 41, and a chase can be 300 balls), so the same match state means something else.
- **Where an ODI model lives** beside the T20 ones, which the IPL and the pooled competitions read
  from `models/<model>/` and `config/models/<model>.yaml`.
- **How shared code learns the format** without threading a parameter through every function of
  the features, the training protocols, the scoring and the reports.

## Decision

- **ODIs get their own models**, trained on ODIs alone from an ODI copy of the warehouse
  (`data/warehouse/odi.duckdb`, built beside the pooled T20 copy by `run` and every sync), with
  the same features, protocols and gates as the T20 models. Forward selection chose their extra
  features again on the pre-test rolling origin.
- **One folder per format.** The T20 models keep their places; another format's sit in a folder
  named after it: `config/models/odi/`, `models/odi/`, `docs/model-cards/odi/` and
  `frontend/data/models/odi/`. Each folder has its own `CURRENT` pointers and versions (the ODI
  models are 1.0.0).
- **The format is a context.** `criciq_core.phases.use_format("ODI")` sets the models' format for
  a block of code (a `ContextVar`, T20 by default); `model_phases()`, the chase table's limits,
  the projection's buckets, the rating components and the registry and config paths all read it.
  The ML entry points set it: `criciq-ml train <model> --format ODI` and `report --format ODI`,
  and `score` sets each competition's format from its serving database. Worker processes (the
  ball model's parallel fits) are handed the format explicitly.
- **The simulator's rules travel with each side.** `criciq_core.simulation.FormatRules` (overs,
  each bowler's quota, the over from which bowlers with overs left are favoured, and the phases)
  comes from `rules_for("T20" | "ODI")`; a `Side` carries its rules, so the engine, the backtest
  and the API play 20 or 50 overs without a separate code path. The API takes the rules from the
  database's format (`db.match_format`), not from the context, because its requests run in a
  thread pool.

## Consequences

**Positive**
- The T20 models, cards and serving data are untouched: the T20 code paths read the same values
  as before (checked against the IPL serving database's checksums and the regenerated T20 cards).
- Test cricket (V2-6) needs its own phases and rules, not another set of special cases.
- An ODI model is judged exactly like a T20 one, and reported whichever way it comes out.

**Negative / accepted trade-offs**
- A context is implicit: code that runs outside an entry point, or in a new process or thread,
  works with T20 models unless told otherwise. The places that cross processes say so.
- ODI histories are shorter than the pooled T20 data (2,474 matches with a result against
  6,391), and players' T20 records do not inform their ODI ones.
