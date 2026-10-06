# ADR-0008: Incremental data sync with an ingest log

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

v2 promises "constant updates": stats that include each match within a few days of it being played.
Cricsheet publishes new and corrected matches one to three days after play, both in the full
archives (about 45 MB for the eight competitions) and in small "recently added" feeds (2, 7 and 30
days). Until now every refresh downloaded everything and rebuilt from scratch, with no record of what
changed, and one bad file in a curated competition (an unknown ground in a new IPL season, say)
failed the whole build.

## Decision

- **`criciq-data sync`** fetches the shortest feed that reaches back to the last successful sync: the
  7-day feed within 6 days, the 30-day feed within 28, else the full archives. Only the full archives
  can reveal a match Cricsheet has withdrawn, so `--feed full` is also available on demand.
- **An ingest log** (`data/sync/ingest.duckdb`) records every match's SHA-256, competition, status
  (active, quarantined, withdrawn) and the archive its current version came from. Comparing a feed
  with it classifies each match as new, corrected (a different file for a known match), unchanged
  or withdrawn, and the run history and per-competition update counts live beside it.
- **Only the changes are applied** to the interim tables (a match's rows are dropped and re-added),
  and the result is rebuilt into staging files: the warehouse (about 40 s), validation, the IPL
  copy, the serving database, and scoring with the committed models. Nothing current changes until
  all of that has worked, so a failed sync leaves the data as it was.
- **Quarantine instead of failure.** A new match that cannot be built (unknown ground or team in a
  curated competition) or fails validation is set aside with its reason, and the rest go in; a bad
  correction keeps the previous version. A failure that no incoming match explains still stops the
  sync. `--retry-quarantined` tries them again after a config fix.
- **Publishing while the API runs.** Windows cannot replace a file another process has open, and the
  local API keeps the serving database open. A sync leaves the new file as `serving.duckdb.next`;
  the API swaps it in between requests (waiting for queries in flight, then clearing its caches),
  and at startup if it was down.
- **The web app follows the data version.** Its API requests carry the data version, and the
  metadata that holds it is refreshed every five minutes, so new data shows within minutes instead
  of after the day-long cache. A freshness badge and a "Latest matches" strip show what came in.

## Consequences

**Positive**
- A sync that finds nothing new takes seconds; one that brings matches takes about two minutes end
  to end, measured on real Cricsheet data (31 new matches from the 7-day feed in 1 min 39 s).
- Two incremental syncs on a deliberately stale copy produced warehouses and model outputs identical
  to a full rebuild from the same files, table by table.
- Every version of the data is traceable: the feed files a sync took in are kept under
  `data/raw/feeds/`, and the log names each match's source.

**Negative / accepted trade-offs**
- **Scoring is a full rescore, not incremental.** Scoring every ball takes about 50 seconds, so
  saving per-match model state to score only new balls (as first planned) would add complexity for
  little gain. It is revisited if pooled models in V2-3 make scoring much slower.
- **The interim tables are rewritten whole, not partitioned.** They are about 20 MB for every
  competition; rewriting them takes a second, which partitions would not improve.
- **Withdrawals are only found by a full check.** The recent feeds list additions, not removals.
- The schedule runs locally (Windows Task Scheduler) until the v2.0 launch; the GitHub workflow that
  will run it in the cloud is written but switched off (V2-8).
