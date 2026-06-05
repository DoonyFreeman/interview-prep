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
evaluation and hints — everything else is plain DB/memory reads. It's meant to be
**self-hosted on one small server, deployed via Docker** (see Roadmap 7–8), so
keep new code container-friendly: config from env, state on a volume.

Status: Phases 0–4 done; **Phase 5 (frontend) in progress** — a React/TS/Vite SPA
(`frontend/`) covers the MVP loop (auth, course/lesson reading with Shiki code
highlighting, quiz serve/evaluate/hint, basic progress) plus question
re-practice and account settings; RU/EN i18n. Backend has 71 passing tests.
Phase 5b done (dashboard, review-queue page, dark theme). Phase 5c done (glossary:
138 P0 terms in `content/glossary.json`, public `GET /api/glossary`, a `/glossary`
page with search + category filter). Phase 5d done (configurable glossary term
quizzes: client-side generation with smart progress-weighted selection, a
`glossary_term_stats` user-state table + auth-gated progress/result endpoints, a
`/glossary/quiz` page). Phase 5e done (plain-language slang dictionary: 83 RU
terms in `content/slang.json`, served via a `kind` discriminator on the glossary
table, a `/slang` page). Frontend now has vitest. Not built yet: Docker/deploy.

## Commands

All backend commands run from `backend/`.

```bash
# Environment (recreate .venv if the project was moved — venvs hardcode paths)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # runtime
pip install -r requirements-dev.txt       # + pytest

cp .env.example .env                       # fill GEMINI_API_KEY, JWT_SECRET

# Run (creates backend/data/app.db, all tables, and seeds content on startup)
uvicorn app.main:app --reload              # http://127.0.0.1:8000  — /health, /docs

# Tests (run from backend/ — pytest.ini sets asyncio_mode=auto)
pytest                                     # whole suite (tests/)
pytest tests/test_auth.py::test_login_and_me   # a single test
```

`content_dir` defaults to `../content`, so always run the server and pytest with
`backend/` as the working directory or the content seed/loader finds nothing.

## Architecture

Layered, dependency-light. The layering is strict: **endpoint → service →
repository → model**, with Pydantic schemas at the API boundary. Big picture you
can't get from one file:

- **Repositories are the only place that talks SQLAlchemy** (`app/repositories/`).
  Each wraps an `AsyncSession` (`BaseRepository`) and exposes intent-revealing
  methods (`CourseRepository.get_by_slug`, `QuestionRepository.get_with_context`,
  `ConceptMasteryRepository.due_for_user`, …) — no endpoint or service builds a
  `select(...)` by hand. **Repositories never commit**: they `add`/`flush` and the
  calling service owns the transaction, so one service method can persist across
  several repositories atomically (e.g. `evaluate_answer` writes the `Attempt` +
  the SM-2 mastery step together). The grep invariant: `session.execute(` /
  `select(` appear only under `app/repositories/` (and `content/seed.py`, which is
  startup infra, not request-path access).

- **Services hold business logic + transaction boundaries** (`app/services/`):
  `content.py` (course/lesson reads), `auth.py` (register/login/current-user),
  `quiz.py` (serve/evaluate/hint), `progress.py` (mastery/review/overview),
  `sm2.py` (pure algorithm). Endpoints are thin: parse input, call a service,
  return a schema. ORM→schema mapping lives in the service.

- **Content vs. user state is a hard split** (`app/models.py`). Content tables
  (`courses → lessons → concepts → questions`) are a queryable **mirror of the
  markdown/JSON seed** under `content/` — markdown is the source of truth,
  upserted into these tables at startup by `content/seed.py` (called from the
  `main.py` lifespan). User-state tables (`users`, `attempts`, `concept_mastery`,
  `lesson_progress`) hold per-user data and are never seeded.

- **Content pipeline** (`app/content/`): `loader.py` parses each
  `content/courses/<slug>/` (a `metadata.json` with course+lessons+concepts, a
  `questions.json` keyed `lesson_slug → concept_slug → [questions]`, and one
  markdown file per lesson) into dataclasses; `seed.py` upserts them idempotently
  (match by slug; a concept's questions are replaced wholesale); `registry.py` is
  an in-memory cache of lesson markdown (keyed `(course_slug, lesson_slug)`) used
  to serve lesson bodies and, later, to ground the LLM. The lessons endpoint reads
  metadata from the DB and the markdown body from the registry.

- **Auth is Bearer-JWT, no refresh** (`app/auth/`). `tokens.py` issues a
  long-lived access token (jose); `security.py` hashes with **bcrypt used
  directly**; `dependencies.get_current_user` (HTTPBearer) is the gate for
  per-user routes. Endpoints: `POST /api/auth/{register,login}`, `GET /api/auth/me`.

- **`questions.reference_answer` is what makes grading "by the knowledge base"
  work.** The evaluation prompt (`llm/prompts.py:build_eval_prompt`) feeds the
  lesson text + the question's reference answer + the user's answer; the model is
  told to grade only against those. Authoring questions (text + reference answer)
  is content work done alongside the theory, not generated at runtime.

- **LLM is runtime-only and narrow** (`app/llm/`, `app/services/quiz.py`).
  Serving a question is a pure DB read (`serve_question`, no LLM). One Gemini call
  grades an answer (`evaluate_answer` → persists an `Attempt`); one more produces
  a hint (`generate_hint` — a leading nudge whose prompt deliberately omits the
  reference answer). `config.Settings.model_chain` is the primary model +
  fallbacks, in order. `GeminiClient` is resilient (pattern mirrors the author's
  telegram-bot `gemini.py`): **per-model retries with backoff**, then **fallback**
  down the chain. Daily-quota 429 (`quotaId` has `PerDay`) → switch model now;
  minute-rate 429 → retry the same model after the server's `RetryInfo` delay, but
  a long cooldown switches instead of stalling an interactive request; 5xx/network
  → retry then switch. The client forces compact
  JSON and disables 2.5-family "thinking" (`thinkingBudget: 0`) with a real
  `maxOutputTokens` so graded JSON isn't truncated. The `LLMClient` protocol is
  the seam tests override (`get_llm` dependency) to run without network/key.

- **Spaced repetition lives in `concept_mastery`** (SM-2 fields: `ease`,
  `interval_days`, `reps`, `due_at`). The algorithm is pure in `services/sm2.py`
  (`score_to_quality` maps the 0..100 grade onto SM-2's 0..5 quality;
  `sm2_update` returns the next state); the DB-facing side is in
  `services/progress.py`. `quiz.evaluate_answer` calls `progress.update_mastery`
  in the **same transaction** as the `Attempt`, so a graded answer and the SM-2
  step commit together, and the evaluation response carries the new mastery
  (reps / interval / due_at). The review queue (`get_review_queue`) surfaces
  concepts whose `due_at` has passed; `serve_question` prefers a never-attempted
  concept, then the most-overdue due one, then a random concept (review ahead).
  A concept is "mastered" at `reps >= 2 && last_score >= 80`.

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
- **Datetimes are naive UTC** (`models._utcnow` = `datetime.now(utc)` with
  `tzinfo` stripped). The `DateTime` columns are timezone-naive and SQLite returns
  naive values, so everything stays naive-UTC: mixing aware/naive raises, and an
  offset suffix would break the lexical ordering SQLite uses for `due_at` filters.
  Use `_utcnow()` for any new timestamp/`now` rather than `datetime.now(...)`.
- **`reference_answer` must never reach the client.** It grounds server-side
  grading only; the read schemas in `app/schemas.py` deliberately omit it, and a
  test (`test_reference_answers_never_leak`) guards this. Keep it server-side when
  adding quiz endpoints.
- **bcrypt is used directly, not via passlib** (`app/auth/security.py`): passlib
  1.7.4 breaks against bcrypt ≥ 4/5. Passwords are truncated to 72 bytes (bcrypt's
  limit) before hashing/verifying.
- **Test fixtures** (`tests/conftest.py`): in-memory SQLite with a `StaticPool`
  (so the DB persists across connections in a test). The app **lifespan does not
  run** under `ASGITransport`, so content is seeded into the test engine via the
  `client` fixture and `get_session` is dependency-overridden — don't rely on the
  real `data/app.db` in tests.
- **Moving the project breaks `backend/.venv`** (absolute paths) — recreate it.
- **No Alembic**: schema is created via `create_all`. There are no migrations
  yet; changing models means recreating `data/app.db` during early development.

## Layout

```
backend/app/
  config.py    Settings (pydantic-settings), cached get_settings(), Gemini model_chain
  database.py  async engine (SQLite WAL), SessionLocal, get_session(), init_db()
  models.py    all ORM tables (content mirror + user state)
  schemas.py   Pydantic read responses + quiz I/O (no reference_answer)
  main.py      create_app(), lifespan (init_db + seed_from_dir), /health, CORS, routers
  content/     loader.py, seed.py, registry.py            — DONE
  auth/        security.py, tokens.py, dependencies.py, schemas.py  — DONE
  llm/         client.py (GeminiClient + LLMClient protocol), prompts.py  — DONE
  repositories/  base.py + content/users/attempts/mastery/lesson_progress.py  — DONE
  services/    content.py, auth.py, quiz.py, progress.py, sm2.py  — DONE
  api/endpoints/  courses.py, lessons.py, auth.py, quizzes.py, progress.py  — DONE
backend/tests/  conftest.py + test_content/auth/quiz/llm/progress/repositories.py
content/courses/python-core/  metadata.json, 01-gil.md, questions.json
```

Implemented API: `GET /health`; `GET /api/courses`, `/api/courses/{slug}`,
`/api/courses/{course}/lessons/{lesson}`; `POST /api/auth/{register,login}`,
`GET/PATCH /api/auth/me`, `POST /api/auth/password`;
`GET /api/quiz/courses/{course}/lessons/{lesson}/{next,questions}`,
`GET /api/quiz/questions/{id}`, `POST /api/quiz/questions/{id}/{evaluate,hint}`;
`GET /api/progress`, `GET /api/progress/review`,
`POST /api/progress/courses/{course}/lessons/{lesson}` (all quiz + progress +
profile-mutation routes require auth). `…/questions` lists a lesson's questions
with the user's attempt history; `GET /quiz/questions/{id}` serves one for
re-practice.

Frontend (`frontend/`, Phase 5): React 18 + TS + Vite + Tailwind v4 + React
Router + TanStack Query + i18next (RU/EN) + Shiki (VS Code-grammar code
highlighting). Layered: `lib/` (axios `api` with Bearer + 401 bounce, token
store, slugify matching content anchors, Shiki singleton), `api/` (typed
hooks + types), `auth/` (token context + `RequireAuth`), `components/`,
`pages/`. `VITE_API_BASE` points at the backend (default `:8000`). Run with
`npm install && npm run dev` (port 5173, matches backend CORS default).

## Roadmap (phases)

0. ✅ Reference lesson end-to-end (Python Core → GIL): theory + 5 questions with
   reference answers — validates the loop before scaling content.
1. ✅ Content loader/seed + courses/lessons endpoints.
2. ✅ Auth (email/password + bcrypt + JWT; `get_current_user`).
3. ✅ Gemini client (fallback chain) + quiz service (serve / evaluate / hint).
   Live evaluation needs `GEMINI_API_KEY` in `backend/.env`; logic is testable
   with a mocked LLM (`test_quiz.py`, `test_llm.py`).
4. ✅ Progress + SM-2 + review queue (mastery updated per scored attempt;
   due-aware question selection; `/api/progress` + `/api/progress/review`).
5. **← IN PROGRESS.** Frontend (React + TS + Vite + React Router + TanStack Query
   + Tailwind; markdown render with code syntax highlighting). MVP loop + question
   re-practice + account settings + RU/EN i18n done; **5b done**: dashboard stats
   hero, review-queue page, dark theme.
5c. ✅ **Glossary** (see `content/GLOSSARY_PLAN.md`). A public reference section
   of terms a Python backend middle must know, grouped in 12 categories. New
   content type alongside courses/lessons: `glossary_terms` table mirroring
   `content/glossary.json` (wholesale re-seed, no user state), public
   `GET /api/glossary`(+`?category=&q=`) and `/api/glossary/{slug}`, a `/glossary`
   page with client-side search + category filter, deep-links back to theory via
   the existing `anchor`/`slugify`. Shipped feature slice + 138 P0 terms (RU);
   P1/P2 fill in during Phase 6.
5d. ✅ **Glossary quizzes** (see `content/GLOSSARY_QUIZ_PLAN.md`). Configurable
   multiple-choice term quizzes by knowledge area, with progress + smart
   selection. Quiz **generation is client-side** (`frontend/src/lib/glossaryQuiz.ts`,
   pure + vitest-tested): from the loaded glossary it builds questions
   (definition→term & term→def), weighted by the user's per-term stats (buckets
   new/weak/learning/mastered + recency penalty); modes smart/weak/mistakes/random;
   distractors prefer the same category. **Backend** is user-state only:
   `glossary_term_stats` table, auth-gated `GET /api/glossary/progress` +
   `POST /api/glossary/quiz/result` (one upsert per answered term). A `/glossary/quiz`
   setup→run→result page; entry points + per-category mastery on `/glossary`.
5e. ✅ **Slang dictionary** (see `content/SLANG_PLAN.md`). A separate plain-language
   dev-jargon dictionary (`content/slang.json`, 83 terms RU). Reuses the
   `glossary_terms` table via a `kind` discriminator (`reference` | `slang`); the
   public `GET /api/glossary?kind=slang` serves it (default `kind=reference`, so the
   glossary page and quizzes stay reference-only). A `/slang` page groups terms
   alphabetically with client-side search; nav item "Сленг".
6. Author remaining topics (deep lessons + reference answers; glossary P1/P2 fill
   in here too).
7. **Dockerize.** Multi-stage `Dockerfile` for the backend (and the frontend, or
   a single image serving the built SPA via FastAPI static files), a
   `docker-compose.yml` wiring backend + frontend + a reverse proxy, the SQLite
   file on a **named volume** so WAL data survives container rebuilds, and config
   (`GEMINI_API_KEY`, `JWT_SECRET`, `CORS_ORIGINS`, `CONTENT_DIR`) injected via
   env / a mounted `.env`. Content markdown is baked into the image (source of
   truth) and re-seeded on startup. Keep it as light as the stack: one small host,
   no Redis/Postgres.
8. **Deploy to a server.** Single-host deploy of the compose stack behind a
   reverse proxy with TLS (Caddy or nginx + certbot); persistent volume for
   `data/app.db`; a simple backup of that volume; restart policy + healthcheck on
   `/health`.

Deployment intent: the app is meant to run on a small self-hosted server, so
**containerization is a first-class goal** — do Docker as soon as there's a
frontend to serve (Phase 7), not as an afterthought.

Topic backlog: Python Core, OOP, Async/Asyncio, FastAPI, SQLAlchemy, PostgreSQL,
Redis, Celery, Docker, System Design.
