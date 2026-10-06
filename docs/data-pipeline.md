# Data Pipeline

CricIQ turns Cricsheet's ball-by-ball JSON into a validated, normalized DuckDB warehouse holding
every competition it covers: the IPL, the BBL, PSL, CPL and SA20, and men's T20 internationals,
ODIs and Tests. One command rebuilds everything from scratch:

```bash
just data run            # download -> extract -> build -> validate -> report
just data run --no-download   # rebuild from the latest local snapshot
```

`CRICIQ_COMPETITIONS` (comma separated, e.g. `IPL`) limits a run to some competitions; by default
every competition in `config/competitions.yaml` is downloaded and built. All of them (about 9,900
matches and 4.6 million deliveries) extract in about 20 seconds and build in about 40 after
download. The run ends with the validation summary, regenerates
[data-quality-report.md](data-quality-report.md) and a report per other T20 competition
([data-quality/](data-quality/)), and exports the serving and players databases.

## Layers

```
cricsheet.org                       config/*.yaml, reference/*.csv (version-controlled)
     │                                       │
     ▼                                       │
data/raw/<data_version>/            immutable snapshot: one archive per competition,
     │                              the people register, manifest.json
     │  extract                              │
     ▼                                       │
data/interim/<data_version>/        flat, typed Parquet (one file per table)
     │  build  ◄─────────────────────────────┘
     ▼
data/warehouse/cricket.duckdb       every competition (constraints enforced)
     │  validate ──► data/warehouse/validation.json + docs/data-quality-report.md
     │  scope
     ▼
data/warehouse/ipl.duckdb           the IPL in the v1 shape: what the export,
     │                              the models and the reports read today
     │  export
     ▼
data/exports/serving.duckdb         what the API serves (the IPL), scored by the models
data/exports/players.duckdb         Player Lab tables for every T20 competition and all T20
```

Everything under `data/` is generated and gitignored. Curated knowledge lives in version-controlled
files:

| File | Purpose |
|---|---|
| `config/competitions.yaml` | Competitions, how a match is recognised, season rules, which are curated |
| `config/teams/*.yaml` | Teams of each competition family and every name they played under (`ipl.yaml`, `bbl.yaml`, ..., `national.yaml`) |
| `config/venues.yaml` | Curated grounds (every IPL ground) and every raw venue string that maps to them |
| `config/venue_countries.yaml` | Countries and renames for grounds added automatically |
| `config/phases.yaml` | Phase definitions per format (T20, ODI, open-ended Test) |
| `config/golden_matches.yaml` | Independently known scorecards the warehouse must reproduce |
| `reference/player_attributes.csv` | Full name, date of birth, country, batting hand, bowling style |
| `reference/player_attributes_overrides.csv` | Documented manual corrections, applied last |

## Steps

### 1. Download (`criciq-data download`)

The step fetches the archive of every selected competition (`ipl_json.zip`, `bbl_json.zip`,
`t20s_male_json.zip`, `odis_male_json.zip`, `tests_male_json.zip`, ...) and the `people.csv`
register. The snapshot is **content-addressed**: its `data_version` is the date of the latest match
plus a hash of every file (e.g. `2026-09-17.103eadea`). Downloading unchanged data again reuses the
existing snapshot. Every downstream artifact records the version it was built from.

For offline work, `criciq-data snapshot <zip>... <people.csv>` registers local files the same way.

### 2. Extract (`criciq-data extract`)

This step flattens each match into seven typed tables (`matches`, `innings`, `deliveries`,
`wickets`, `replacements`, `match_players`, `registry`) with explicit Arrow schemas, including
Test details (declarations, forfeits, penalty runs, wins by an innings) and bowl-outs. It does no
cricket interpretation beyond two things:

- **Name resolution.** Every person is resolved to their Cricsheet id through the match's own
  registry, never by name.
- **Legal-ball counting.** Wides and no-balls do not advance the over. Cricsheet's `actual_delivery`
  label repeats on a wide, and a few overs genuinely had 5 or 7 balls, so legal balls are counted,
  never assumed.

A name missing from the registry, or runs that don't add up, fails the step immediately.

### 3. Build (`criciq-data build`)

This step loads interim tables and reference config into the schema in
[`pipelines/src/criciq_pipelines/sql/schema.sql`](../pipelines/src/criciq_pipelines/sql/schema.sql).
Primary keys, foreign keys, `NOT NULL` and `CHECK` constraints are enforced by DuckDB, so a build
that completes already guarantees referential integrity.

- **Competitions.** A match joins the first competition whose rule it meets: club leagues by
  Cricsheet event name, internationals by match type, men's matches only. The archive it came from
  does not matter, so any Cricsheet feed can be ingested; matches that belong to no competition
  (women's cricket, county games) are left out.
- **Seasons.** The BBL spans the new year, so its seasons are Cricsheet's labels ("2023/24" is BBL
  2024, the year it ends); the IPL's labels are clean too. Leagues played within a year (PSL, CPL,
  SA20) and internationals use the calendar year: Cricsheet labels the PSL 2020 playoffs, played in
  November 2020, as "2020/21".
- **Teams.** Each (competition, season, raw team name) is resolved through `config/teams/`. Delhi
  Daredevils and Delhi Capitals are one IPL franchise (`DC`); Deccan Chargers (`DCH`) and Sunrisers
  Hyderabad (`SRH`) are different franchises; Barbados Tridents and Barbados Royals are one CPL
  franchise. A national side is one team across formats (`IND`), with a team-season per
  competition (`ODI-IND-2023`).
- **Venues.** Raw venue strings map to physical grounds. Curated grounds (`venues.yaml`) merge pure
  renames (Feroz Shah Kotla becomes Arun Jaitley Stadium) and keep rebuilt grounds apart (Motera and
  Narendra Modi Stadium). Other grounds are added automatically: named from the text before the
  first comma, placed with `venue_countries.yaml`, and listed in `auto_added` for review. Its
  `merges` join sponsors' names and spellings of one ground (Westpac Stadium and Sky Stadium), and
  its `shared` list splits the few names several grounds use by the match's city: Cricsheet calls
  grounds in Karachi and Bermuda "National Stadium", and has three County Grounds and four Nehru
  Stadiums. A shared name in a city the list does not know fails the build instead of guessing.
- **Curated or not.** In a `strict` competition (the IPL) an unknown team or venue fails the build.
  Elsewhere new teams and venues are added automatically, so a new associate nation never stops a
  refresh.
- **Quarantine.** A match with a source error that would break the warehouse's keys (one register
  id on both sides, a player missing from the register) is set aside in `quarantine` instead of
  failing the build; in a curated competition it fails the build.
- **Chronology.** `matches.match_order` is a strict chronological ordinal within a competition and
  `global_order` across all of them. They are the keys for *as-of* features, so no feature can see
  a later match.
- **Derived fields.** These include running score and wickets per delivery, boundary flags that
  exclude run fours, dismissal versus retirement, bowler credit, revised chase targets in balls,
  follow-ons, innings totals with penalty runs, and Impact Player / concussion substitutes.

The build writes to a temporary file and atomically replaces the warehouse only on success.

### 4. Validate (`criciq-data validate`)

This step runs SQL invariant checks (each returns violating rows, so a failure explains itself)
plus the golden scorecards. Checks are format-aware: limited-overs rules skip Tests, and Test results
have their own. Examples:

- innings totals equal the running score after the last ball, plus penalty runs
- the chase target is the first-innings total plus one, unless a rain rule applied
- margins of victory are consistent with the scores (D/L-aware), including innings wins in Tests
- a Test has at most four innings
- batters and bowlers belong to the right side's squad
- each side names 11 starting players (12 under the 2005-06 supersub rule)

In a curated competition every violation is an error. Elsewhere the source has known quirks (rain
reductions without a recorded method, associate matches with inconsistent margins, sides of ten),
reported as notes per competition rather than failing the build. The step exits non-zero on any
error-level failure. Results go to `data/warehouse/validation.json` and the committed report.

### 5. Scope

The export, the models and the reports were written for the IPL. Until they are made
multi-competition, `criciq_pipelines.scope` copies the IPL out of the full warehouse into
`data/warehouse/ipl.duckdb` with exactly the v1 tables and columns, and an IPL regression test
(`tests/pipelines/test_ipl_regression.py`) checks that the IPL warehouse and the scored serving
database are unchanged, table by table.

Innings phases follow each match's own format. Data code (player, team and simulator tables, the
API's splits) phases a delivery with `PhaseConfig.sql_case(over, format)`, which reads
`competitions.format`, so T20, ODI and Test balls can sit in one query. Model code (win probability,
projection, ball outcome, ratings, similar players, the simulator) uses `model_phases()`: the v1
models are T20 models (`MODEL_FORMAT`), and the ML loaders refuse a database holding other formats
rather than score them with T20 phases. Per-format models replace that guard in V2-3, V2-5 and V2-6.

### 6. Player enrichment (`criciq-data enrich-players`, occasional)

Cricsheet has no biographical attributes. This step links players through their ESPNcricinfo id to
**Wikidata** (full name, date of birth, country; CC0) and to the player's **English Wikipedia**
cricketer infobox (batting hand, bowling style, international side; CC BY-SA 4.0). Parsing is
defensive: wiki links and list templates are unwrapped, styles are normalized to arm plus pace/spin,
and the infobox's international side is preferred over Wikidata citizenship, which proved unreliable.
A player Cricsheet knows by two ESPNcricinfo ids is matched on whichever Wikidata records; requests
the server drops or throttles are retried.

The step covers every player in the full warehouse (6,233 with an ESPNcricinfo id). Players already
in the file keep their row, so adding players never changes the attributes the committed models were
trained on; `--refresh` reads everyone again. The result is committed as
`reference/player_attributes.csv`, so normal builds never touch the network. Values that are still
missing stay empty unless a correction is certain, in which case it goes in the overrides file with a
note.

Coverage of players with a meaningful sample (100 balls faced or 120 bowled), from the reports:
batting hand for 99.7% in the BBL, 97.8% in the IPL, 97.7% in the PSL, 95.5% in the CPL and 93.2% in
the SA20, but 46.8% in T20Is, where most associate nations' players have no Wikipedia article.
Everything that uses an attribute treats a missing one as its own "unknown" category (a split,
a matchup term, a simulator prior) rather than dropping the ball.

### 7. Players database (`criciq-data export-players`)

The Player Lab tables (innings, ball-level cells, phases, fielding, seasons, the directory) for every
T20 competition, and for all T20 cricket together, go to `data/exports/players.duckdb` (ADR-0009).
Each competition's tables are built by the serving database's code from that competition's own
v1-shaped copy, so **par is the competition's own rate for the season and phase**: a PSL strike rate
is judged against the PSL. The IPL's tables are identical to the serving database's. "All T20" puts a
player's rows from every competition together, each with its own par. One schema of views per scope
(`ipl`, `bbl`, ..., `t20`) lets the API serve any of them with the same queries
(`/api/v2/{competition}/players`). It takes about 10 seconds; `run` and every sync build it.

Seasons are named the way the competition names them: "2023/24" where seasons span the new year (the
BBL, `season_spans_new_year` in `config/competitions.yaml`), else the year.

### Data-quality reports (`criciq-data report`)

[data-quality-report.md](data-quality-report.md) covers the IPL in detail and every competition in
summary. Each other T20 competition has its own report in [data-quality/](data-quality/) with the
same sections (contents, coverage by season, every check with the matches behind its notes, golden
scorecards, recorded anomalies, attribute coverage) plus its teams (curated or added, with attribute
coverage per team), quarantined matches and grounds added automatically, for review.

## Known gaps in the source

- **Afghanistan.** Cricsheet holds no matches involving Afghanistan, in any format.
- **Some T20Is are missing**: Cricsheet's archive does not hold every match (it has 118 of Virat
  Kohli's 125 T20Is), so T20I career totals can fall short of official ones.
- **Coverage starts** in 2001 (Tests), 2002 (ODIs) and 2005 (T20Is): Cricsheet's ball-by-ball
  record of earlier internationals is not available.
- **Pitch, weather and session times** are not in the data.

## Keeping data up to date (sync)

Cricsheet publishes each match one to three days after it is played. A sync takes in only what
changed (ADR-0008):

```bash
just sync                        # new, corrected (and, on a full check, withdrawn) matches
just sync --feed full            # check every archive, which also finds withdrawn matches
just sync --retry-quarantined    # try quarantined matches again after a config fix
just sync-status                 # data version, recent runs, quarantined matches
```

1. **Feed.** The shortest one that reaches back to the last successful sync: Cricsheet's 7-day
   additions within 6 days, the 30-day ones within 28, else the full archives. Downloads retry a
   dropped connection three times (after 5, 20 and 60 seconds).
2. **Diff.** Each match of a selected competition is compared with the **ingest log**
   (`data/sync/ingest.duckdb`) by the SHA-256 of its file: new, corrected, unchanged or withdrawn.
3. **Apply.** Only those matches' rows change in the interim tables; the warehouse, validation, the
   IPL copy, the serving database (every ball scored) and the players database are rebuilt, all into
   staging files.
4. **Quarantine.** A new match that cannot be built (an unknown ground or team in the strict IPL)
   or fails validation is set aside with its reason and the rest go in; a bad correction keeps the
   previous version. Fix the config (e.g. add the ground to `config/venues.yaml`), then
   `just sync --retry-quarantined`. A failure no incoming match explains stops the sync and changes
   nothing.
5. **Publish.** The staging files replace the current ones, the files the sync took in are kept
   under `data/raw/feeds/`, and the run is recorded (`sync_runs`, `data_updates`). The API and the
   site's freshness badge report the update.

While the local API runs, Windows will not let the serving database be replaced; the sync leaves it
as `serving.duckdb.next` and the API swaps it in on its next request (or at startup).

Measured on real Cricsheet data (2026-10-06): a sync with nothing new takes a few seconds (the first
one also records the ingest log, about 35 seconds); 31 new matches from the 7-day feed took 1 min
39 s end to end; a full check of all eight archives took 4 minutes. On a deliberately stale copy,
two syncs produced warehouses and model outputs identical to a full rebuild.

**On a schedule (local).** `scripts/sync_task.ps1` registers a Windows scheduled task that runs the
sync every six hours while you are logged in and appends to `data/sync/sync.log`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_task.ps1            # register
powershell -ExecutionPolicy Bypass -File scripts/sync_task.ps1 -RunOnce   # run the task's command now
powershell -ExecutionPolicy Bypass -File scripts/sync_task.ps1 -Remove    # unregister
```

At the v2.0 launch the same sync runs in GitHub Actions (`.github/workflows/data-sync.yml`, written
but switched off until V2-8; see [deployment.md](deployment.md)).

## Rebuilding from scratch

```bash
just data run                    # download every archive and rebuild (also records the ingest log)
just data enrich-players         # look up players new to the file (--refresh: everyone)
just data build && just data report   # the main report and one per T20 competition
uv run python scripts/make_fixtures.py   # only if fixture matches should change
```

## Local v2 runtime

v2 is built and checked on one PC before it goes live. One command builds every competition,
scores every ball and serves the API and the web app together:

```bash
just v2-up                  # download, build, validate, score, then serve (Ctrl+C stops)
just v2-up --no-download    # rebuild from the latest local snapshot
just v2-up --serve-only     # serve what is already built
```

The site is at http://localhost:3000 (use `localhost`: the dev server does not hydrate on
`127.0.0.1`) and the API docs at http://localhost:8000/docs (the Player Lab of every T20
competition is under `/api/v2`). The data-quality reports of a local run go to
`data/data-quality-report.md` and `data/data-quality/`, leaving the committed ones alone.

Measured on the development laptop with all eight competitions (2026-10-06): the data step takes
about 70 seconds after download (extract 20, build 40, validate and export the rest) and scoring
about 50; the dev servers are ready within a minute. Everything under `data/` takes about 0.8 GB:
raw archives 0.07 GB, interim Parquet 0.02 GB, warehouses 0.66 GB (the full `cricket.duckdb` is
about 0.6 GB) and the serving database 0.03 GB.

## Testing

`tests/fixtures/cricsheet/` holds 33 real matches chosen for edge cases: every golden scorecard, a
double super over, a no-result, D/L chases, umpire miscounts, penalty runs, substitutions and
retirements in the IPL; and from the other competitions a BBL season spanning two years, the PSL's
inconsistent labels, the PSL and CPL 2023 finals (golden), a renamed CPL franchise, a bowl-out, a quarantined source error, a side of ten,
the 2019 World Cup final, supersubs, and Tests with a draw, a declaration, a follow-on and an
innings win. The test suite builds a complete warehouse from them, and includes negative tests that
corrupt data to prove the checks catch it. `tests/pipelines/test_full_dataset.py` validates the full
local warehouse when one has been built.
