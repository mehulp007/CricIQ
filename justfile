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

# Data pipeline CLI, e.g. `just data paths`
data *args:
    uv run criciq-data {{args}}
