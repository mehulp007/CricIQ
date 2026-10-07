# ADR-0013: Each model group trains on its own competitions only

- **Status:** Accepted
- **Date:** 2026-10-07
- **Supersedes:** the pooling in ADR-0010 (the IPL kept its own models then, and still does)

## Context

V2-3 (ADR-0010) trained one set of T20 models on every T20 competition at once: the IPL, the
BBL, CPL, PSL and SA20, and men's T20 internationals. The pooled models served the leagues and
T20Is, while the IPL kept its v1 models because pooling did worse on the IPL's own test seasons.
ODIs got models of their own in V2-5 (ADR-0012).

The pooled models were judged by their results, but what they learned from was mixed: a BBL
replay's win probability had learned from IPL and T20I matches, and a T20I's from franchise
leagues. The decision on the project is that every kind of cricket is modelled from its own
matches only: the IPL alone, the other four leagues together, T20 internationals alone, ODIs
alone, and (V2-6) Tests alone.

Training still runs on a laptop and takes hours per group, so it has to be one command that can
be left running, resumed and read afterwards, without someone watching the logs.

## Decision

- **Model groups** (`config/model_groups.yaml`, read by `criciq_core.groups`): `ipl` (IPL),
  `leagues` (BBL, CPL, PSL, SA20), `t20i` (T20I) and `odi` (ODI). Each competition belongs to
  exactly one group. A group's models train only on its competitions, from a copy of the
  warehouse holding just them (`data/warehouse/leagues.duckdb`, `t20i.duckdb`, `odi.duckdb`;
  the IPL's own copy), and serve only them.
- **Its own folders.** `config/models/<group>/` and `models/<group>/` hold a group's settings and
  versions, as ODIs' did. The IPL's versions keep v1's places (`models/<model>/`), marked by
  `CURRENT.IPL`, so its served models and serving data do not move.
- **The group is a context**, like the format: `criciq_ml.formats.use_group("leagues")` sets the
  folders and the format for a block. `criciq-ml train <model> --group <group>`,
  `report --group <group>`, and `score` sets each competition's group.
- **Nothing is borrowed across groups.** The leagues' ratings borrow `k` for a thin component
  from the four leagues' records together (`pool`), not from all T20. The leagues' ball model has
  a term per league and no national-side terms; the T20Is' has national-side terms and no
  competition terms. The feature `international` (constant within each group) is not served.
- **A transition, not a gap.** Until a group has a current version of a model, scoring borrows
  the pooled T20 version (`registry` fallback, only while scoring and only for T20 groups) and
  says so (`[fallback]` in the output, `just model-status`). A group that has trained a
  simulator never borrows the pooled one: a backtest that failed means no simulator there. The
  pooled versions, `models/<model>/CURRENT` and the pooled copy `data/warehouse/t20.duckdb` stay
  only for that fallback and for the "All T20" career view's ratings, a combined record by
  nature.
- **One command per group.** `just train-group <group>` (`scripts/train_group.py`) trains the
  ball model, win probability and projection, scores (the ratings read the new win probability
  added), then the ratings and the simulator's backtest. It names new versions (1.0.0, then
  1.1.0 ...) in the group's configuration, promotes only what passes its gate, keeps going past
  a failure, resumes an interrupted run, keeps Windows awake, and writes
  `data/training/<group>/summary.md`. `just publish-models` scores every competition, writes the
  cards and Model Insights data of every group with models of its own, and re-exports the
  featured replays.

## Outcome

Both groups were trained on 2026-10-07 and tested once on 2025-2026. The leagues' models (1,563
matches) beat their baselines except where the test is too small to say: win probability 0.504
against 0.516 (95% interval -0.001 to +0.024), the projection 16.8 runs against 18.2 for par, the
ball model in all 11 backtest years; the simulator serves the BBL, CPL and SA20. Their win
probability 1.1.0 was re-chosen on the pre-test years and leaves out players' records, which with
league-only careers made the first innings worse. The T20Is' models (3,480 matches) beat theirs
clearly (win probability 0.432 against 0.458, +0.017 to +0.034); their simulator is not served,
its totals 8 runs short of 2025-26. Against the pooled model on the same matches, the groups'
own win probability is better on the BBL and SA20, level on T20Is and the PSL, and behind on the
CPL.

## Consequences

**Positive**
- Every number on a competition's pages comes from models that learned from that kind of cricket
  only, and the cards say what each was trained on.
- The T20Is get a ball model and a simulator built for internationals, without league scoring
  rates mixed in (the pooled T20I simulator failed its gate partly through that mix).
- Retraining any group on newer data is the same command, with a summary to review.

**Negative / accepted trade-offs**
- Less data per model than the pooled versions: the leagues have 1,591 matches (the IPL 1,243),
  and a player's league record no longer informs their international one. Each group is still
  judged against its baselines on 2025-26 and reported whichever way it comes out.
- Until a group is trained, its competitions are served by the pooled models; the fallback is
  visible but it is still pooled.
- Two more warehouse copies (about 30 MB) are built on every run and sync.
