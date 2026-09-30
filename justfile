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
