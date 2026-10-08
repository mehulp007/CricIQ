# ADR-0003: Host the web app on Vercel and the API on Render

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

The original design proposed Vercel for the frontend and Hugging Face Spaces for the API. At deployment time,
Vercel and Render accounts were already connected to the project's GitHub. A Hugging Face account
would have been a new account to create and manage for a single service. Constraints:

- **₹0 hosting**, with no expiring trials.
- The API image must contain its data (see ADR-0001) and be rebuilt reproducibly.
- The site must feel fast for visitors even though free API hosts sleep when idle.

## Decision

- **Web app → Vercel Hobby**, Git-connected with root directory `frontend`, and serverless functions
  pinned to Mumbai (`bom1`).
- **API → Render free web service** (Docker, Singapore). The image build runs the full data pipeline
  and fails on any validation error. Auto-deploy is off, so frontend-only pushes don't consume build
  minutes.
- **Design for cold starts rather than paying to avoid them:** 24-hour caching of API responses in
  Next.js and via `s-maxage`, featured replays bundled into the web app, and an explicit "engine warming
  up" state with retry.

## Consequences

**Positive**
- Both services are free and use existing, already-authorised accounts.
- A deploy is reproducible from a commit, and data validation gates every API release.
- The landing page and featured replays never wait on the API.

**Negative / accepted trade-offs**
- A cold Render instance takes about 30 seconds to wake. The first uncached request after idle is
  slow; the UI explains this instead of timing out silently.
- Render's free instance hours are shared across the workspace. That's fine for portfolio traffic;
  revisit if usage grows.

**Revisit if** traffic needs an always-on API (a paid Render instance or Cloud Run with minimum
instances), or when live inference (M3+) makes cold starts more noticeable.
