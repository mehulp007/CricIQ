<div align="center">

# CricIQ

### AI-Powered Cricket Intelligence & Simulation Platform

**Decode the game. Predict the next move.**

[![CI](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB)
![Next.js](https://img.shields.io/badge/Next.js-16-000000)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**[Live demo → criciq-eight.vercel.app](https://criciq-eight.vercel.app)**

<img src="docs/images/replay.gif" alt="Replaying the last over of the 2019 IPL final ball by ball in CricIQ" width="880">

</div>

---

CricIQ turns every IPL delivery since 2008 into interactive analytics. Today you can replay any match ball by ball with an explainable win probability after every delivery. Probabilistic score projection, player and matchup intelligence, and Monte Carlo match simulation come next, all behind a polished web interface.

It is built as a **full ML product, not a dashboard**. Raw data goes through data engineering, then leak-free feature engineering, statistically validated models, explainability, a versioned API, the frontend and finally deployment.

> **Status:** milestones **M0–M3** are complete and deployed. You can replay every IPL match since 2008 with each side's chance of winning, and the reasons, after every ball. See the [roadmap](#roadmap) and the full [engineering plan](docs/PLAN.md).

## Features

| Feature | What it does | Status |
|---|---|---|
| Match Explorer & Replay | Browse any IPL match and replay it ball by ball: live scoreboard, commentary, worm and Manhattan charts, live scorecard, play/step/seek/speed controls and keyboard shortcuts | **Live** |
| Win Probability | Each side's chance after every ball, with a chart, turning points and plain-language TreeSHAP explanations | **Live** |
| Model Insights | Calibration, a season-by-season backtest, baselines, rejected features and the biggest swings in IPL history | **Live** |
| Score Projection | Median projected total, 80% interval, and P(150+ / 170+ / 190+ / 200+) | M4 · next |
| Player Lab | Batting and bowling profiles with phase, venue, situation and opposition splits | M5 |
| Matchup Lab | Batter vs bowler with sample-size-aware (shrunk) estimates and next-ball distribution | M6 |
| Compare, Ratings, Momentum, Pressure, Teams, Simulator | Transparent derived metrics and Monte Carlo simulation | V1 |

## The data

Every IPL match since 2008 is ingested ball by ball from Cricsheet, normalized into a DuckDB warehouse
and validated before anything downstream sees it.

| | |
|---|---|
| Seasons | 2008–2026 (19) |
| Matches | 1,243 |
| Deliveries | 295,732 |
| Players | 816, with attributes for ~98% of those with a meaningful sample |
| Validation | 17 invariant checks + 6 golden scorecards, all passing ([report](docs/data-quality-report.md)) |

What the exploration found, and how it shapes the models ([notebook](notebooks/01_eda.ipynb)):

- **About 1,200 outcomes, not 300k rows.** Deliveries within a match share one result, so models stay
  modest and are split by season.
- **Scores rose about 27 runs in the Impact Player era** (163 → 190 average first-innings total), so
  every model gets an as-of run-environment feature and is tested on the latest seasons.
- **The median batter–bowler pair has faced just 5 balls**, so matchup estimates are shrunk toward
  sensible baselines instead of over-reading tiny samples.

Details: [data pipeline](docs/data-pipeline.md) · [data dictionary](docs/data-dictionary.md)

## The win probability model

Two monotonic LightGBM models (first innings and chase), tested once on the 144 matches of 2025–2026
that they never saw ([model card](docs/model-cards/win-probability.md)):

| Test seasons 2025–2026 | Log loss | Brier | ECE | AUC |
|---|---|---|---|---|
| **CricIQ win probability** | **0.510** | **0.168** | 0.039 | 0.832 |
| Boosted trees on the match state only | 0.543 | 0.182 | 0.020 | 0.795 |
| Logistic regression on the match state | 0.549 | 0.184 | 0.034 | 0.791 |

- **Better than the baseline, with uncertainty measured honestly:** +0.039 log loss (95% CI +0.012 to
  +0.067), resampling whole matches because balls within a match are correlated. A season-by-season
  backtest (2016–2026) is published too: the model wins 7 of 11 seasons.
- **Leak-free by construction:** every feature uses only that ball or earlier matches. A test deletes
  and rewrites all later matches and checks that no earlier feature changes.
- **Honest negative results:** player, venue and squad strength were built as-of and tested season by
  season. None improved on the match state plus the scoring era, so none is used.
- **Sharp at the finish:** a WASP-style dynamic programme computes the exact chance of a chase from
  runs, balls and wickets, where data is thinnest.
- **Every choice made on validation data:** hyperparameters, calibration (none vs Platt, decided by a
  rolling origin) and features. Model versions are committed and gated; deploys only score
  ([ADR-0004](docs/adr/0004-committed-models-precomputed-predictions.md)).

Experiments: [notebook 02](notebooks/02_wp_experiments.ipynb) (LightGBM vs XGBoost vs CatBoost, the
chase feature, the 2019 final explained).

## Screenshots

| Overview | Match Explorer |
|---|---|
| ![Overview page with featured replays](docs/images/overview.png) | ![Match Explorer with filters](docs/images/explorer.png) |
| **Match Center** | **Model Insights** |
| ![Match Center with win probability during the 2019 final](docs/images/replay.png) | ![Model Insights: calibration and backtest](docs/images/models.png) |

## Architecture

```
Cricsheet JSON → pipelines (ingest · normalize · validate) → DuckDB warehouse
  → leak-free feature tables → ML (train · calibrate · explain · batch-score)
  → serving.duckdb + model registry → FastAPI (/api/v1) → Next.js frontend
```

The replay runs entirely in the browser from a single timeline payload per match, including every
ball's win probability and explanation. There are no per-ball API calls, and the live scorecard,
commentary and charts are all derived client-side. The API runs no model at request time: every
probability is precomputed by the image build from the committed model.

Read more in [docs/architecture.md](docs/architecture.md), [docs/deployment.md](docs/deployment.md)
and the [architecture decision records](docs/adr/).

## Tech stack

| Layer | Tools |
|---|---|
| Data | Python 3.12, DuckDB, Parquet (pyarrow), SQL validation checks, Typer |
| ML | LightGBM (monotonic constraints, exact TreeSHAP), scikit-learn, SciPy; XGBoost and CatBoost for comparison |
| Backend | FastAPI, Pydantic v2, uvicorn |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Quality | uv workspace, ruff, mypy (strict), pytest, Vitest, Testing Library, Playwright, GitHub Actions |
| Hosting | Vercel (web, Mumbai), Render (API in Docker, Singapore), free tiers |

## Local development

**Prerequisites:** Python 3.12 (managed by [uv](https://docs.astral.sh/uv/)), Node 24 with [pnpm](https://pnpm.io), and [just](https://just.systems) (`uv tool install rust-just`).

```bash
just setup      # install Python + frontend deps and git hooks
just dev-api    # API on http://localhost:8000 (OpenAPI docs at /docs)
just dev-web    # web app on http://localhost:3000
just check      # everything CI runs: lint, types, tests, build
just data run   # download Cricsheet data, rebuild, validate and export the serving database
just ml score   # add every ball's win probability from the committed model
just ml train   # retrain, evaluate and backtest (writes a new model version)
just e2e        # Playwright end-to-end tests (desktop + mobile) against the running app
```

## Project structure

```
core/        criciq_core: cricket rules, phase config, shared feature definitions
pipelines/   criciq_pipelines: ingestion → normalization → validation → export
ml/          criciq_ml: features, training, evaluation, inference, explainability, simulation
backend/     criciq_api: FastAPI app (routers → services → repositories)
frontend/    Next.js app
config/      versioned reference config (franchises, venues, phases, golden matches)
reference/   curated player attributes and documented overrides
notebooks/   exploration and research (executed, with outputs)
docs/        plan, architecture, ADRs, model cards, metric definitions
tests/       Python tests + real-match fixtures for every data edge case
```

## Roadmap

- [x] **M0** Foundations: monorepo, tooling, CI, design system, app shell
- [x] **M1** Data warehouse: Cricsheet ingestion, normalization, validation
- [x] **M2** Match Explorer & Replay: first public deployment
- [x] **M3** Win Probability: calibrated, explainable, backtested
- [ ] **M4** Score Projection
- [ ] **M5** Player Lab
- [ ] **M6** Matchup Lab + ball-outcome model → **MVP v0.1**
- [ ] **V1** Compare, ratings, momentum & pressure, teams, simulator

## Data & attribution

Ball-by-ball data is from [Cricsheet](https://cricsheet.org), used under the [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/). Player attributes come from [Wikidata](https://www.wikidata.org) (CC0) and English [Wikipedia](https://en.wikipedia.org) cricketer infoboxes ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)).

CricIQ is an independent portfolio project. It is not affiliated with the IPL, the BCCI or any franchise. All predictions and simulations are statistical model estimates, not guarantees, and the project is not intended for betting.

## License

[MIT](LICENSE) © 2026 Mehul Patil
