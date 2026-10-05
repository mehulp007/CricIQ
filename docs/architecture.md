# CricIQ Architecture

CricIQ is a **modular monolith**: one data pipeline, one ML package, one API service and one web app, all in a single repository. There are no microservices, queues or caches beyond HTTP caching and in-process LRU until a measured need appears.

## Data flow

```
Cricsheet IPL JSON zip ─┐   config/*.yaml + reference/player_attributes.csv
                        ▼
  [pipelines] download → raw (immutable, versioned by data_version)
              extract/normalize → warehouse.duckdb (core tables)
              validate (schemas + invariants + golden matches)
              export → serving.duckdb (slim, read-only, plus Player Lab tables with par
                       and Team Analytics tables checked against the official league tables)
                        ▼
  [ml] features: as-of, leak-free match states
       train → evaluate → backtest → register (models/<name>/<version>/, committed; ADR-0004)
       score every historical ball with the current models → serving.duckdb
       (wp_predictions, score_projections, player_wpa, matchup_cells, ball_model_terms,
        rating constants, simulator settings)
                        ▼
  [backend] FastAPI /api/v1: reads serving.duckdb only; next-ball odds are computed
            from the stored ball-model terms with plain arithmetic (ADR-0005)
                        ▼
  [frontend] Next.js on Vercel: server components + client-side replay engine
             (featured replays bundled; see deployment.md)
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
| `registry.py` | Versioned models on disk, `CURRENT` pointer, promotion gate |
| `scoring.py` | Score every ball and publish into `serving.duckdb` atomically |
| `ball_outcome.py` | Ball-outcome model: outcomes, situation, penalised player effects, head-to-head prior (kappa) |
| `ball_outcome_training.py` | Its protocol: tuning, feature selection, test, calibration, head-to-head check, backtest |
| `leverage.py` | Pressure (leverage) for every state from what-if next balls, and momentum |
| `lab.py` | Analytics Lab research notes: momentum, pressure and clutch tests |
| `ratings.py` | CricIQ Ratings: shrinkage per component (k, noise), next-season validation, stability, similar-player retrieval test |
| `report.py`, `projection_report.py`, `ball_outcome_report.py`, `ratings_report.py` | Model cards (`docs/model-cards/`) and the Model Insights data bundled with the web app |

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

## Precompute vs live

Everything historical is precomputed: every ball's win probability, explanation and projection, and the Player Lab's innings rows and ball-level cells. A profile for any season window is a handful of small aggregates over those tables (tens of milliseconds). CricIQ Ratings and similar players need the whole population of a window, so the API computes each window once (about 30 ms) and keeps the most recent 48 windows in an in-process cache; the database is read-only, so a cached window never goes stale. Evaluation artifacts are generated with each model version. Live computation is reserved for what depends on user input: next-ball distributions from the ball model's terms, and match simulations and what-if states from `criciq_core.simulation`, which steps 10,000 simulations forward together as numpy arrays (ADR-0006). A simulated match is played in one season: its squads come from `match_players` (everyone who played for each franchise that year), and the scoring era, league rates and players' batting positions and bowling usage are taken as of that season. Simulation results are cached per request and seeded from it, so a repeated question gets the same answer instantly.

A match replay is driven **entirely client-side** from one timeline payload per match. There are no per-ball API calls.
