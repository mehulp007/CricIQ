# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **M0 Foundations**
  - uv workspace (Python 3.12) with `core`, `pipelines`, `ml` and `backend` packages.
  - `criciq_core`: overs/run-rate arithmetic on legal balls and configurable innings phases (`config/phases.yaml`).
  - `criciq-data` CLI skeleton (`paths` command).
  - FastAPI app with `/healthz` and versioned `/api/v1/meta`.
  - Next.js 16 frontend: "floodlit night match" design tokens, responsive app shell with sidebar and mobile drawer, Overview and About & Methodology pages.
  - Tooling: ruff, mypy (strict), pytest, Vitest and Testing Library, Prettier, pre-commit, `justfile`.
  - GitHub Actions CI for Python and frontend.
  - Docs: engineering plan, architecture overview, ADR-0001 (DuckDB), ADR-0002 (uv workspace on Python 3.12).
