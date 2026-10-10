<div align="center">

# CricIQ

### AI-Powered Cricket Intelligence Platform

**Decode the game. Predict the next move.**

[![CI](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB)
![Next.js](https://img.shields.io/badge/Next.js-16-000000)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**[Live demo](https://criciq-eight.vercel.app)** · [Every competition on your machine](#every-competition-on-your-machine) · [Write-up](https://criciq-eight.vercel.app/writeup) · [Models and results](docs/models.md)

<img src="docs/images/demo.gif" alt="A tour of CricIQ: the last over of the 2019 IPL final replayed ball by ball with win probability, then the Player Lab, Matchups, Compare, Teams, the Match Simulator, the Analytics Lab and Model Insights" width="880">

</div>

---

CricIQ turns every ball of the IPL since 2008 (1,243 matches, about 296,000 balls) into
interactive analytics. Replay any match with a live, explained win probability, explore every
player measured against par, read any rivalry without over-reading small samples, rebuild any
season and simulate any two sides 10,000 times.

> **Two editions.** This branch (`main`) is **v1.0.0, the IPL edition**, which the
> [live demo](https://criciq-eight.vercel.app) serves. **v2.0.0 adds Tests, ODIs, T20Is and the
> BBL, CPL, PSL and SA20**, each with its own models, and runs on your machine
> ([how](#every-competition-on-your-machine)).

## Every competition on your machine

Install [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/)
(it also installs Python), [Node.js 24 LTS](https://nodejs.org) and pnpm (`npm install -g pnpm`),
then **open a new terminal** and run:

```bash
git clone -b v2 https://github.com/mehulp007/CricIQ.git
cd CricIQ
uv run python scripts/v2_up.py
```

The first run takes about 25 minutes on a laptop. When it prints **`CricIQ is up`**, open
**http://localhost:3000**. Step-by-step install commands and a troubleshooting table are in
[the v2 README](https://github.com/mehulp007/CricIQ/tree/v2#run-it-on-your-machine).

## What you can do

- **Replay any match** ball by ball, with each side's win chance, a projected total and a
  plain-language explanation after every ball.
- **Player Lab**: every player's career measured against par for their era, with ratings, splits
  and similar players.
- **Matchups and Compare**: any batter against any bowler without over-reading small samples, and
  any two players side by side.
- **Teams**: every season's league table rebuilt from the balls (identical to the official ones),
  comebacks, collapses and head to heads.
- **Match Simulator and what-if**: play any two sides from any season 10,000 times in about half a
  second, or change the score in any replay and see what follows.
- **Analytics Lab**: is momentum real, is clutch a skill, do rivalries repeat? Tests that could
  have gone either way, "no"s included.
- **Model Insights**: every model against its baseline on seasons it never saw.

## How good are the models

Tested once on the 2025–2026 seasons, never used for training or tuning:

| Model | CricIQ | Baseline |
|---|---|---|
| Win probability, log loss (lower is better) | **0.510** | 0.549 (logistic regression) |
| Projected total, median miss | **16.9 runs**, 80% range holds 80.3% | 18.4 runs (par for the era) |
| Ball outcome, log loss | **1.4895** | 1.5057 (phase and wickets) |
| League tables | Identical to the official tables for all 19 seasons | — |

Full results, what failed and why: [docs/models.md](docs/models.md).

## Screenshots

| Match replay | Player Lab |
|---|---|
| ![Match Center with win probability during the 2019 final](docs/images/replay.png) | ![Virat Kohli's profile against par](docs/images/player.png) |
| **Match Simulator** | **Model Insights** |
| ![Mumbai Indians against Chennai Super Kings simulated 10,000 times](docs/images/simulator.png) | ![Model Insights overview: every model against its baseline on the 2025–2026 seasons](docs/images/models.png) |

## How it's built

- **Data:** Cricsheet's ball-by-ball files go into a DuckDB warehouse, validated by 17 invariant
  checks and 6 golden scorecards, then exported as a read-only serving database.
- **Models:** LightGBM, multinomial regression and empirical Bayes, each tested against a baseline
  and committed with a model card. Every real ball's predictions are computed ahead of time;
  simulations and what-ifs run live.
- **API and site:** FastAPI (Docker on Render) reads the serving database; Next.js (Vercel)
  renders the pages and replays each match in the browser.
- **Quality:** 280+ Python tests, 100+ frontend tests, 110+ end-to-end tests and an
  accessibility scan of every key page, run in CI on every push.

| Layer | Tools |
|---|---|
| Data and ML | Python 3.12, DuckDB, LightGBM, scikit-learn, SciPy |
| Backend | FastAPI, Pydantic, uvicorn |
| Frontend | Next.js 16, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Quality and hosting | uv, ruff, mypy, pytest, Vitest, Playwright, GitHub Actions; Vercel and Render (free tiers) |

More: [architecture](docs/architecture.md) · [data pipeline](docs/data-pipeline.md) ·
[models and results](docs/models.md) · [deployment](docs/deployment.md) ·
[decision records](docs/adr/) · [changelog](CHANGELOG.md)

## For developers

To run this IPL edition locally, install the task runner [just](https://just.systems)
(`uv tool install rust-just`, then `uv tool update-shell` and a new terminal):

```bash
just setup      # install dependencies and git hooks
just data run   # download Cricsheet data, build, validate and export
just ml score   # add every ball's predictions with the committed models
just dev-api    # API on http://localhost:8000 (docs at /docs); then, in a second terminal:
just dev-web    # web app on http://localhost:3000
just check      # everything CI runs: lint, types, tests, build
```

## Data & attribution

Ball-by-ball data is from [Cricsheet](https://cricsheet.org) under the [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/). Player attributes come from [Wikidata](https://www.wikidata.org) (CC0) and English [Wikipedia](https://en.wikipedia.org) ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)).

CricIQ is an independent portfolio project, not affiliated with the IPL, the BCCI or any
franchise. Predictions and simulations are statistical estimates, not guarantees, and are not
intended for betting.

## License

[MIT](LICENSE) © 2026 Mehul Patil
