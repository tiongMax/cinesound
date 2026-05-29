# CineSound backend container.
# Two-stage isn't worth it here — uv install + a small Python app fit in one stage.

FROM python:3.11-slim

# uv is the only build dep we need
RUN pip install --no-cache-dir uv==0.11.5

WORKDIR /app

# Install deps first (cached layer when only app code changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Now copy the rest
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Railway injects $PORT
EXPOSE 8000

# Run migrations on every boot (idempotent — only pending ones apply), then start
CMD ["sh", "-c", "uv run python -m scripts.migrate && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
