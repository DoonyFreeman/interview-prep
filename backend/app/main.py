"""FastAPI application entry point.

On startup it initializes the database and seeds course content from markdown.
Heavy work is delegated to the LLM at request time; the app itself stays light.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import auth, courses, lessons, quizzes
from app.config import get_settings
from app.content.seed import seed_from_dir
from app.database import SessionLocal, init_db


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
    app.include_router(lessons.router, prefix="/api", tags=["lessons"])
    app.include_router(quizzes.router, prefix="/api", tags=["quiz"])

    return app


app = create_app()
