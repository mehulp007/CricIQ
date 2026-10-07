# CricIQ task runner — run `just` to list recipes.
# Install: `uv tool install rust-just` (or any method from https://just.systems).

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

# Install all Python and frontend dependencies and git hooks
setup:
    uv sync --all-packages
    pnpm --dir frontend install --frozen-lockfile
    uv run pre-commit install

# Lint + format check + type check everything
lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy
    pnpm --dir frontend lint
    pnpm --dir frontend format:check
    pnpm --dir frontend typecheck

# Auto-format Python and TypeScript
fmt:
    uv run ruff check --fix .
    uv run ruff format .
    pnpm --dir frontend format

# Run all tests
test: test-py test-web

test-py:
    uv run pytest --cov

test-web:
    pnpm --dir frontend test

# Everything CI runs
check: lint test
    pnpm --dir frontend build

# Start the API with auto-reload on http://localhost:8000 (docs at /docs)
dev-api:
    uv run uvicorn criciq_api.main:app --reload --port 8000

# Start the web app on http://localhost:3000
dev-web:
    pnpm --dir frontend dev

# Data pipeline CLI, e.g. `just data run` or `just data validate`
data *args:
    uv run criciq-data {{args}}

# Bring every competition up to date from Cricsheet (new, corrected and withdrawn matches),
# e.g. `just sync`, `just sync --feed full` or `just sync --retry-quarantined`
sync *args:
    uv run criciq-data sync {{args}}

# The data version, recent syncs and quarantined matches
sync-status:
    uv run criciq-data sync-status

# Models CLI, e.g. `just ml train score_projection`, `just ml score` or `just ml report`
ml *args:
    uv run criciq-ml {{args}}

# Train one model group's models in order (ipl, leagues, t20i or odi), each on its own
# competitions only; writes data/training/<group>/summary.md. Resumes an interrupted run.
# e.g. `just train-group leagues`, `just train-group t20i --only simulator`, `--fresh`
train-group group *args:
    uv run python scripts/train_group.py train {{group}} {{args}}

# Put every group's current models on the site's data: score, model cards, featured replays
publish-models:
    uv run python scripts/train_group.py publish

# Which models serve each model group (and which still use the pooled T20 fallback)
model-status:
    uv run python scripts/train_group.py status

# Re-execute notebooks in place so their outputs are stored (needs a built warehouse)
notebooks *args:
    uv run --group notebooks python scripts/run_notebooks.py {{args}}

# Regenerate the OpenAPI spec and the frontend's TypeScript types from the API
api-types:
    uv run python -m criciq_api.openapi
    pnpm --dir frontend gen:api

# Re-export the featured replays bundled with the web app (needs the serving database)
featured:
    uv run python -m criciq_api.featured

# End-to-end tests against running servers (E2E_BASE_URL overrides the target)
e2e:
    pnpm --dir frontend e2e

# v2 local runtime: build every competition, score, then serve API + web (Ctrl+C stops)
# e.g. `just v2-up`, `just v2-up --no-download` or `just v2-up --serve-only`
v2-up *args:
    uv run python scripts/v2_up.py {{args}}
