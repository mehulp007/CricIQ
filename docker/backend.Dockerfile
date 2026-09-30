# CricIQ API image.
#
# Stage 1 builds the data: it downloads the latest Cricsheet IPL archive, builds
# and validates the warehouse, exports the read-only serving database, and
# scores every ball with the committed win probability model (models/). A
# failed validation fails the image build, so invalid data can never ship.
#
# Stage 2 is the runtime: the API package and the serving database only. The
# API never runs a model, so no ML libraries ship in the runtime image.
#
# Build from the repository root:
#   docker build -f docker/backend.Dockerfile -t criciq-api .

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.12.21

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------------------------------------------------------- data build
FROM python:${PYTHON_VERSION}-slim AS data
COPY --from=uv /uv /bin/uv
# LightGBM needs the OpenMP runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1     && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never CRICIQ_ROOT=/app
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY core core
COPY pipelines pipelines
COPY ml ml
COPY backend backend
RUN uv sync --frozen --no-dev --all-packages

COPY config config
COPY reference reference
COPY models models
RUN uv run --frozen --no-sync criciq-data run --report /tmp/data-quality-report.md     && uv run --frozen --no-sync criciq-ml score

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    CRICIQ_ROOT=/app CRICIQ_ENVIRONMENT=production PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY core core
COPY pipelines pipelines
COPY ml ml
COPY backend backend
RUN uv sync --frozen --no-dev --package criciq-api \
    && useradd --system --uid 10001 criciq

COPY --from=data /app/data/exports/serving.duckdb /app/data/exports/serving.duckdb
USER criciq

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=4)"
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn criciq_api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
