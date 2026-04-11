# ------------------------------------------------------------------------------
#  Sharptoolz Backend – Production Dockerfile (Dokploy)
# ------------------------------------------------------------------------------

# -- Stage 1: Build Dependencies --
FROM python:3.11-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Install build essentials and libraries for WeasyPrint/Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    pkg-config \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry>=2.0.0

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (without dev)
RUN poetry lock && poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

# -- Stage 2: Final Runtime --
FROM python:3.11-slim-bullseye AS runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime system dependencies
# Includes support for: Postgres, WeasyPrint, Cairo, OpenCV, and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxml2-dev \
    libxslt1-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # Playwright dependencies
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Ensure scripts are executable
RUN chmod +x docker-entrypoint.sh

# Install Playwright browser (Chromium)
RUN playwright install chromium

# Create directories for volumes
RUN mkdir -p /app/staticfiles /app/media /app/temp_uploads

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command: Gunicorn with Uvicorn worker for ASGI (Daphne alternative)
CMD ["gunicorn", "serverConfig.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300"]
