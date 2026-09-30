<div align="center">

# CricIQ

### AI-Powered Cricket Intelligence & Simulation Platform

**Decode the game. Predict the next move.**

[![CI](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB)
![Next.js](https://img.shields.io/badge/Next.js-16-000000)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

</div>

---

CricIQ turns every IPL delivery since 2008 into interactive analytics. It offers ball-by-ball historical match replays, calibrated and explainable win probability, probabilistic score projection, player and matchup intelligence, and Monte Carlo match simulation, all behind a polished web interface.

It is built as a **full ML product, not a dashboard**. Raw data goes through data engineering, then leak-free feature engineering, statistically validated models, explainability, a versioned API, the frontend and finally deployment.

> **Status:** early development. Milestone **M0 (Foundations)** is complete. See the [roadmap](#roadmap) and the full [engineering plan](docs/PLAN.md).

## Planned features

| Feature | What it does | Milestone |
|---|---|---|
| Match Explorer & Replay | Browse any IPL match and replay it ball by ball with full playback controls | M2 |
| Win Probability Engine | Calibrated probability after every ball, with plain-language SHAP explanations | M3 |
| Score Projection | Median projected total, 80% interval, and P(150+ / 170+ / 190+ / 200+) | M4 |
| Player Lab | Batting and bowling profiles with phase, venue, situation and opposition splits | M5 |
| Matchup Lab | Batter vs bowler with sample-size-aware (shrunk) estimates and next-ball distribution | M6 |
| Compare, Ratings, Momentum, Pressure, Teams, Simulator | Transparent derived metrics and Monte Carlo simulation | V1 |

## Architecture

```
Cricsheet JSON → pipelines (ingest · normalize · validate) → DuckDB warehouse
  → leak-free feature tables → ML (train · calibrate · explain · batch-score)
  → serving.duckdb + model registry → FastAPI (/api/v1) → Next.js frontend
```

Read more in [docs/architecture.md](docs/architecture.md) and the [architecture decision records](docs/adr/).

## Tech stack

| Layer | Tools |
|---|---|
| Data | Python 3.12, DuckDB, Parquet, pandera, Typer |
| ML | scikit-learn, LightGBM (+ XGBoost/CatBoost comparisons), SHAP, NumPy Monte Carlo |
| Backend | FastAPI, Pydantic v2, uvicorn |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts, visx, Framer Motion |
| Quality | uv workspace, ruff, mypy (strict), pytest, Vitest, Testing Library, Playwright, GitHub Actions |
| Hosting | Vercel (web), Hugging Face Spaces (API), GitHub Releases (data and model artifacts) |

## Local development

**Prerequisites:** Python 3.12 (managed by [uv](https://docs.astral.sh/uv/)), Node 24 with [pnpm](https://pnpm.io), and [just](https://just.systems) (`uv tool install rust-just`).

```bash
just setup      # install Python + frontend deps and git hooks
just dev-api    # API on http://localhost:8000 (OpenAPI docs at /docs)
just dev-web    # web app on http://localhost:3000
just check      # everything CI runs: lint, types, tests, build
```

## Project structure

```
core/        criciq_core: cricket rules, phase config, shared feature definitions
pipelines/   criciq_pipelines: ingestion → normalization → validation → export
ml/          criciq_ml: features, training, evaluation, inference, explainability, simulation
backend/     criciq_api: FastAPI app (routers → services → repositories)
frontend/    Next.js app
config/      versioned reference config (phases, aliases, franchises)
docs/        plan, architecture, ADRs, model cards, metric definitions
tests/       Python tests (unit, data, features, ml, api)
```

## Roadmap

- [x] **M0** Foundations: monorepo, tooling, CI, design system, app shell
- [ ] **M1** Data warehouse: Cricsheet ingestion, normalization, validation
- [ ] **M2** Match Explorer & Replay: first public deployment
- [ ] **M3** Win Probability
- [ ] **M4** Score Projection
- [ ] **M5** Player Lab
- [ ] **M6** Matchup Lab + ball-outcome model → **MVP v0.1**
- [ ] **V1** Compare, ratings, momentum & pressure, teams, simulator

## Data & attribution

Ball-by-ball data is from [Cricsheet](https://cricsheet.org), used under the [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/).

CricIQ is an independent portfolio project. It is not affiliated with the IPL, the BCCI or any franchise. All predictions and simulations are statistical model estimates, not guarantees, and the project is not intended for betting.

## License

[MIT](LICENSE) © 2026 Mehul Patil
