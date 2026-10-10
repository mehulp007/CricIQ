# ADR-0016: v2 runs on your machine; the hosted demo stays the IPL edition

- **Status:** Accepted
- **Date:** 2026-10-10
- **Supersedes:** the hosting part of ADR-0003 for v2 (v1 keeps it)

## Context

v2 was planned to replace v1 online at its release: a paid Render instance for an API serving
every competition, a GitHub workflow syncing the data every six hours and redeploying, and `v2`
merged into `main`. v2's serving data is about 525 MB across nine databases, and the API settles
near 1 GB of memory once every competition has been browsed; the free Render instance has 512 MB.
The owner decided not to pay for hosting.

## Decision

- **v2 is a local release.** The `v2` branch is the full product (Tests, ODIs, T20Is, the IPL,
  BBL, CPL, PSL and SA20); `just v2-up` downloads and builds the data, scores it and serves the
  API and a production build of the web app at http://localhost:3000. It is tagged `v2.0.0` on
  `v2`, and `v2` is not merged into `main`.
- **`main` stays v1.0.0, the IPL edition**, deployed as before (Vercel and free Render,
  ADR-0003). Its README points to `v2` and how to run it.
- **The data stays fresh locally**: `just sync`, scheduled every six hours with Windows Task
  Scheduler (`scripts/sync_task.ps1`); the running API swaps new data in between requests.
  Quarantined matches are reported by `just sync-status` and the data-quality report. The cloud
  workflow (`data-sync.yml`) is removed.
- **Bounded memory instead of a bigger server**: each database's DuckDB buffer pool is capped
  (`CRICIQ_DUCKDB_MEMORY_LIMIT`, 384 MB), where DuckDB's default allows each of the nine up to 80% of
  RAM.

## Consequences

**Positive**
- No hosting cost, and nothing about the live site changes.
- The local site is a production build: measured on a laptop, every competition's key API calls
  answer within 180 ms (warm p95, median 50 ms), 10,000 simulations take 0.5 s (T20) and 1.2 s
  (ODI), and key pages score 92-95 in Lighthouse (mobile, throttled).

**Negative / accepted trade-offs**
- Seeing v2 needs Python, Node and about 2 GB of disk; the first build takes a few minutes.
- Two editions to describe: each README says which it is.

**Revisit if** free hosting can hold the serving data and the API's memory, or a paid plan
becomes worthwhile: the deployment plan of ADR-0011 still applies.
