# Contributing to CricIQ

Thanks for your interest! CricIQ is developed in milestone-sized vertical slices. Each milestone is recorded in the [changelog](CHANGELOG.md).

## Setup

```bash
just setup   # Python deps (uv), frontend deps (pnpm), pre-commit hooks
just check   # lint, types, tests, build: the same as CI
```

## Ground rules

1. **No leakage.** Any feature about a player, venue or league must be computed only from matches strictly earlier than the match it describes. New feature code needs a test proving this.
2. **One source of truth for features.** Feature definitions live in `core/` and are imported by both training and serving code. Never re-implement a feature in the API.
3. **Notebooks are for exploration.** Production logic belongs in `pipelines/`, `ml/` or `backend/`, with tests.
4. **Nothing fake in the UI.** Pages ship only when backed by real data and real models. Label every prediction as a model estimate.
5. **Document decisions.** Significant architecture choices get an ADR in `docs/adr/`. New metrics get a formula, rationale, limitations and validation in `docs/metrics.md`.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(pipelines): ...`, `fix(api): ...`, `docs: ...`, `test(ml): ...`.
- Keep PRs focused on one milestone task. CI must be green before merge.
- Update `CHANGELOG.md` under **Unreleased** for user-visible changes.

## Code style

- Python: ruff (lint and format), mypy strict, type hints everywhere.
- TypeScript: ESLint, Prettier (with the Tailwind plugin), strict TS.
