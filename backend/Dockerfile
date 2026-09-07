FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (no editable install, no dev deps)
RUN uv sync --frozen --no-dev

# Copy application source
COPY . .

# Run alembic migrations then start server. --no-sync: the venv is baked
# at build time; without it uv re-syncs on start, pulling dev deps from
# PyPI at runtime (network-dependent boot, mutated venv).
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000"]
