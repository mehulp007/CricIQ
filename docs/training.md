# Training the models

Every kind of cricket on CricIQ has models of its own, trained only on its own matches
([ADR-0013](adr/0013-models-per-group.md)). The **model groups** are in
`config/model_groups.yaml`:

| Group | Trains on and serves | Settings | Models |
|---|---|---|---|
| `ipl` | IPL | `config/models/ipl/` | `models/` (`CURRENT.IPL`) |
| `leagues` | BBL, CPL, PSL, SA20 | `config/models/leagues/` | `models/leagues/` |
| `t20i` | Men's T20 internationals | `config/models/t20i/` | `models/t20i/` |
| `odi` | Men's ODIs | `config/models/odi/` | `models/odi/` |

Training runs on your own computer; nothing is sent anywhere.

## Before you start

- **Tools on PATH.** In PowerShell, from the repository folder:

  ```powershell
  $env:Path = "C:\Users\HP\AppData\Roaming\Python\Python312\Scripts;$PWD\.venv\Scripts;$env:Path"
  ```

  (`uv` and `just` were installed there; this lasts for that PowerShell window.)
- **Data built.** The warehouse and its copies must exist (`just v2-up --no-download` builds
  them; the scheduled sync keeps them current). The runner builds a missing copy itself.
- **The local site stopped.** Press Ctrl+C in the window running `just v2-up`. The runner refuses
  to start while ports 8000 or 3000 are in use: training needs the CPU, and the last steps
  rewrite the files the site serves.
- **Power.** Plug the laptop in. The runner asks Windows not to sleep while it works, but closing
  the lid can still suspend it.

## Train a group

```powershell
just train-group leagues
```

It runs, in order, each step printing as it goes:

1. the next-ball model (about 30-45 min for the leagues, 45-60 min for T20Is),
2. win probability (about 5-15 min),
3. the score projection (about 5-15 min),
4. scoring every competition, so the ratings see the new win probabilities (about 10 min),
5. the ratings (about a minute),
6. the match simulator's backtest (about 20-40 min for the leagues, 15-30 min for T20Is).

Each model is switched on (promoted) only if it passes its test against its baseline on
2025-2026 matches. One that fails is kept, reported, and the run carries on. The times are
estimates for this laptop.

When it finishes, `data/training/<group>/summary.md` has a table of every model: its version,
whether it passed, how long it took and its test result, then the details (each competition's
result, the gate's reasons for a failure, feature candidates that looked better before the test
years). The whole output is in `data/training/<group>/training.log`.

Train one group at a time; the runner refuses a second one while one is going.

### If it stops part-way

Run the same command again: it resumes, skipping the models already finished in that run.
`--fresh` starts over with new versions.

### Options

```powershell
just train-group t20i --only simulator     # only some models (in the usual order)
just train-group leagues --fresh           # start a new run instead of resuming
```

## Publish

When the groups you are training are done:

```powershell
just publish-models
```

This scores every competition with its group's current models, writes the model cards
(`docs/model-cards/<group>/`) and the Model Insights data (`frontend/data/models/<group>/`), and
re-exports the featured replays. `data/training/publish-summary.md` says what ran and whether any
competition still uses a pooled T20 model.

Then look at the site with `just v2-up --serve-only`.

## Check what serves each group

```powershell
just model-status
```

lists, for each group, the version of each model serving it, and marks a model still borrowed
from the pooled T20 models (`pooled T20 fallback`).

## Retraining later

The same commands retrain a group on newer data, for example after a season:
`just train-group ipl`, `just train-group odi`. A new run names the next version itself (1.0.0
is followed by 1.1.0) and writes it into the group's settings; the previous versions stay in the
registry, and a new one replaces the current one only if it passes its gates.
