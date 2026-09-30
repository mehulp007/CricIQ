# Deployment

CricIQ runs on two free tiers:

| Piece | Host | URL |
|---|---|---|
| Web app (Next.js) | Vercel (Hobby), functions in Mumbai (`bom1`) | https://criciq-eight.vercel.app |
| API (FastAPI + DuckDB) | Render web service (free, Docker), Singapore | https://criciq-api.onrender.com |

Why these hosts rather than the plan's original Hugging Face Spaces is recorded in
[ADR-0003](adr/0003-hosting-vercel-and-render.md).

```
browser ──► Vercel (Next.js server components, cached for 24h)
               │  featured replays: bundled JSON, no API call
               └► Render API (read-only serving.duckdb baked into the image)
```

## API (Render)

The service builds [`docker/backend.Dockerfile`](../docker/backend.Dockerfile) from the repository root.
The image build **is** the data pipeline:

1. The `data` stage downloads the latest Cricsheet archive, then builds, validates and exports the
   serving database (`criciq-data run`). If any validation check or golden scorecard fails, the image
   build fails, so invalid data can never go live.
2. The `runtime` stage installs only the API package and copies in the 8 MB serving database. It runs
   as a non-root user with a container health check.

| Setting | Value |
|---|---|
| Runtime | Docker, `./docker/backend.Dockerfile`, context `.` |
| Plan / region | Free / Singapore |
| Auto-deploy | **Off**. Frontend-only pushes shouldn't rebuild the image and re-run the pipeline, which would burn build minutes. |
| Env | `CRICIQ_ENVIRONMENT=production` (port comes from Render's `PORT`) |

**Redeploy the API** (after backend changes, or to refresh data during an IPL season) by triggering a
manual deploy from the Render dashboard or the Render API. The new image picks up the latest Cricsheet
data automatically.

**Cold starts.** Free Render services sleep after 15 minutes idle and take about 30 seconds to wake. The
web app is designed around this:

- API responses carry `Cache-Control: s-maxage=86400`, and Next.js caches every API fetch for 24 hours,
  so repeat visits rarely reach the API.
- The ten featured replays are bundled into the web app and never depend on the API.
- If the API is asleep, pages show an honest "engine warming up" state with a retry button instead of
  failing.

## Web app (Vercel)

| Setting | Value |
|---|---|
| Project | `criciq`, Git-connected to `mehulp007/CricIQ`, root directory `frontend` |
| Framework | Next.js (auto-detected) |
| Function region | `bom1` (Mumbai), close to Indian users and the Singapore API |
| Env | `CRICIQ_API_URL=https://criciq-api.onrender.com` (server-side only) |
| Protection | Production domain public; preview deployments require Vercel login |

Every push to `main` deploys the web app to production automatically.

## Verifying a deployment

```bash
E2E_BASE_URL=https://criciq-eight.vercel.app just e2e
```

This runs the Playwright suite (desktop and mobile) against production, including a replay served
live by the API.

## Refreshing featured replays

The featured replays bundled with the web app come from the local serving database:

```bash
just data run      # refresh data locally
just featured      # re-export frontend/data/featured
```

Commit the result. Vercel redeploys automatically.
