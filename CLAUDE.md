# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Web app for technical-interview prep. A user reads deep theory on a topic, then
an LLM quizzes them and **grades each answer against this site's own knowledge
base** (the lesson text + an authored reference answer) — not against the model's
general knowledge. The grader returns a score + written review; on demand it
gives a Socratic hint or links back to the exact theory section. Progress is
tracked per **concept** with SM-2 spaced repetition, so weak concepts resurface.

Audience is private (author + a friend), so the stack is deliberately light:
**FastAPI + SQLAlchemy 2.0 (async) + SQLite (WAL)**, no Redis. Static content is
cached in memory. The LLM (Gemini) is called **only** at request time for answer
evaluation and hints — everything else is plain DB/memory reads.

Status: foundation only (DB layer, models, app skeleton). Frontend, content
seed, auth, LLM, and quiz/progress services are not built yet.

## Commands

All backend commands run from `backend/`.

```bash
# Environment (recreate .venv if the project was moved — venvs hardcode paths)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # runtime
pip install -r requirements-dev.txt       # + pytest

cp .env.example .env                       # fill GEMINI_API_KEY, JWT_SECRET

# Run (creates backend/data/app.db and all tables on startup via lifespan)
uvicorn app.main:app --reload              # http://127.0.0.1:8000  — /health, /docs

# Tests
pytest                                     # whole suite (tests/)
pytest tests/test_x.py::test_name          # a single test
```

## Architecture

Layered, dependency-light. Big picture you can't get from one file:

- **Content vs. user state is a hard split** (`app/models.py`). Content tables
  (`courses → lessons → concepts → questions`) are a queryable **mirror of the
  markdown/JSON seed** under `content/` — markdown is the source of truth and is
  upserted into these tables at startup (seed loader is a TODO in `main.py`
  lifespan). User-state tables (`users`, `attempts`, `concept_mastery`,
  `lesson_progress`) hold per-user data and are never seeded.

- **`questions.reference_answer` is what makes grading "by the knowledge base"
  work.** Evaluation prompts will receive the lesson text + the question's
  reference answer + the user's answer; the model is told to grade only against
  those. Authoring questions (text + reference answer) is content work done
  alongside the theory, not generated at runtime.

- **LLM is runtime-only and narrow.** Serving a question is a pure DB read (no
  LLM). One Gemini call grades an answer; one more produces a hint (a leading
  nudge that must not reveal the reference answer). `config.Settings.model_chain`
  is the primary model + fallbacks, in order — the Gemini client walks this chain
  on per-day quota errors (pattern mirrors the author's telegram-bot `gemini.py`).

- **Spaced repetition lives in `concept_mastery`** (SM-2 fields: `ease`,
  `interval_days`, `reps`, `due_at`). Each scored attempt updates the mastery of
  the question's concept; the "review queue" surfaces concepts whose `due_at`
  has passed. Quiz question selection prefers due/weak concepts.

- **"Back to theory" deep-links** use `concepts.anchor` (a markdown heading
  anchor), so a quiz can jump the reader to the exact section a concept came from.

## Conventions & gotchas

- **SQLite pragmas per connection** (`app/database.py`): a `connect` event sets
  `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout`.
  `foreign_keys` is OFF by default in SQLite and must be set per connection or
  cascades/FK constraints silently don't apply.
- **`init_db()` imports `app.models` inside the function** so all tables register
  on `Base.metadata` before `create_all`. Don't move that import to module top
  (circular import with `database.Base`).
- **Settings are cached**: `get_settings()` is `@lru_cache`. In tests, after
  mutating env vars call `get_settings.cache_clear()`.
- **Sessions**: `async_sessionmaker(expire_on_commit=False)`; use
  `async with SessionLocal() as session`. FastAPI deps use `get_session()`.
- **`content_dir` is resolved relative to the backend CWD** (default `../content`).
- **Moving the project breaks `backend/.venv`** (absolute paths) — recreate it.
- **No Alembic**: schema is created via `create_all`. There are no migrations
  yet; changing models means recreating `data/app.db` during early development.

## Layout

```
backend/app/
  config.py    Settings (pydantic-settings), cached get_settings(), Gemini model_chain
  database.py  async engine (SQLite WAL), SessionLocal, get_session(), init_db()
  models.py    all ORM tables (content mirror + user state)
  main.py      create_app(), lifespan (init_db; content-seed TODO), /health, CORS
  auth/ content/ llm/ services/ api/endpoints/   — empty packages, filled per phase
content/       markdown lessons + seed JSON (source of truth; dir currently empty)
```

## Roadmap (phases)

0. One reference lesson end-to-end (Python Core → GIL): theory + 4–6 questions
   with reference answers — validates the whole loop before scaling content.
1. Content loader/seed + courses/lessons endpoints.
2. Auth (email/password + bcrypt + JWT; `get_current_user`).
3. Gemini client (fallback chain) + quiz service (serve / evaluate / hint).
4. Progress + SM-2 + review queue.
5. Frontend (React + TS + Vite + React Router + TanStack Query + Tailwind;
   markdown render with code syntax highlighting).
6. Author remaining topics. 7. Polish + deploy.

Topic backlog: Python Core, OOP, Async/Asyncio, FastAPI, SQLAlchemy, PostgreSQL,
Redis, Celery, Docker, System Design.
