"""FastAPI application entry point.

On startup it initializes the database and seeds course content from markdown.
Heavy work is delegated to the LLM at request time; the app itself stays light.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import (
    admin,
    auth,
    cat,
    courses,
    glossary,
    lessons,
    pet,
    progress,
    quizzes,
    roadmap,
    search,
)
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
    app.include_router(pet.router, prefix="/api", tags=["pet"])
    app.include_router(cat.router, prefix="/api", tags=["cat"])
    app.include_router(search.router, prefix="/api", tags=["search"])
    app.include_router(roadmap.router, prefix="/api", tags=["roadmap"])
    app.include_router(admin.router, prefix="/api", tags=["admin"])

    _mount_spa(app)
    return app


#: Revalidate on every load — not "don't store". Starlette's ``FileResponse``
#: doesn't answer ``If-None-Match``, so this is a full re-fetch rather than a
#: 304; at ~1 KB for `index.html`, and only on a real page load (client-side
#: routing never re-fetches it), that is cheaper than the staleness it prevents.
NO_CACHE = "no-cache"
#: Safe only for content-hashed filenames: a new build is a new URL.
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
#: For files with stable names that still change between releases.
SHORT_CACHE = "public, max-age=3600"


class _CachedStatic(StaticFiles):
    """``StaticFiles`` that stamps a fixed ``Cache-Control`` on what it serves.

    Starlette sets ETag and Last-Modified but no Cache-Control, which leaves
    browsers guessing — the very thing that pinned mobile clients to an old
    build. Hashed assets deserve the strongest possible answer instead.
    """

    def __init__(self, *args, cache_control: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cache_control = cache_control

    def file_response(self, *args, **kwargs) -> FileResponse:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = self._cache_control
        return response


def _mount_spa(app: FastAPI) -> None:
    """Serve the built SPA same-origin (Docker), with client-side-routing fallback.

    Registered last so it never shadows ``/api``, ``/health`` or ``/docs``. Any
    path that isn't a real file falls back to ``index.html`` so deep links like
    ``/glossary`` work on a hard refresh. Skipped when the build is not present.

    Being registered last only protects the routes that *exist*: an unmatched
    ``/api/...`` would otherwise fall through to this catch-all and answer
    ``200 text/html``. That turns a typo or a route that failed to register into
    a confusing client-side parse error instead of an honest 404 — and hides a
    bad deploy from any smoke check. So API-shaped paths 404 here rather than
    rendering the SPA.

    **Caching is explicit, because the default is silently wrong.** Without a
    ``Cache-Control`` header browsers fall back to *heuristic* caching off
    ``Last-Modified`` — and mobile Safari happily reuses a stale ``index.html``
    for a long time. Since that HTML names the content-hashed bundles, a stale
    copy pins the whole app to the previous release: a deploy ships and the
    phone keeps showing the old site. So:

    - ``index.html`` — ``no-cache``: fetched fresh on every real page load. At
      about a kilobyte, and never re-fetched during client-side routing, that
      is far cheaper than the staleness it prevents.
    - ``/assets/*`` — immutable for a year. The filenames contain a content
      hash, so a new build is a new URL and can never collide.
    - everything else (favicons, ``site.webmanifest``) — an hour. These keep
      stable names *and* do change between releases, so neither extreme fits.
    """
    if not STATIC_DIR.is_dir():
        return

    index_file = STATIC_DIR / "index.html"
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            _CachedStatic(directory=assets_dir, cache_control=IMMUTABLE_CACHE),
            name="assets",
        )

    #: Prefixes that belong to the server, never to client-side routing.
    api_prefixes = ("api", "health", "docs", "redoc", "openapi.json")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        head = full_path.split("/", 1)[0]
        if head in api_prefixes:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file() and assets_dir not in candidate.parents:
            return FileResponse(candidate, headers={"Cache-Control": SHORT_CACHE})
        return FileResponse(index_file, headers={"Cache-Control": NO_CACHE})


app = create_app()
