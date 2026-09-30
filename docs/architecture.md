# CricIQ Architecture

CricIQ is a **modular monolith**: one data pipeline, one ML package, one API service and one web app, all in a single repository. There are no microservices, queues or caches beyond HTTP caching and in-process LRU until a measured need appears.

## Data flow

```
Cricsheet IPL JSON zip ─┐   config/*.yaml + reference/player_attributes.csv
                        ▼
  [pipelines] download → raw (immutable, versioned by data_version)
              extract/normalize → warehouse.duckdb (core tables)
              validate (schemas + invariants + golden matches)
              export → serving.duckdb (slim, read-only)
                        ▼
  [ml] features: as-of, leak-free match states
       train → evaluate → backtest → register (models/<name>/<version>/, committed; ADR-0004)
       score every historical ball with the current model → serving.duckdb (wp_predictions)
                        ▼
  [backend] FastAPI /api/v1: reads serving.duckdb only, no model at request time
            (live inference arrives with the V1 what-if sandbox and simulator)
                        ▼
  [frontend] Next.js on Vercel: server components + client-side replay engine
             (featured replays bundled; see deployment.md)
```

## Packages and dependency direction

| Package | Import name | Responsibility |
|---|---|---|
| `core/` | `criciq_core` | Cricket rules (legal balls, overs, rates), phase config, paths, **feature definitions shared by training and serving** |
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
| `registry.py` | Versioned models on disk, `CURRENT` pointer, promotion gate |
| `scoring.py` | Score every ball and publish into `serving.duckdb` atomically |
| `report.py` | Model card (`docs/model-cards/`) and the Model Insights data bundled with the web app |

The full protocol and results are in the [win probability model card](model-cards/win-probability.md).

## Data layer

See [data-pipeline.md](data-pipeline.md) for the ingestion, normalization and validation steps,
[data-dictionary.md](data-dictionary.md) for every warehouse table, and
[data-quality-report.md](data-quality-report.md) for the current validation results.

## Key decisions

- [ADR-0001](adr/0001-duckdb-over-postgres.md): DuckDB + Parquet instead of PostgreSQL
- [ADR-0002](adr/0002-uv-workspace-python-312.md): uv workspace pinned to Python 3.12
- [ADR-0003](adr/0003-hosting-vercel-and-render.md): Vercel for the web app, Render for the API
- [ADR-0004](adr/0004-committed-models-precomputed-predictions.md): committed model versions, precomputed predictions

## Precompute vs live

Everything historical is precomputed. Since M3 that covers every ball's win probability and explanation; later milestones add projections and player and matchup aggregates. Evaluation artifacts are generated with each model version. Live computation is reserved for what depends on user input (what-if states, next-ball distributions, simulations), which arrives in later milestones.

A match replay is driven **entirely client-side** from one timeline payload per match. There are no per-ball API calls.
