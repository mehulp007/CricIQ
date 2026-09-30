# Data Pipeline

CricIQ turns Cricsheet's ball-by-ball JSON into a validated, normalized DuckDB warehouse.
One command rebuilds everything from scratch:

```bash
just data run            # download -> extract -> build -> validate -> report
just data run --no-download   # rebuild from the latest local snapshot
```

The run takes about 10 seconds after download and ends with the validation summary. It also
regenerates [data-quality-report.md](data-quality-report.md).

## Layers

```
cricsheet.org                   config/*.yaml, reference/*.csv (version-controlled)
     │                                   │
     ▼                                   │
data/raw/<data_version>/        immutable snapshot + manifest.json
     │  extract                          │
     ▼                                   │
data/interim/<data_version>/    flat, typed Parquet (one file per table)
     │  build  ◄─────────────────────────┘
     ▼
data/warehouse/criciq.duckdb    normalized warehouse (constraints enforced)
     │  validate
     ▼
data/warehouse/validation.json + docs/data-quality-report.md
```

Everything under `data/` is generated and gitignored. Curated knowledge lives in version-controlled
files:

| File | Purpose |
|---|---|
| `config/competitions.yaml` | Competitions in scope and their rules (e.g. Impact Player from 2023) |
| `config/franchises.yaml` | Franchises and every name they played under, with season ranges |
| `config/venues.yaml` | Canonical grounds and every raw venue string that maps to them |
| `config/phases.yaml` | Powerplay / middle / death definitions per format |
| `config/golden_matches.yaml` | Independently known scorecards the warehouse must reproduce |
| `reference/player_attributes.csv` | Full name, date of birth, country, batting hand, bowling style |
| `reference/player_attributes_overrides.csv` | Documented manual corrections, applied last |

## Steps

### 1. Download (`criciq-data download`)

The step fetches `ipl_json.zip` and the `people.csv` register from Cricsheet. The snapshot is
**content-addressed**: its `data_version` is the date of the latest match plus a hash of both files
(e.g. `2026-05-31.713dafe9`). Downloading unchanged data again reuses the existing snapshot. Every
downstream artifact records the version it was built from.

For offline work, `criciq-data snapshot <zip> <people.csv>` registers local files the same way.

### 2. Extract (`criciq-data extract`)

This step flattens each match into seven typed tables (`matches`, `innings`, `deliveries`,
`wickets`, `replacements`, `match_players`, `registry`) with explicit Arrow schemas. It does no
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

- **Franchises.** Each (season, raw team name) pair is resolved through `franchises.yaml`. Delhi
  Daredevils and Delhi Capitals are one franchise (`DC`); Deccan Chargers (`DCH`) and Sunrisers
  Hyderabad (`SRH`) are different franchises. A team name outside its declared seasons fails the build.
- **Venues.** Raw venue strings map to physical grounds. Pure renames are merged (Feroz Shah Kotla
  becomes Arun Jaitley Stadium); rebuilt or different grounds stay separate (Motera and Narendra Modi
  Stadium, PCA Mohali and Mullanpur). An unmapped venue fails the build.
- **Chronology.** `matches.match_order` is a strict chronological ordinal. It is the key for all
  future *as-of* feature computation, so no feature can see a later match.
- **Derived fields.** These include running score and wickets per delivery, boundary flags that
  exclude run fours, dismissal versus retirement, bowler credit, revised chase targets in balls, and
  Impact Player / concussion substitutes.

The build writes to a temporary file and atomically replaces the warehouse only on success.

### 4. Validate (`criciq-data validate`)

This step runs SQL invariant checks (each returns violating rows, so a failure explains itself)
plus the golden scorecards. Examples:

- innings totals equal the running score after the last ball
- the chase target is the first-innings total plus one, unless a rain rule applied
- margins of victory are consistent with the scores (D/L-aware)
- batters and bowlers belong to the right side's squad
- each side names exactly 11 starting players

The step exits non-zero on any error-level failure. Results go to `data/warehouse/validation.json`
and the committed report.

### 5. Player enrichment (`criciq-data enrich-players`, occasional)

Cricsheet has no biographical attributes. This step links players through their ESPNcricinfo id to
**Wikidata** (full name, date of birth, country; CC0) and to the player's **English Wikipedia**
cricketer infobox (batting hand, bowling style, international side; CC BY-SA 4.0). Parsing is
defensive: wiki links and list templates are unwrapped, styles are normalized to arm plus pace/spin,
and the infobox's international side is preferred over Wikidata citizenship, which proved unreliable.

The result is committed as `reference/player_attributes.csv`, so normal builds never touch the
network. Values that are still missing stay empty unless a correction is certain, in which case it
goes in the overrides file with a note. Coverage is reported in the data-quality report (about 98% for
players with a meaningful sample).

## Refreshing data

During an IPL season:

```bash
just data run                    # fetch new matches and rebuild
just data enrich-players         # only when new players appear
just data build && just data report
uv run python scripts/make_fixtures.py   # only if fixture matches should change
```

## Testing

`tests/fixtures/cricsheet/` holds 14 real matches chosen for edge cases: every golden scorecard, a
double super over, a no-result, D/L chases, umpire miscounts, penalty runs, substitutions and
retirements. The test suite builds a complete warehouse from them, and includes negative tests
that corrupt data to prove the checks catch it. `tests/pipelines/test_full_dataset.py` validates the
full local warehouse when one has been built.
