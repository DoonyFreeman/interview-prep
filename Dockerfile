# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------- #
# Stage 1 — build the Vite SPA. VITE_API_BASE is left empty so the frontend
# talks to the same origin (`/api`), since FastAPI serves the built assets.
# ---------------------------------------------------------------------------- #
FROM node:20-alpine AS frontend
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ENV VITE_API_BASE=""
RUN npm run build        # -> /frontend/dist

# ---------------------------------------------------------------------------- #
# Stage 2 — runtime. Python deps + app + content + the built SPA, served by
# uvicorn. Runs as a non-root user; SQLite lives under ./data (a mounted volume).
# ---------------------------------------------------------------------------- #
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CONTENT_DIR=/app/content \
    DATABASE_URL=sqlite+aiosqlite:///./data/app.db

WORKDIR /app/backend

# Dependencies first for layer caching.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code, content (source of truth, re-seeded on startup), built SPA.
COPY backend/app ./app
COPY content /app/content
COPY --from=frontend /frontend/dist ./app/static

# Non-root user owns the writable data dir (SQLite + WAL).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/backend/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Plain stdlib healthcheck (no curl in slim). Compose also defines one.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
