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
table, a `/slang` page). Frontend now has vitest. **Phase 6 (content authoring)
in progress** — the curriculum is now authored across **20 courses / 97 lessons /
346 concepts / 346 questions** (`content/courses/`), each lesson with full theory,
analogies, simple explanations and an authored reference answer per concept. Tests
updated for the multi-course content (6 stale single-course assertions rewritten to
derive from the loader) plus a new `tests/test_content_integrity.py` (all courses
load, anchors match H2s, no orphan questions, reference_answer never leaks) — **94
passing**. **Phase 7 (Dockerize) done**: a multi-stage `Dockerfile` builds the SPA
and serves it + `/api` from one `python:3.13-slim` image (FastAPI mounts the built
`dist/` at `app/static` with an SPA fallback — guarded, so dev/tests are
unaffected), `docker-compose.yml` runs the single `app` service with SQLite on a
named volume + a `/health` healthcheck. Not built yet: reverse-proxy + TLS deploy
(Phase 8).

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
  The layer is a thin **Data Mapper**: SQLAlchemy's ORM already maps the plain
  `app/models.py` classes to rows, and `base.py` adds a generic, typed
  `BaseRepository[ModelT]` over it (`model` class attr + reusable primitives `get`
  (PK via identity map), `find_one_by`, `list_by`, `add`, and `_one`/`_all`
  execute helpers). Each concrete repo binds its model (`UserRepository(
  BaseRepository[User])`, `model = User`) and exposes intent-revealing methods
  (`CourseRepository.get_by_slug`, `QuestionRepository.get_with_context`,
  `ConceptMasteryRepository.due_for_user`, …): trivial lookups delegate to the
  base primitives, only genuinely bespoke queries (joins, eager loads, search,
  aggregates) hand-write a `select(...)`. No endpoint or service builds a
  `select(...)` by hand. **Repositories never commit**: they `add`/`flush` and the
  calling service owns the transaction, so one service method can persist across
  several repositories atomically (e.g. `evaluate_answer` writes the `Attempt` +
  the SM-2 mastery step together). The grep invariant: `session.execute(` /
  `select(` appear only under `app/repositories/` (and `content/seed.py`, which is
  startup infra, not request-path access). (`*MasteryRepository.get` /
  `LessonProgressRepository.get` deliberately override the base PK `get` to look up
  by their composite `(user_id, …)` key — that's their public contract.)

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
- **`reference_answer` must never reach the client pre-answer.** It grounds
  server-side grading; the read schemas in `app/schemas.py` deliberately omit it
  (serve / lesson list / attempts history), and tests
  (`test_reference_answers_never_leak*`) guard this. The **one deliberate
  exception** is `EvaluationOut`: after the user submits an answer and it is
  graded, the response reveals the authored reference answer for
  self-comparison. Keep every new pre-answer endpoint reference-free.
- **bcrypt is used directly, not via passlib** (`app/auth/security.py`): passlib
  1.7.4 breaks against bcrypt ≥ 4/5. Passwords are truncated to 72 bytes (bcrypt's
  limit) before hashing/verifying.
- **Test fixtures** (`tests/conftest.py`): in-memory SQLite with a `StaticPool`
  (so the DB persists across connections in a test). The app **lifespan does not
  run** under `ASGITransport`, so content is seeded into the test engine via the
  `client` fixture and `get_session` is dependency-overridden — don't rely on the
  real `data/app.db` in tests.
- **Moving the project breaks `backend/.venv`** (absolute paths) — recreate it.
- **No Alembic**: schema is created via `create_all`. For a *new table* that's
  enough. For a *new column on an existing table* (which `create_all` won't add),
  append an idempotent, additive step to `database.ensure_schema_upgrades()` — it
  runs after `create_all` on startup and `ALTER TABLE … ADD COLUMN`s a nullable
  column only if `PRAGMA table_info` shows it missing (e.g. `pet_state.hat`). This
  lets the live `data/app.db` / docker volume gain columns without recreation or
  data loss. Only ever ADD nullable columns there (never drop/alter), so re-runs
  are safe. Anything more complex than an additive column still means Alembic or a
  manual migration.

## Layout

```
backend/app/
  config.py    Settings (pydantic-settings), cached get_settings(), Gemini model_chain
  database.py  async engine (SQLite WAL), SessionLocal, get_session(), init_db()
  models.py    all ORM tables (content mirror + user state)
  schemas.py   Pydantic read responses + quiz I/O (reference_answer only post-grade)
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
`GET /api/quiz/questions/{id}`, `GET /api/quiz/questions/{id}/attempts`,
`POST /api/quiz/questions/{id}/{evaluate,hint}`;
`GET /api/progress`, `GET /api/progress/questions`, `GET /api/progress/review`,
`POST /api/progress/courses/{course}/lessons/{lesson}`;
`GET/PATCH /api/pet`; `GET /api/cat/thoughts` (all quiz + progress + pet/cat +
profile-mutation routes require auth); **admin** (403 unless the JWT user's
email is in the `ADMIN_EMAILS` env list, comma-separated; `/api/auth/me`
carries `is_admin`): `GET /api/admin/users` (per-user rollup: pet + concepts/
lessons/tests/attempts via the existing per-user services in a loop),
`GET /api/admin/users/{id}` (adds the full progress + tests overviews),
`PATCH /api/admin/users/{id}/pet` (manual override — skips the unlock clamps,
keeps `best_streak >= streak` and non-negative counters; used e.g. to restore a
lost streak). Client: `/admin` page (users list → expandable per-course lesson
breakdown + pet editor), linked from `/settings` only when `is_admin`;
`GET /api/search?q=` (public) — global
lesson search over course/lesson/concept titles + full lesson markdown.
Python-side whole-phrase `casefold()` scan of the in-memory registry (SQLite
LIKE is Cyrillic-case-sensitive) in `services/search.py` via
`excerpt.extract_h2_sections`; ranked lesson_title > section_title > body >
course_title, deduped per (lesson, anchor), capped at 20, word-boundary
snippets. The client is a Cmd/Ctrl+K command-palette modal
(`frontend/src/components/SearchModal.tsx` in the header) that deep-links to
`/courses/{c}/lessons/{l}#{anchor}`. `…/questions` lists a lesson's questions
with the user's attempt history; `GET /quiz/questions/{id}` serves one for
re-practice; `…/{id}/attempts` returns the user's past answers + stored reviews
for that question (newest first). `GET /api/progress/questions` rolls up
questions-answered-vs-total per course/lesson (the "what's left" view).
`GET /api/cat/thoughts` powers the corner cat: one entry per concept of every
**completed** lesson, each carrying the first prose paragraph of its H2 section
(parsed from the lesson markdown by `app/content/excerpt.py`, truncated on a
sentence boundary). The client (`lib/cat.ts:pickThought`) picks **two-stage** —
a random lesson, then a random concept within it — so big lessons don't dominate
and topics jump around; it avoids the lesson shown last and a 30-key
localStorage anti-repeat window. `useMarkLesson` invalidates `["cat-thoughts"]`
so newly completed lessons appear without a reload.

The corner cat's **skin** (10) and **hat** (7) are streak-gated cosmetics,
unlocked by `pet_state.best_streak` and clamped server-side (`services/pet.py:
SKIN_MILESTONES`/`HAT_MILESTONES`, mirrored client-side in `lib/cat.ts`) so a
stale/locked choice silently falls back (`classic` skin; `null` hat — which
still shows the wizard hat by default on the wizard stage, `"none"` opts out
explicitly). Skins are palette-only entries in `cat/CatSprite.tsx:PALETTES`
(same 12×12 pixel grid); hats are a small pixel-rect registry (`HATS`) drawn
above the head, extending the SVG viewBox upward. **Achievements** (11
streak thresholds, 1–100 days) are purely derived from `best_streak` — no
storage — via `lib/cat.ts:ACHIEVEMENTS`/`achievementsUnlocked`; a panel in
`PetSettings` shows locked/unlocked, and `useCat.syncDailyStreak` toasts any
newly crossed threshold after a visit.

Frontend (`frontend/`, Phase 5): React 18 + TS + Vite + Tailwind v4 + React
Router + TanStack Query + i18next (RU/EN) + Shiki (VS Code-grammar code
highlighting) + Motion (Framer Motion). Layered: `lib/` (axios `api` with
Bearer + 401 bounce, token store, slugify matching content anchors, Shiki
singleton, `motion.ts` shared animation presets, `accent.ts` per-course colour,
`useActiveAnchor` TOC observer), `api/` (typed hooks + types), `auth/` (token
context + `RequireAuth`), `components/`, `pages/`. `VITE_API_BASE` points at the
backend (default `:8000`). Run with `npm install && npm run dev` (port 5173,
matches backend CORS default).

**Design system** (Phase 5f, "own identity" redesign): one warm-stone palette
driven entirely by CSS custom properties in `index.css` (`@theme` for light, a
`.dark` override). Tokens map to Tailwind v4 utilities: colours (`bg-surface`,
`text-ink`, `bg-primary-soft`, `text-accent`, plus a teal `celebrate` reward
accent), a 3-step elevation scale (`shadow-card`/`shadow-raised`/`shadow-pop`),
and fonts — **self-hosted via `@fontsource`** (Docker-friendly, no external
requests): **Bricolage Grotesque** display (`font-display`, used on every page
title/brand/heading), **Geist** body (`--font-sans`), JetBrains Mono code. Body
has a faint two-wash radial gradient mesh for depth. Motion is deliberately
**subtle** (6–10px offsets, 0.12–0.28s) and everything honours
`prefers-reduced-motion` (global CSS reset + Motion's `useReducedMotion`):
route crossfades (`Layout` wraps `useOutlet()` in `AnimatePresence` keyed by
pathname so the header/nav stay put), staggered list/card reveals, an animated
nav "pill" (`layoutId`), count-up + ring sweep in `ScoreGauge`, quiz phase
crossfade. Shared primitives: `Button` (variants + `loading` + `active:scale`),
`Skeleton`/`SkeletonCard`/`SkeletonGrid` (replace the dashboard spinner to cut
layout shift), `EmptyState`, a lightweight `Toast` context (`ToastProvider` in
`main.tsx`, `useToast()` — used for settings save/error), `DictTabs` (segmented
Glossary↔Slang switch; slang is no longer a top-nav item). Primary nav is 3
items (Courses / Glossary / Progress) + a single "to review" badge; the mobile
`BottomNavBar` mirrors them + Profile. **iOS**: `viewport-fit=cover` +
`env(safe-area-inset-*)` padding on the bottom bar/main/toasts, 16px form-control
font on phones to stop focus-zoom, `theme-color` per scheme.

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
   alphabetically with client-side search; nav item "Сленг". **Slang quiz**: the
   `/slang/quiz` route reuses `GlossaryQuizPage` with `kind="slang"` (category
   picker hidden — slang is one flat category); stats flow through the same
   `glossary_term_stats` endpoints (`all_slugs` is kind-agnostic by design, and
   the reference category rollup ignores slang slugs).
6. **← IN PROGRESS.** Author remaining topics (deep lessons + reference answers;
   glossary P1/P2 fill in here too). Done so far: full curriculum across **20
   courses / 97 lessons / 346 concepts / 346 questions** under `content/courses/`
   (python-core, python-data-types, python-oop, python-idioms, python-concurrency,
   python-asyncio, databases-sql, sqlalchemy, fastapi, web-http, testing,
   algorithms, python-typing, postgresql, redis, celery, docker, devops,
   system-design, security). Each lesson = full theory + analogies + simple
   explanations; each concept has an `anchor` (slugified H2) and an authored
   `reference_answer`. **Tests updated**: the 6 stale single-course assertions in
   `test_content`/`test_progress`/`test_repositories` were rewritten to derive
   expectations from the loader / look up `python-core` by slug, and a new
   `tests/test_content_integrity.py` guards the whole curriculum (all courses load,
   every concept anchor == `slugify(H2)`, no orphan `questions.json` keys,
   reference answers present server-side + never leak via the lesson API). Suite is
   **94 passing**.
7. ✅ **Dockerize** (single-image topology). Multi-stage `Dockerfile`: a
   `node:20-alpine` stage builds the SPA with `VITE_API_BASE=""` (same-origin), a
   `python:3.13-slim` runtime installs `requirements.txt`, copies `backend/app`,
   `content/`, and the built `dist/` into `app/static`, runs as non-root, and
   serves everything via uvicorn. `app/main.py:_mount_spa` mounts `/assets` and
   adds an SPA `index.html` fallback for client-side routes — **guarded by
   `STATIC_DIR.is_dir()`** so local dev and the test suite (no `static/`) are a
   no-op. `docker-compose.yml` runs one `app` service with the SQLite file on the
   `app-data` **named volume** (`/app/backend/data`, survives rebuilds), config
   from `.env` (`JWT_SECRET`, `GEMINI_API_KEY`, …; see `.env.docker.example`),
   port 8000, and a stdlib `/health` healthcheck. Content is baked into the image
   and re-seeded on startup. Smoke-tested: image builds (~347 MB), container goes
   healthy, `/api/courses` returns 20 courses, SPA + deep links + assets serve,
   no `reference_answer` leak, DB persists across restart.
8. ✅ **Deploy to a server** — **live** at `https://176.123.168.87.sslip.io`.
   Artifacts ready: `Caddyfile` (reverse_proxy `app:8000`, automatic Let's Encrypt
   TLS, HSTS/security headers), `docker-compose.prod.yml` overlay (adds a `caddy`
   service on 80/443 with persistent `caddy_data`/`caddy_config` volumes,
   `depends_on app: service_healthy`), the base compose now binds the app to
   `127.0.0.1:8000` so only Caddy is public, `scripts/backup.sh` (consistent online
   SQLite snapshot from the running container → `./backups/`, pruned) +
   `scripts/restore.sh`, and `DEPLOY.md` (full single-host runbook: DNS, launch,
   updates, backup cron, restore, local `tls internal` test). Run with
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
   **Updates are CI/CD**: a push to `master` builds the `linux/amd64` image in
   GitHub Actions, pushes it to GHCR, then SSHes the host and runs
   `scripts/deploy.sh` (backup → `git pull` → `compose pull` → `up -d --no-build`
   → health check). The host **never builds** — a Vite build OOMs the VPS — and
   `deploy.sh` never touches the `app-data` volume, so user progress survives
   every deploy. Rollback: `docker compose ... pull` an older `:<sha>` tag, or
   `scripts/restore.sh ./backups/<snapshot>.db`.
   **Schema changes must stay additive** (`ensure_schema_upgrades`): the live DB
   is upgraded in place on startup, never recreated. The `bank` column was
   validated this way against a real pre-change database — column added with
   `DEFAULT 'lesson'` (no NULLs), every user table byte-identical, login and
   scores intact, and idempotent across restarts. A rollback to the previous
   image is also clean: the old seed re-writes the MCQ set per concept, so exam
   rows simply disappear and orphaned `mcq_stats` are ignored.
9. **Lesson MCQ self-test** (see `content/LESSON_QUIZ_PLAN.md`). A second, no-LLM
   way to check yourself in a lesson, alongside the AI interview: closed
   multiple-choice questions graded **client-side** for instant feedback.
   **9.1 done (pilot)**: `mcq_questions` + `mcq_stats` tables mirroring a new
   `content/courses/<slug>/tests.json` (loader auto-derives a stable
   `course:lesson:concept:i` slug; `_seed_mcq` re-seeds per concept wholesale),
   auth-gated `GET /api/quiz/courses/{c}/lessons/{l}/test`, `…/test/progress`,
   `…/test/result`; a `/courses/:c/lessons/:l/test` page (run→result, "review
   mistakes" mode) with a "📝 Пройти тест" entry point + score badge on the lesson
   page; pure runner helpers in `frontend/src/lib/lessonTest.ts` (vitest).
   Stats are kept **separate from SM-2** (an MCQ guess shouldn't move
   spaced-repetition mastery).
   **Deliberate exception to the answer-hiding rule**: unlike `reference_answer`
   (hidden to protect LLM grading), the MCQ `correct_index` + `explanation_md` are
   sent to the client — the options are visible anyway and grading is a plain index
   compare, exactly like the glossary quiz. The `reference_answer` rule is
   unchanged (the lesson endpoint leaks neither).
   **9.1b done**: lesson-test progress is surfaced on the dashboard as a separate
   indicator — `lesson_test_results` (best/last/attempts per lesson; the score is
   the **standing** score over the latest answer to each MCQ — the `mcq_stats`
   union — recorded once every MCQ of the lesson has been answered, so fixing a
   failed question in "review mistakes" mode lifts the lesson to passed; `best_score`
   is `max` and never drops, and a lone subset can't inflate it since the score is
   always over the full MCQ set), `GET /api/quiz/tests/
   overview`, a "Тесты X/Y" stat + per-course indicator on the catalog, lesson
   badge shows best-score % (passed at ≥80%); the mastery ring is untouched. UI
   emoji on buttons replaced with SVG icons (`icons.tsx`).
   **9.2 done**: MCQ authored for **all 20 courses — 692 MCQ (2 per concept ×
   346)** via the `content/MCQ_AUTHORING_GUIDE.md` runbook (Sonnet agents,
   batched by course, each validated). `test_content_integrity` now asserts every
   concept of every course has ≥2 MCQ (≥692 total). Backend 112 passing.
   **9.3 done — mixed tests (the `/tests` section)**: one place to drill MCQ
   across *all* courses. `mcq_questions` gained a **`bank` discriminator**
   (mirroring the glossary's `kind`): `lesson` mirrors `tests.json` (unchanged —
   still the only bank a lesson badge or the tests overview scores against), and
   `exam` mirrors a new optional `content/courses/<slug>/exam.json` of applied /
   scenario questions authored **only** for `/tests`, with `exam:`-prefixed slugs
   so the two can never collide. `database.ensure_schema_upgrades` adds the column
   additively (`DEFAULT 'lesson'` backfills live rows). Auth-gated
   `GET /api/quiz/tests/topics` (per-course counts + this user's answered/weak
   tallies), `GET …/tests/mix` (`courses=&banks=&mode=&count=`),
   `POST …/tests/mix/result`.
   **Selection is server-side here** — a deliberate departure from the
   client-generated glossary quiz, because the full bank is ~836 KB of JSON
   (148 KB gzipped): far too much to ship in order to keep 20 questions.
   `services/lesson_test.py:pick_mix` is pure apart from an injected `Random`
   (unit-tested): modes `random` (uniform — "random" has to mean random),
   `smart` (weighted: unseen > wrong > shaky > mastered, recently-seen demoted,
   via Efraimidis–Spirakis weighted sampling without replacement), `weak`,
   `mistakes`; the chosen questions are then round-robined across courses so a
   mixed test actually feels mixed. Answers flow into the **same** `mcq_stats`,
   and every lesson a run touched has its standing score recomputed
   (`_record_standing_score`, shared with the per-lesson path) — so answering a
   lesson's last unseen question inside a mixed run completes that lesson's test.
   Exam-bank answers cannot reach a lesson score by construction
   (`list_for_lesson` and `lessons_for_slugs` filter `bank == "lesson"`; guarded
   by `test_exam_bank_never_touches_a_lesson_score`). Client: a `/tests` page
   (three one-tap presets → a setup panel for count / mode / source / topics), and
   the run+result UI was extracted out of `LessonTestPage` into a shared
   `components/TestRunner.tsx` used by both (a mixed run passes `showOrigin`, and
   each question carries its own course/lesson deep link — `prepareTest` fills the
   origin in from the URL for the per-lesson case). The mobile bottom nav is now
   **user-configurable**: `lib/navTabs.ts` (localStorage + `useSyncExternalStore`,
   3–6 tabs, canonical order enforced) with a picker in Settings.
   `scripts/check_mcq_quality.py` gates the "pick the longest option" tell
   (`--report` surveys an existing bank without failing).
   **The `exam.json` bank covers all 22 courses — 206 questions**, 2 per lesson,
   every one a scenario ("given this code / this situation, what happens") rather
   than a definition, and every file passing the length gate (correct-is-longest
   0–40%, mean ratio ~1.0 vs the lesson bank's 1.5).
   Backend 184 passing, frontend 85.
   **Release note**: `lib/whatsNew.ts` + `components/WhatsNew.tsx` show a
   one-time dialog after an update (localStorage stores the release id, not a
   flag). To announce the next release: bump `CURRENT_RELEASE` and rewrite the
   `whatsNew.*` strings in both locales.
   The SPA fallback now **404s unknown `/api/*`** instead of answering
   `200 text/html` (`main.py:_mount_spa`, guarded by `test_spa_fallback.py`) —
   otherwise a route that failed to register is indistinguishable from a working
   one in a post-deploy smoke check.
   **Known content debt**: the *lesson* bank (734 MCQ, phase 9.2) has the length
   tell badly — the correct answer is the uniquely longest option in ~80% of
   questions (chance is 25%), mean 1.5× the distractor length. Deliberately left
   alone for now at the author's call; `scripts/check_mcq_quality.py --report`
   ranks the worst courses (nginx 100%, sqlalchemy 100%, postgresql 96%).

Deployment intent: the app is meant to run on a small self-hosted server, so
**containerization is a first-class goal** — do Docker as soon as there's a
frontend to serve (Phase 7), not as an afterthought.

Topic backlog: Python Core, OOP, Async/Asyncio, FastAPI, SQLAlchemy, PostgreSQL,
Redis, Celery, Docker, System Design.
