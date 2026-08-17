# Development image: source-mounted, auto-reloading.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so the layer caches across source edits.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[dev]"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "rag_backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]
