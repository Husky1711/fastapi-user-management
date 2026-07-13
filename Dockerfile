# Production image for the FastAPI user-management API.
# See docs/CONTAINER_HARDENING.md for runtime (non-root, read-only FS) guidance.

FROM python:3.11-slim-bookworm AS builder

WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.lock

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP__HOST=0.0.0.0 \
    APP__PORT=9000

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app \
    && mkdir -p /app \
    && chown app:app /app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app

COPY --chown=app:app \
    main.py \
    alembic.ini \
    requirements.lock \
    requirements.txt \
    ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app config ./config
COPY --chown=app:app models ./models
COPY --chown=app:app routes ./routes
COPY --chown=app:app schemas ./schemas
COPY --chown=app:app services ./services
COPY --chown=app:app utils ./utils
COPY --chown=app:app scripts ./scripts

USER app
EXPOSE 9000

# Prefer 1 worker per container; scale with replicas (docs/DEPLOYMENT_TOPOLOGY.md).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
