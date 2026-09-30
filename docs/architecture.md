# CricIQ Architecture

CricIQ is a **modular monolith**: one data pipeline, one ML package, one API service and one web app, all in a single repository. There are no microservices, queues or caches beyond HTTP caching and in-process LRU until a measured need appears.

## Data flow

```
Cricsheet IPL JSON zip ─┐   config/*.yaml + reference/player_attributes.csv
                        ▼
  [pipelines] download → raw (immutable, versioned by data_version)
              extract/normalize → warehouse.duckdb (core tables)
              validate (schemas + invariants + golden matches)
              features → as-of feature tables (leak-safe)
                        ▼
  [ml] train → evaluate → calibrate → register (models/<name>/<version>/ + model card)
       batch-score every historical ball → ball_predictions
                        ▼
  [export] serving.duckdb (slim, read-only) + model artifacts → GitHub Release
                        ▼
  [backend] FastAPI /api/v1: reads serving.duckdb; live inference only for
            what-if, next-ball and simulation requests
                        ▼
  [frontend] Next.js on Vercel: server components + client-side replay engine
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
core ◄── backend ──► ml (inference only)
```

The backend never imports `pipelines`. Production code never imports notebooks.

## Data layer

See [data-pipeline.md](data-pipeline.md) for the ingestion, normalization and validation steps,
[data-dictionary.md](data-dictionary.md) for every warehouse table, and
[data-quality-report.md](data-quality-report.md) for the current validation results.

## Key decisions

- [ADR-0001](adr/0001-duckdb-over-postgres.md): DuckDB + Parquet instead of PostgreSQL
- [ADR-0002](adr/0002-uv-workspace-python-312.md): uv workspace pinned to Python 3.12

## Precompute vs live

Everything historical is precomputed by the pipeline: match timelines (with win probability, projections and explanations for every ball), player and matchup aggregates, and evaluation artifacts. The API computes live only what depends on user input: what-if states, next-ball distributions and simulations.

A match replay is driven **entirely client-side** from one timeline payload per match. There are no per-ball API calls.
