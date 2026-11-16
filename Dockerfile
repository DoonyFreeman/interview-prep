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
    API_DOCS=false \
    DATABASE_URL=sqlite+aiosqlite:///./data/app.db \
    ASSISTANT_INDEX_PATH=/app/assistant-assets/lessons.sqlite3 \
    ASSISTANT_MODEL_DIR=/app/assistant-assets/e5 \
    ASSISTANT_PERSISTENCE_PATH=/app/backend/data/assistant/langgraph.sqlite3

WORKDIR /app/backend

# Dependencies first for layer caching.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code and content are also inputs to the assistant index.
COPY backend/app ./app
COPY content /app/content
COPY scripts/assistant_prepare_index.py /app/scripts/assistant_prepare_index.py

# Non-root user owns the writable data dir (SQLite + WAL).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/backend/data /app/assistant-assets \
    && chown -R appuser:appuser /app
USER appuser

RUN PYTHONPATH=/app/backend python /app/scripts/assistant_prepare_index.py \
    --content-dir "$CONTENT_DIR" \
    --model-dir "$ASSISTANT_MODEL_DIR" \
    --index "$ASSISTANT_INDEX_PATH"

COPY --from=frontend --chown=appuser:appuser /frontend/dist ./app/static

EXPOSE 8000

# Plain stdlib healthcheck (no curl in slim). Compose also defines one.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
