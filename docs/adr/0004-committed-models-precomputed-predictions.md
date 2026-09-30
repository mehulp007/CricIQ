# ADR-0004: Commit versioned model artifacts and precompute every prediction

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

The plan kept model artifacts out of git (GitHub Releases or the Hugging Face Hub) and allowed the
API to run models live. At M3 the win probability model became real, and three facts shaped where
it should live:

- The API image is rebuilt from the latest Cricsheet data on every deploy (ADR-0003). If the image
  also **retrained**, every deploy would ship an unreviewed model, and the published model card
  could silently stop matching what users see.
- The two LightGBM models are small text files (about 540 KB together). The repository is private,
  so downloading from a Release at build time would need a token inside the Render build.
- Every win probability shown in a replay is for a completed historical match, so none of them
  needs to be computed on request.

## Decision

- **Model versions are committed** under `models/<name>/<version>/`: the model files, a manifest,
  and the full evaluation. `models/<name>/CURRENT` names the served version.
- **Training is explicit and gated.** `criciq-ml train` tunes, evaluates, backtests and registers a
  version. It promotes the version only if it beats the baseline on test log loss and Brier score
  and does not regress against the current version. The result is reviewed and committed like code.
- **Deploys only score.** The image's data stage runs `criciq-data run` and then `criciq-ml score`.
  That step computes features for the freshly downloaded data and writes every ball's win
  probability and explanation into `serving.duckdb`.
- **The API never runs a model.** It reads precomputed tables, and the runtime image contains no
  ML libraries.

## Consequences

**Positive**
- What users see always comes from the reviewed model described in the model card.
- A deploy is reproducible from a commit, and new matches are scored by the current model without
  retraining.
- The runtime image stays small, which matters on a 512 MB free instance.

**Negative / accepted trade-offs**
- A new season's matches are scored by a model trained before them until someone retrains and
  commits a new version. That is deliberate: retraining is a reviewed act.
- Model files in git make diffs noisy when a version changes. They are small and change rarely.

**Revisit when** live inference arrives (the V1 what-if sandbox and simulator). The API will then
need the model at request time, loaded from the same registry.
