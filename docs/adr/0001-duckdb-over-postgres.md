# ADR-0001: DuckDB + Parquet instead of PostgreSQL

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

The original brief suggested PostgreSQL (with SQLAlchemy) as the primary database. CricIQ's data has these properties:

- **Small:** about 1,200 IPL matches and about 280k deliveries, which is well under 1 GB including derived feature tables.
- **Read-only at serve time:** historical data changes only when the pipeline refreshes, at most weekly during an IPL season.
- **Analytical:** queries are aggregations, window functions and group-bys (splits, as-of features, matchup cubes), not transactional row updates.
- **Zero budget:** hosting must be free. Free managed Postgres tiers either expire after a trial period or cap storage and compute, and they add a network hop and a second service to operate.

## Decision

- The pipeline builds a **DuckDB warehouse** (`data/warehouse/criciq.duckdb`), with Parquet for interim layers.
- The export step produces a slim, read-only **`serving.duckdb`**, which is baked into the API container image at build time.
- The API accesses data only through a **repository layer** (`criciq_api.repositories`) so that the storage engine is an implementation detail.

## Consequences

**Positive**
- Columnar execution makes splits and aggregations fast (tens of milliseconds) without tuning.
- There is no database service to host, secure, back up or pay for, and deployments are atomic (data + code in one image).
- Pipeline, notebooks and API all use the same SQL dialect and the same file.

**Negative / accepted trade-offs**
- There are no concurrent writes. User-generated state (accounts, saved views) would need a different store. This is out of scope for MVP and V1.
- Data refresh requires a redeploy, which is acceptable at a weekly cadence.

**Revisit if** CricIQ adds user accounts, live ingestion, or data volumes that no longer fit comfortably in the API container. The repository layer keeps a move to PostgreSQL contained.
