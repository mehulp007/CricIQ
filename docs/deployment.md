# Deployment

CricIQ runs on two free tiers:

| Piece | Host | URL |
|---|---|---|
| Web app (Next.js) | Vercel (Hobby), functions in Mumbai (`bom1`) | https://criciq-eight.vercel.app |
| API (FastAPI + DuckDB) | Render web service (free, Docker), Singapore | https://criciq-api.onrender.com |

Why these hosts rather than the originally planned Hugging Face Spaces is recorded in
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
2. The same stage scores every ball with the committed models (`criciq-ml score`), adding win
   probabilities, explanations and first-innings score projections to the serving database. It
   never retrains (ADR-0004).
3. The `runtime` stage installs only the API package (no ML libraries) and copies in the 12 MB serving
   database. It runs as a non-root user with a container health check.

| Setting | Value |
|---|---|
| Runtime | Docker, `./docker/backend.Dockerfile`, context `.` |
| Plan / region | Free / Singapore |
| Auto-deploy | **Off**. Frontend-only pushes shouldn't rebuild the image and re-run the pipeline, which would burn build minutes. |
| Env | `CRICIQ_ENVIRONMENT=production` (port comes from Render's `PORT`) |

**Redeploy the API** (after backend changes, or to refresh data during an IPL season) by triggering a
manual deploy from the Render dashboard or the Render API. The new image picks up the latest Cricsheet
data automatically.

The web app caches API responses for 24 hours, and that cache survives web deployments. Once the new
API is live, **invalidate the `criciq-api` cache tag** on the Vercel project (dashboard, CLI or API)
so pages pick up the new responses immediately.

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

## Releasing a new model version

Training is an explicit, reviewed step, never part of a deploy:

```bash
just data run      # latest data locally
just ml train win_probability    # or score_projection: tune, evaluate, backtest, gate
just ml score      # score the local serving database
just ml report     # regenerate the model card and the Model Insights data
just featured      # re-export featured replays with the new probabilities
```

Bump `version` in the model's config (`config/models/*.yaml`) first. Review the model card diff, commit
`models/`, then trigger a Render deploy.

## Refreshing featured replays

The featured replays bundled with the web app come from the local serving database:

```bash
just data run      # refresh data locally
just featured      # re-export frontend/data/featured
```

Commit the result. Vercel redeploys automatically.
