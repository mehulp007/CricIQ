# ADR-0002: uv workspace pinned to Python 3.12

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

CricIQ has four Python components (domain core, data pipelines, ML, API) that must share code, especially **feature definitions**, which must be identical in training and serving. The development machine ships Python 3.14, but the ML stack (LightGBM, XGBoost, CatBoost, SHAP/numba) tends to publish wheels for new Python versions later than the core ecosystem.

## Decision

- Use a **uv workspace**: `core`, `pipelines`, `ml` and `backend` are separate packages with explicit dependencies, sharing one lockfile (`uv.lock`) and one virtual environment.
- Pin **Python 3.12** (`.python-version`, `requires-python = ">=3.12,<3.13"`). uv installs it automatically, independent of the system interpreter.

## Consequences

- Package boundaries enforce the dependency direction (`core ← pipelines/ml/backend`, backend → ml inference only).
- The backend container installs only `criciq-api` and its workspace dependencies, not pipeline tooling.
- Reproducible installs: CI runs `uv sync --locked`.
- Upgrading Python is a deliberate, one-line change once every ML dependency supports the newer version.
