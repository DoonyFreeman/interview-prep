"""FastAPI application entry point.

On startup it initializes the database and seeds course content from markdown.
Heavy work is delegated to the LLM at request time; the app itself stays light.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import auth, courses, glossary, lessons, progress, quizzes
from app.config import get_settings
from app.content.seed import seed_from_dir
from app.database import SessionLocal, init_db

# The built SPA (Vite ``dist/``) is copied here in the Docker image. When the
# directory is absent (local dev, tests) static serving is skipped and the API
# runs on its own — so this is a no-op for the existing test suite.
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_from_dir(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Interview Prep API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(courses.router, prefix="/api", tags=["courses"])
    app.include_router(glossary.router, prefix="/api", tags=["glossary"])
    app.include_router(lessons.router, prefix="/api", tags=["lessons"])
    app.include_router(quizzes.router, prefix="/api", tags=["quiz"])
    app.include_router(progress.router, prefix="/api", tags=["progress"])

    _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    """Serve the built SPA same-origin (Docker), with client-side-routing fallback.

    Registered last so it never shadows ``/api``, ``/health`` or ``/docs``.
    Hashed build assets get long-cache headers via ``StaticFiles``; any other
    path falls back to ``index.html`` so deep links like ``/glossary`` work on
    a hard refresh. Skipped entirely when the build is not present.
    """
    if not STATIC_DIR.is_dir():
        return

    index_file = STATIC_DIR / "index.html"
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file() and assets_dir not in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
