# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **M3 Win probability**
  - `criciq_ml`: leak-free, as-of match-state features (tested by deleting and rewriting later
    matches), a WASP-style chase dynamic programme, and two monotonic LightGBM models.
  - Evaluation protocol: tuning on 2023-2024, calibration and feature selection by rolling origin on
    pre-test seasons, one-shot test on 2025-2026, a season-by-season backtest and a match-level
    bootstrap against a logistic baseline and a state-only model. Test log loss 0.510 vs 0.549.
  - TreeSHAP explanations grouped into cricket concepts and converted to percentage points.
  - Versioned model registry committed under `models/`, with a promotion gate and a generated model
    card (`docs/model-cards/win-probability.md`). ADR-0004.
  - `criciq-ml` CLI (`train`, `score`, `report`). The API image scores every ball at build time, and
    the API serves precomputed probabilities with no ML libraries.
  - Replay: win probability bar, win probability chart with turning points, "Why this estimate"
    panel, per-ball swings in the commentary, and deep links to any ball (`?ball=innings.seq`).
  - Model Insights page: calibration, backtest, comparisons, rejected features, calibration choice
    and the biggest swings in IPL history.
  - Notebook `02_wp_experiments`: LightGBM vs XGBoost vs CatBoost, the chase feature, the 2019 final.
- **M2 Match Explorer & Replay (first public deployment)**
  - Live at https://criciq-eight.vercel.app (web on Vercel, API on Render).
  - API: `GET /api/v1/matches` (filters, pagination), `/matches/{id}` (full scorecards) and
    `/matches/{id}/timeline` (one payload per replay), all cacheable and gzip-compressed.
  - `criciq-data export`: slim read-only serving database with match summaries. Extraction now streams
    (peak memory 375 MB to 50 MB).
  - Match Explorer with season, team and playoff filters.
  - Match Center: live scoreboard, crease panel, commentary with Impact Player events, worm and
    Manhattan charts, live scorecard, play/step/seek/speed controls and keyboard shortcuts.
  - Featured replays bundled with the web app; honest "engine warming up" state for API cold starts.
  - Typed API client generated from the OpenAPI spec, with a drift test.
  - Playwright end-to-end tests (desktop and mobile), plus CI jobs for e2e and the API Docker image.
  - Docs: deployment guide, ADR-0003 (hosting), README demo GIF and screenshots.
- **M1 Data warehouse**
  - Content-addressed raw snapshots of Cricsheet's IPL archive and people register (`criciq-data download`).
  - Extraction of every match into typed Parquet tables, resolving people by registry id and counting legal balls.
  - Normalized DuckDB warehouse with enforced keys, references and domains: competitions, seasons, franchises, team seasons, venues, players, matches, innings, deliveries, wickets, squads and substitutions.
  - Reference config for franchise renames, venue aliases and competition rules.
  - 17 SQL invariant checks and 6 golden scorecards, with a generated data-quality report.
  - Player attributes (full name, date of birth, country, batting hand, bowling style) from Wikidata and Wikipedia, with documented overrides.
  - `criciq-data run`: one-command rebuild from download to validated warehouse and report.
  - 14 real-match test fixtures covering every data edge case; negative tests prove the checks catch corruption.
  - EDA notebook linking data findings to modelling decisions; docs for the pipeline and data dictionary.
- **M0 Foundations**
  - uv workspace (Python 3.12) with `core`, `pipelines`, `ml` and `backend` packages.
  - `criciq_core`: overs/run-rate arithmetic on legal balls and configurable innings phases (`config/phases.yaml`).
  - `criciq-data` CLI skeleton (`paths` command).
  - FastAPI app with `/healthz` and versioned `/api/v1/meta`.
  - Next.js 16 frontend: "floodlit night match" design tokens, responsive app shell with sidebar and mobile drawer, Overview and About & Methodology pages.
  - Tooling: ruff, mypy (strict), pytest, Vitest and Testing Library, Prettier, pre-commit, `justfile`.
  - GitHub Actions CI for Python and frontend.
  - Docs: engineering plan, architecture overview, ADR-0001 (DuckDB), ADR-0002 (uv workspace on Python 3.12).
