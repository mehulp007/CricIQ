# CricIQ Architecture

CricIQ is a **modular monolith**: one data pipeline, one ML package, one API service and one web app, all in a single repository. There are no microservices, queues or caches beyond HTTP caching and in-process LRU until a measured need appears.

## Data flow

```
Cricsheet JSON zips ────┐   config/*.yaml + reference/player_attributes.csv
                        ▼
  [pipelines] download → raw (immutable, versioned by data_version)
              or sync: only new/corrected/withdrawn matches since the last run, against an
              ingest log (ADR-0008), applied to the interim tables and rebuilt in staging
              extract/normalize → warehouse.duckdb (core tables)
              validate (schemas + invariants + golden matches)
              export → serving.duckdb (the IPL: slim, read-only, plus Player Lab tables with
                       par and Team Analytics tables checked against the official league tables)
                     → serving-<competition>.duckdb (the same tables for every other competition
                       on the site: BBL, PSL, CPL, SA20, T20I, ODI, Test; ADR-0011)
                     → players.duckdb (Player Lab tables of every competition, par per
                       competition, and all T20 together; one schema per scope, ADR-0009)
                        ▼
  [ml] features: as-of, leak-free match states
       train → evaluate → backtest → register (models/<name>/<version>/, committed; ADR-0004)
       model groups (config/model_groups.yaml; ADR-0013): the IPL, the other leagues
       (BBL, CPL, PSL, SA20), T20Is, ODIs and Tests each train on their own competitions
       only, from their own warehouse copy (ipl, leagues, t20i, odi, test .duckdb), into
       models/<group>/
       (the IPL's in models/ with CURRENT.IPL); `just train-group <group>` trains one in
       order and writes a summary. Until a group has its own, scoring borrows the pooled
       T20 models of V2-3 (t20.duckdb, models/<name>/CURRENT; ADR-0010) and says so.
       ODIs: ADR-0012. Tests (ADR-0014): win, draw or loss per innings (a regression the
       API can run), every innings projected, no simulator; a chase what-if and calculator
       score every historical ball with the models serving each competition → each serving
       database (wp_predictions, score_projections, player_wpa, matchup_cells, ball_model_terms,
        rating constants, simulator settings where a simulator passed there) and
        players.duckdb (player_wpa, each scope's rating constants)
                        ▼
  [backend] FastAPI /api/v2/{competition}/...: each request reads its competition's
            serving database (get_db); next-ball odds are computed from the stored
            ball-model terms with plain arithmetic (ADR-0005); the Player Lab reads one
            scope of players.duckdb (search_path), also for all T20 (ADR-0009)
                        ▼
  [frontend] Next.js on Vercel: every data page under /[competition]/, a switcher in
             the top bar, server components + client-side replay engine (featured
             replays bundled per competition; see deployment.md)
```

## Packages and dependency direction

| Package | Import name | Responsibility |
|---|---|---|
| `core/` | `criciq_core` | Cricket rules (legal balls, overs, rates), phase config, paths, **definitions shared by training and serving** (rating components, style profiles) |
| `pipelines/` | `criciq_pipelines` | Ingestion, normalization, validation, export (`criciq-data` CLI) |
| `ml/` | `criciq_ml` | Feature assembly, training, evaluation, inference, explainability, metrics, simulation |
| `backend/` | `criciq_api` | HTTP API: `routers → services → repositories → DuckDB`, `services → inference` |
| `frontend/` | — | Next.js web application |

```
core ◄── pipelines
core ◄── ml
core ◄── backend
```

The backend imports neither `pipelines` nor `ml`: the ML package writes its outputs into the serving
database, which the API reads. Production code never imports notebooks.

## ML layer

`criciq_ml` owns everything model-related (`criciq-ml` CLI):

| Module | Responsibility |
|---|---|
| `data.py` | Load warehouse tables into an `Inputs` bundle (truncatable, for leakage tests) |
| `features.py` | One row per match state; as-of player, venue and era history updated only after each match |
| `chase.py` | WASP-style dynamic programme for the chase, from earlier seasons' death-over rates |
| `training.py` | Tuning, calibration choice, test scoring, feature selection, backtest, served fit |
| `model.py` | The served model: prediction, TreeSHAP explanations grouped into concepts, rule layer |
| `projection.py` | Score projection: era-relative target, quantile models, conformal shifts, CDF |
| `projection_training.py` | Its protocol: tuning, calibration, test, feature selection, backtest |
| `registry.py` | Versioned models on disk, `CURRENT` pointer (and `CURRENT.<competition>`), promotion gate |
| `comparison.py` | A pooled version against the IPL's own on the IPL's test balls (v1 rebuilt exactly) |
| `scoring.py` | Score every ball and publish into `serving.duckdb` atomically |
| `players_scoring.py` | Win probability added and each scope's rating constants in `players.duckdb` |
| `ball_outcome.py` | Ball-outcome model: outcomes, situation, penalised player effects, head-to-head prior (kappa) |
| `ball_outcome_training.py` | Its protocol: tuning, feature selection, test, calibration, head-to-head check, backtest |
| `leverage.py` | Pressure (leverage) for every state from what-if next balls, and momentum |
| `lab.py` | Analytics Lab research notes: momentum, pressure and clutch tests |
| `ratings.py` | CricIQ Ratings: shrinkage per component (k, noise), next-season validation, stability, similar-player retrieval test |
| `report.py`, `projection_report.py`, `ball_outcome_report.py`, `ratings_report.py`, `simulator_report.py`, `report_common.py` | Model cards (`docs/model-cards/`) and the Model Insights data bundled with the web app (the IPL's, and the pooled versions' under `t20/`) |

The full protocols and results are in the model cards for [win probability](model-cards/win-probability.md), [score projection](model-cards/score-projection.md), [ball outcome](model-cards/ball-outcome.md) and [CricIQ Ratings](model-cards/ratings.md); derived metrics are defined in [metrics.md](metrics.md).

## Data layer

See [data-pipeline.md](data-pipeline.md) for the ingestion, normalization and validation steps,
[data-dictionary.md](data-dictionary.md) for every warehouse table, and
[data-quality-report.md](data-quality-report.md) for the current validation results.

## Key decisions

- [ADR-0001](adr/0001-duckdb-over-postgres.md): DuckDB + Parquet instead of PostgreSQL
- [ADR-0002](adr/0002-uv-workspace-python-312.md): uv workspace pinned to Python 3.12
- [ADR-0003](adr/0003-hosting-vercel-and-render.md): Vercel for the web app, Render for the API
- [ADR-0004](adr/0004-committed-models-precomputed-predictions.md): committed model versions, precomputed predictions
- [ADR-0005](adr/0005-ball-model-as-additive-terms.md): the ball-outcome model served as additive terms
- [ADR-0006](adr/0006-simulator-in-the-api-with-numpy.md): the simulator runs in the API with numpy
- [ADR-0007](adr/0007-one-warehouse-for-every-competition.md): one warehouse for every competition, with v1-shaped scopes
- [ADR-0008](adr/0008-incremental-sync.md): incremental data sync with an ingest log
- [ADR-0009](adr/0009-players-database-per-competition.md): a players database with one schema per competition
- [ADR-0010](adr/0010-pooled-t20-models.md): pooled T20 models, served per competition
- [ADR-0011](adr/0011-one-serving-database-per-competition.md): one serving database per competition, the API under `/api/v2/{competition}` and the site under `/[competition]/`
- [ADR-0012](adr/0012-models-per-format.md): each format has its own models (`models/odi/`), the format as a context, and the simulator's rules per format
- [ADR-0013](adr/0013-models-per-group.md): each model group (the IPL, the other leagues, T20Is, ODIs, Tests) trains on its own competitions only
- [ADR-0014](adr/0014-test-cricket-models.md): Test cricket has models of its own design: three outcomes, every innings projected, no simulator
- [ADR-0015](adr/0015-series-and-tournaments.md): series and tournaments from Cricsheet's event names, with known results the build must reproduce

## Precompute vs live

Everything historical is precomputed: every ball's win probability, explanation and projection, and the Player Lab's innings rows and ball-level cells. A profile for any season window is a handful of small aggregates over those tables (tens of milliseconds). CricIQ Ratings and similar players need the whole population of a window, so the API computes each window once (about 30 ms) and keeps the most recent 48 windows in an in-process cache; the database is read-only, so a cached window never goes stale. Evaluation artifacts are generated with each model version. Live computation is reserved for what depends on user input: next-ball distributions from the ball model's terms, and match simulations and what-if states from `criciq_core.simulation`, which steps 10,000 simulations forward together as numpy arrays (ADR-0006). A simulated match is played in one season: its squads come from `match_players` (everyone who played for each franchise that year), and the scoring era, league rates and players' batting positions and bowling usage are taken as of that season. Simulation results are cached per request and seeded from it, so a repeated question gets the same answer instantly.

A match replay is driven **entirely client-side** from one timeline payload per match. There are no per-ball API calls.
