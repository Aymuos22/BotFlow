# ────────────────────────────────────────────────────────────────────────────
# Stage 1: builder
# Install dependencies in an isolated layer so the final image stays lean.
# ────────────────────────────────────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

# System deps for cryptography / psycopg2 compilation (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ────────────────────────────────────────────────────────────────────────────
# Stage 2: runtime
# ────────────────────────────────────────────────────────────────────────────
FROM python:3.10-slim AS runtime

# Non-root user for security.
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser \
    && chown -R appuser:appuser /home/appuser

# Runtime media conversion for inbound WhatsApp voice notes (OGG/AMR -> MP3).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
# Bump BUILD_CACHE_BUST to force Docker to invalidate this layer and all
# subsequent layers (e.g. after changes to app/ that Render's registry
# cache incorrectly serves as a stale hit).
ARG BUILD_CACHE_BUST=3
COPY --chown=appuser:appuser app/ ./app/

# Copy Alembic migration tooling
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser migrations/ ./migrations/

# Operational CLI scripts
COPY --chown=appuser:appuser scripts/ ./scripts/

# Ensure data dir exists for any runtime file drops
RUN mkdir -p ./data

# Ensure Python can find the app package
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser

# ────────────────────────────────────────────────────────────────────────────
# Runtime configuration (override via environment variables or .env file)
# ────────────────────────────────────────────────────────────────────────────
ENV APP_ENV=production
ENV LOG_LEVEL=INFO
ENV APP_VERSION=0.3.0

# Supabase / Postgres
ENV DATABASE_URL=""

# Supabase Storage
ENV SUPABASE_URL=""
ENV SUPABASE_SERVICE_ROLE_KEY=""
ENV SUPABASE_STORAGE_BUCKET="documents"
ENV SUPABASE_JWT_SECRET=""

# Weaviate
ENV WEAVIATE_URL=""
ENV WEAVIATE_API_KEY=""

# LLM — Groq
ENV LLM_PROVIDER="groq"
ENV GROQ_API_KEY=""
ENV LLM_MODEL="llama-3.3-70b-versatile"

# Embeddings — VoyageAI
ENV EMBEDDING_PROVIDER="voyage"
ENV VOYAGE_API_KEY=""
ENV EMBEDDING_MODEL="voyage-3"

# Security
ENV SECRET_KEY=""

USER appuser

EXPOSE 8000

# Health check – matches the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Single worker by default — safe for small instances (~2GB RAM). Scale with replicas or override CMD.
# Local dev only — production uses Render native Python (render.yaml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
