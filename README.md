# Interview Prep Platform

Веб-приложение для подготовки к техническим собеседованиям. Пользователь читает
глубокую теорию по теме, затем ИИ задаёт вопросы и **проверяет ответ по базе
знаний сайта** (а не по своим общим знаниям): выставляет балл, пишет рецензию,
по кнопке даёт подсказку или возвращает к нужному разделу теории. Прогресс
ведётся по концептам со spaced repetition (слабые темы возвращаются).

Стек подобран лёгким (для себя + друга): **FastAPI + SQLAlchemy 2.0 async +
SQLite (WAL)**, без Redis — статичный контент кешируется в памяти. Frontend —
React + TS + Vite + Tailwind (добавляется позже). LLM — Gemini, вызывается
только на оценку ответа и подсказку.

## Backend — запуск

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # заполнить GEMINI_API_KEY, JWT_SECRET
uvicorn app.main:app --reload # http://127.0.0.1:8000  (/health, /docs)
```

SQLite-файл создаётся в `backend/data/app.db`, таблицы — при старте (lifespan).

## Тесты

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Docker (единый образ)

Multi-stage сборка: Vite собирает SPA → `dist` копируется в python-образ, FastAPI
раздаёт статику и `/api` с одного origin (CORS не нужен). SQLite живёт на named
volume и переживает пересборки. Reverse proxy + TLS — Фаза 8.

```bash
cp .env.docker.example .env   # заполнить JWT_SECRET, GEMINI_API_KEY
docker compose up -d --build  # http://localhost:8000  (SPA + /api + /health)
```

Контент (`content/`) запекается в образ как источник правды и пересеивается при
старте. Данные — в томе `app-data` (`/app/backend/data`).

## Прод-деплой

Одиночный хост за Caddy (reverse proxy + авто-TLS), бэкап тома SQLite. Запуск:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Полный runbook (DNS, TLS, бэкап/restore, обновления, локальный TLS-тест) — в
[`DEPLOY.md`](DEPLOY.md).

## Структура

```
backend/app/
  config.py     — Settings (pydantic-settings), get_settings() с кешем
  database.py   — async engine (SQLite WAL), сессии, init_db()
  models.py     — ORM: courses, lessons, concepts, questions,
                  users, attempts, concept_mastery, lesson_progress
  main.py       — FastAPI app, lifespan (init_db), /health
  auth/ content/ llm/ services/ api/endpoints/  — заполняются по фазам
content/        — учебный контент (markdown + seed JSON), источник правды
```

См. план реализации (фазы 0–8) и бэклог тем — в задачах проекта.
