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

См. план реализации (фазы 0–7) и бэклог тем — в задачах проекта.
