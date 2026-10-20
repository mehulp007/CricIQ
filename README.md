<div align="center">

# CricIQ

### AI-Powered Cricket Intelligence Platform

**Decode the game. Predict the next move.**

[![CI](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/mehulp007/CricIQ/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB)
![Next.js](https://img.shields.io/badge/Next.js-16-000000)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**[Run it on your machine](#run-it-on-your-machine)** · [Live demo (IPL edition)](https://criciq-eight.vercel.app) · [Write-up](https://criciq-eight.vercel.app/writeup) · [Models and results](docs/models.md)

<img src="docs/images/landing.png" alt="CricIQ's home page: the headline 'Decode the game. Predict the next move.' beside a cricket ball drawn in particles, with the deliveries, matches and competitions in the data" width="880">

</div>

---

CricIQ turns every ball of men's cricket recorded by [Cricsheet](https://cricsheet.org) into
interactive analytics: **Tests, ODIs, T20Is, the IPL, BBL, CPL, PSL and SA20**, about 9,900
matches and 4.6 million balls. Replay any match with a live, explained win probability, follow
every series and tournament, and explore players, rivalries, teams and simulations. Each kind of
cricket has models trained on its own matches only.

> **Editions.** The [live demo](https://criciq-eight.vercel.app) is v1.0.0, the IPL edition
> (branch `main`). **This branch, `v3`, has every competition with the redesigned, animated
> interface, and runs on your machine.** v2.0.0 (branch `v2`) has the same competitions with the
> earlier interface.

## Run it on your machine

### 1. Install these once

| Tool | Windows | macOS / Linux |
|---|---|---|
| [Git](https://git-scm.com/downloads) | Installer from git-scm.com | Usually installed already |
| [uv](https://docs.astral.sh/uv/) (it also installs Python for you) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js 24 LTS](https://nodejs.org) | Installer from nodejs.org | Installer from nodejs.org |
| [pnpm](https://pnpm.io) | `npm install -g pnpm` | `npm install -g pnpm` |

**Then close the terminal and open a new one**, so it finds the new programs.

### 2. Download CricIQ and start it

```bash
git clone -b v3 https://github.com/mehulp007/CricIQ.git
cd CricIQ
uv run python scripts/v2_up.py
```

The first run takes about 25 minutes on a laptop. It downloads the data (about 45 MB), builds and
checks every competition (about 1.5 GB on disk), scores every ball with the trained models and
builds the website. When it prints **`CricIQ is up`**, open **http://localhost:3000**. Press
**Ctrl+C** in the terminal to stop it.

### 3. Next time

```bash
cd CricIQ
uv run python scripts/v2_up.py --serve-only
```

It starts in seconds, using the data already built. To add matches played since then, run
`uv run criciq-data sync`; the running site picks them up by itself.

### If something goes wrong

| You see | Do this |
|---|---|
| `'git'`, `'uv'` or `'npm'` is not recognized | Install it (step 1), then open a **new** terminal |
| `npm.ps1 cannot be loaded because running scripts is disabled` | Run `npm.cmd install -g pnpm` instead |
| `pnpm is not installed` or `Node.js is not installed` | Install it (step 1), then open a new terminal |
| `port 3000` or `port 8000 is already in use` | CricIQ is already running in another window: use that one, or close it first |
| `scripts/v2_up.py` does not exist | You have the IPL edition (`main`): run `git checkout v3` inside the folder |
| The page does not open | Wait for `CricIQ is up`, then use http://localhost:3000 |

## What you can do

- **Start with the story**: the home page shows what CricIQ does as you scroll. A cricket ball
  drawn in particles breaks into every delivery in the data, then becomes the 2019 IPL final's
  real win-probability curve, then fans out into simulated outcomes, before you choose a
  competition. Every number in it is the real figure, and visitors who prefer reduced motion get
  the same story as a still page.
- **Find anything fast**: search pages, players, teams and replays with Ctrl/⌘ K, switch
  competitions from the top bar, and choose a light or dark theme: a deep "floodlit night" with a
  fine film grain, or a bright "day match" with warm shadows. Pages glide in as you move between
  them, their headings arriving word by word, and every animation calms down when your device asks
  for reduced motion. Even the 404 page has a ball knock the bails off.
- **A home for every competition**: its numbers count up as they come into view, then the latest
  matches and series, featured replays, the latest season at a glance and the biggest swings in
  its history, each card arriving in turn.
- **Replay any match** ball by ball, with each side's win chance, a projected total and a
  plain-language explanation after every ball. The scoreboard reads like a broadcast: the score's
  digits flip, the win-probability bar glides and glows faster as the pressure on the next ball
  rises, each new ball slides into the feed (wickets, sixes and fours flash), and wickets ring on
  the timeline as the replay reaches them.
- **Series and tournaments**: every international series and World Cup, with tables, knockouts and
  champions.
- **Player Lab**: every player's career in every format, measured against par for their era, with
  ratings, splits and similar players. Each rating grows out along its 0–100 track as you reach it.
- **Matchups and Compare**: any batter against any bowler without over-reading small samples, and
  any two players side by side. A new matchup springs into place with its next-ball odds counting
  up, and two players to compare come in from either side.
- **Teams**: seasons, league tables rebuilt from the balls (identical to the official ones) and head
  to heads. Table rows arrive in turn, and the league's trends draw themselves as they come into
  view.
- **Match Simulator and what-if**: play two limited-overs sides 10,000 times in about half a second,
  or change the score in any replay and see what follows. Tests get a chase calculator.
- **Analytics Lab**: research notes that test ideas like momentum, clutch, the toss and home
  advantage, including the answers that came out "no".
- **Model Insights**: every model against its baseline on matches it never saw.

## How good are the models

Each model is tested once on the 2025–2026 matches, which were never used for training or tuning.

| Competition | Win probability, log loss (lower is better) | Projected total, typical miss |
|---|---|---|
| IPL | **0.510** vs 0.549 baseline | **16.9 runs** vs 18.4 for par |
| BBL, CPL, PSL, SA20 | **0.504** vs 0.516 | **16.8 runs** vs 18.2 |
| T20Is | **0.432** vs 0.458 | **18.1 runs** vs 22.2 |
| ODIs | 0.550 vs 0.552: level, and the site says so | **31.2 runs** vs 38.0 |
| Tests (win, draw or loss) | **0.633** vs 0.651 | **63 runs** vs 67 (mean) |

Full results, what failed and why: [docs/models.md](docs/models.md).

## Screenshots

| The home page's story | A competition's home |
|---|---|
| ![The 2019 IPL final's win probability drawn as a ribbon of particles, with Pollard's six and Malinga's final over marked](docs/images/ribbon.png) | ![The IPL home page: its headline, the way into a replay, players and matchups, and its numbers](docs/images/home.png) |
| **Match replay** | **Player Lab** |
| ![The 2019 final with Chennai Super Kings needing 9 from 6 balls: the scoreboard, a 78% win chance and very high pressure on the next ball](docs/images/replay.png) | ![Virat Kohli's IPL career against par](docs/images/player.png) |
| **Match Simulator** | **Model Insights** |
| ![Mumbai Indians against Chennai Super Kings simulated 10,000 times](docs/images/simulator.png) | ![Model Insights overview: every model against its baseline on the 2025–2026 seasons](docs/images/models.png) |

## How it's built

- **Data:** Cricsheet's ball-by-ball files go into a DuckDB warehouse, are validated against
  invariants, golden scorecards and 27 known results, then exported as one serving database per
  competition.
- **Models:** LightGBM, multinomial regression and empirical Bayes, each tested against a baseline
  and committed with a model card. Every real ball's predictions are computed ahead of time;
  simulations and what-ifs run live.
- **API and site:** FastAPI reads the serving databases; Next.js renders the pages and replays
  each match in the browser.
- **Motion without the weight:** most animation is plain CSS. GSAP and Lenis load only on the home
  page, after it has painted, and Motion only with the match replay, so other pages start with
  about as much JavaScript as before any of it. The particles draw in batches and hold their frame
  rate on a slowed-down CPU, with fewer of them on phones.
- **Quality:** 480+ Python tests, 210+ frontend tests and 400 end-to-end tests on desktop and
  mobile, plus an accessibility scan of every key page in both themes, run in CI on every push.

| Layer | Tools |
|---|---|
| Data and ML | Python 3.12, DuckDB, LightGBM, scikit-learn, SciPy |
| Backend | FastAPI, Pydantic, uvicorn |
| Frontend | Next.js 16, TypeScript, Tailwind CSS, shadcn/ui, Recharts, GSAP, Lenis, Motion, Canvas 2D |
| Quality | uv, ruff, mypy, pytest, Vitest, Playwright, axe-core, GitHub Actions |

More: [architecture](docs/architecture.md) · [data pipeline](docs/data-pipeline.md) ·
[models and results](docs/models.md) · [training](docs/training.md) ·
[decision records](docs/adr/) · [changelog](CHANGELOG.md)

## For developers

The repository has a task runner, [just](https://just.systems) (`uv tool install rust-just`, then
`uv tool update-shell` and a new terminal). `just` lists every task; the main ones:

```bash
just setup      # install dependencies and git hooks
just check      # everything CI runs: lint, types, tests, build
just v2-up      # same as scripts/v2_up.py (--serve-only, --no-download, --dev)
just sync       # take in new and corrected matches
just train-group leagues   # retrain one model group: ipl, leagues, t20i, odi or test
```

```
core/  pipelines/  ml/  backend/  frontend/   the packages and the web app
config/  reference/  models/                  configuration, player data, trained models
docs/  notebooks/  tests/                     documentation, research, tests
```

## Data & attribution

Ball-by-ball data is from [Cricsheet](https://cricsheet.org) under the [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/). Player attributes come from [Wikidata](https://www.wikidata.org) (CC0) and English [Wikipedia](https://en.wikipedia.org) ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)).

CricIQ is an independent portfolio project, not affiliated with the ICC or any board, league or
franchise. Predictions and simulations are statistical estimates, not guarantees, and are not
intended for betting.

## License

[MIT](LICENSE) © 2026 Mehul Patil
