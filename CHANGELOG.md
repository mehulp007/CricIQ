# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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
