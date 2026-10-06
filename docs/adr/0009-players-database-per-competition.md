# ADR-0009: A players database with one schema per competition

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

V2-2 brings the BBL, PSL, CPL, SA20 and men's T20Is into the Player Lab. Three things had to be
decided:

- **What "par" means outside the IPL.** Par is what an average player would have produced from the
  same balls (the league rate for the season and phase). A T20I strike rate measured against IPL
  rates, or a PSL economy against an all-T20 average, would mostly measure the competition, not the
  player.
- **Where the tables live.** The serving database is the IPL's, and an IPL regression gate checks it
  table by table, so it cannot change. Yet the API (in V2-4) has to serve any competition, plus a
  player's T20 career across all of them.
- **How to serve them without a second copy of the Player Lab code.** The repository and service
  layers are about 1,000 lines of SQL and assembly written against the serving tables' names.

## Decision

- **Par is per competition and season.** Each competition's tables are built by the unchanged
  `criciq_pipelines.players` code from that competition's v1-shaped copy of the full warehouse
  (`criciq_pipelines.scope`), so its league rates come from its own balls only. The IPL's tables in
  the new database are row for row the serving database's, and a test holds them to that.
- **"All T20" is the union of the competitions' rows**, each keeping its own par. Only the directory
  (`player_index`: role, seasons, latest team) is recomputed over the union, by the same SQL.
- **A separate players database** (`data/exports/players.duckdb`, about 40 MB for every T20
  competition) holds the tables with a `competition_id` column, plus one schema of views per scope
  (`ipl`, `bbl`, `psl`, `cpl`, `sa20`, `t20i`, and `t20` for all of them) with the serving
  database's table names and columns. `criciq-data run` and every sync build it, and the API swaps it
  in like the serving database.
- **The API reads a scope through `search_path`.** `ScopedDatabase` sets a cursor's
  `search_path` to the scope's schema, so the existing Player Lab services answer
  `/api/v2/{competition}/players/...` without changes. In `t20`, an innings' `match_order` is its order
  across every competition, so "most recent" means the same in every scope.
- **Season names** come from configuration: competitions whose seasons span the new year (the BBL,
  `season_spans_new_year`) are named "2023/24"; the others by their year, since Cricsheet's labels
  are not always the names in use (it calls IPL 2008 "2007/08").

## Consequences

**Positive**
- The IPL product is untouched: the serving database and the scored outputs are identical.
- One Player Lab implementation serves seven scopes; V2-4 can move the site onto it page by page.
- Building it takes about 10 seconds on the full data.

**Negative / accepted trade-offs**
- Two databases hold the IPL's player tables until V2-4 retires the v1 routes.
- Ratings, similar players and win probability added are empty outside the serving database until
  the pooled T20 models (V2-3) are fitted for each competition.
- Teams without curated colours (most associate nations) get a neutral grey, so every team tag has
  one.

**Revisit when** V2-4 decides the shape of the multi-competition serving data: the scope schemas may
then hold every table the site reads, not only the Player Lab's.
