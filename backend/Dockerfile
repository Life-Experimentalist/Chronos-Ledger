FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (no editable install, no dev deps)
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Baked in rather than left to compose, so anyone who pulls this image gets
# a working probe without copying our compose file. /health is on the app
# root, outside /api/v1, so it needs no token and no API key. start-period
# covers `alembic upgrade head`, which runs before uvicorn binds and takes
# longest on a database that has never been migrated.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Copy application source
COPY . .

# Run alembic migrations then start server. --no-sync: the venv is baked
# at build time; without it uv re-syncs on start, pulling dev deps from
# PyPI at runtime (network-dependent boot, mutated venv).
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000"]
