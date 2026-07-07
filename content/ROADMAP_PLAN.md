# Roadmap — план фичи (research, 2026-07-07)

Интерактивный роудмап «Python middle backend»: визуальная карта стека, клик по
узлу → что учить, ссылка на наш курс/уроки, подобранные видео (YouTube) и
статьи. Реализация — в отдельной ветке; этот файл — итог анализа.

## Ключевая идея

**Роудмап — это визуальный слой над уже готовым контентом, а не новый контент.**
У нас уже есть полный middle-стек: 20 курсов / 97 уроков в learning-порядке
(`metadata.json:order` 1–20). Узел роудмапа = наш курс; в панели узла — список
его уроков (внутренние ссылки) + 2–4 внешних ресурса (видео/статьи).

Второй бонус бесплатно: **прогресс на карте**. Узлы указывают на курсы, а
прогресс по урокам/концептам/тестам уже трекается (`/api/progress`,
`/api/quiz/tests/overview`) — роудмап может подсвечивать пройденное без единой
новой user-state таблицы.

## Референс: roadmap.sh

- UX: вертикальная «магистраль» с ответвлениями; клик по узлу → drawer с
  коротким описанием и списком ссылок, тегированных по типу
  (article / video / course / official docs); чекбокс "done" на узле.
- Данные: JSON-граф (layout) + markdown-файл контента на узел со списком
  тегированных ссылок. Рендерер свой (React/Astro).
- Вывод для нас: их формат тяжелее, чем нужно. Нам хватит одного
  `content/roadmap.json` и ручной вертикальной вёрстки (никаких graph-библиотек
  — мобильная версия roadmap.sh сама по себе просто вертикальный список).

## Структура роудмапа (7 этапов, из наших course.order)

1. **Ядро Python** — python-core, python-data-types, python-oop,
   python-idioms, python-typing
2. **Конкурентность** — python-concurrency, python-asyncio
3. **Данные** — databases-sql, sqlalchemy, postgresql, redis
4. **Web** — web-http, fastapi, celery
5. **Качество** — testing, algorithms
6. **Инфраструктура** — docker, devops
7. **Senior-track** — system-design, security

Возможные external-only узлы (тем без наших курсов почти нет — стек закрыт):
кандидаты — «процесс собеседования / мок-интервью», «Kafka/брокеры глубже»,
«nginx». Помечаются `kind: "external"` и рендерятся без прогресс-кольца.

## Формат данных — `content/roadmap.json`

```json
{
  "stages": [
    {
      "slug": "core",
      "title": "Ядро Python",
      "nodes": [
        {
          "slug": "python-core",
          "kind": "course",            // "course" | "external"
          "course_slug": "python-core", // null для external
          "summary": "GIL, память, итераторы — фундамент собеса.",
          "resources": [
            {"type": "video",   "lang": "ru", "title": "…", "url": "https://youtu.be/…", "source": "Диджитализируй"},
            {"type": "article", "lang": "ru", "title": "…", "url": "https://habr.com/…", "source": "Хабр"},
            {"type": "docs",    "lang": "en", "title": "…", "url": "https://docs.python.org/…", "source": "docs.python.org"}
          ]
        }
      ]
    }
  ]
}
```

Заголовок/описание/уроки курса в JSON не дублируем — берём из БД/registry по
`course_slug` (single source of truth). В JSON только то, чего больше нигде
нет: этапы, порядок, summary «зачем это на собесе», внешние ссылки.

## Бэкенд (минимальный)

- Никаких новых таблиц и seed: user-state нет, поиска нет.
- Загрузка `content/roadmap.json` в память на старте (по образцу registry) +
  один публичный `GET /api/roadmap`, отдающий узлы, обогащённые
  title/lessons из контентных таблиц. Прогресс клиент берёт из уже
  существующих `/api/progress` и tests overview — новых endpoint'ов не надо.
- Тест целостности: каждый `course_slug` существует, слаги уникальны, у
  каждого course-узла ≥1 видео и ≥1 статья, схема ресурсов валидна
  (добавить в `test_content_integrity.py`).

## Фронтенд

- Страница `/roadmap`: вертикальные этапы (CSS, дизайн-система, Motion-ревил
  как на каталоге), узлы с прогресс-кольцом (уроки done / total, тесты).
- Клик по узлу → drawer/модалка (паттерн `SearchModal` уже есть): summary,
  список уроков со статусом ✓/○ и ссылками на `/courses/{c}/lessons/{l}`,
  блок «Видео» и «Почитать» — внешние ссылки `target="_blank" rel="noopener"`.
- Видео — **просто ссылки наружу, без iframe-embed** (проще, без внешних
  запросов со страницы, без cookie-баннеров YouTube). Превью-картинки с
  i.ytimg.com не тянем — политика self-hosted ассетов.

## Откуда брать видео (курируем на этапе реализации, RU-first)

Проверенные каналы под наши темы:

| Темы | RU-источники | EN-fallback |
|---|---|---|
| Python core / типы / ООП / идиомы | Диджитализируй (А. Голобурдин), selfedu (С. Балакирев), лекции Школы бэкенд-разработки Яндекса | Corey Schafer, mCoding, ArjanCodes |
| Typing / Pydantic | Диджитализируй (mypy), Артём Шумейко | ArjanCodes |
| Конкурентность / asyncio | Диджитализируй, Яндекс-лекции, Шумейко | — |
| SQL / PostgreSQL | Postgres Professional (лекции Е. Рогова), Хекслет | Hussein Nasser |
| SQLAlchemy | курс Артёма Шумейко (github.com/artemonsh/sqlalchemy_course) | — |
| FastAPI | плейлист Шумейко (youtube.com/playlist?list=PLeLN0qH0-mCVQKZ8-W1LhxDcVlWtTALCS), официальные доки (есть RU) | — |
| Web / HTTP | Listen IT (короткие ролики про HTTP/REST/сети) | Hussein Nasser |
| Тестирование | Диджитализируй (pytest), Шумейко | ArjanCodes |
| Алгоритмы | «Тренировки по алгоритмам» Яндекса, selfedu | NeetCode |
| Docker / DevOps | ADV-IT | TechWorld with Nana |
| Redis / Celery | Шумейко, статьи Хабра (RU-видео мало) | Hussein Nasser |
| System Design | karpov.courses (открытые лекции), мок-собесы Хекслета | System Design Interview, ByteByteGo |
| Security | OWASP (доки), Хабр | — |

Статьи: в первую очередь **наши же уроки** (это и есть «что почитать»), затем
официальные доки, Хабр, RealPython.

Процесс курирования: на этапе реализации по каждому узлу подобрать 1–2 видео +
1–2 статьи поиском, **каждый URL проверить** (для YouTube — дёшево через
`https://www.youtube.com/oembed?url=<video_url>&format=json`: 200 = живое,
404 = удалено/приватное). Скрипт `scripts/check_roadmap_links.py` для ручного
прогона (сетевой — в pytest не включать).

## Оценка объёма

- ~20–25 узлов × ~3 внешних ссылки ≈ 60–75 курируемых URL — обозримо.
- Код: 1 JSON, ~1 маленький сервис+endpoint, 1 страница + drawer, тесты.

## Открытые вопросы (решить перед веткой)

1. Гранулярность узла: курс (рекомендую) или урок (97 узлов — шум)?
2. Нужны ли external-only узлы (Kafka, nginx, «как проходить собес») в v1?
3. Ссылки только RU или RU+EN с пометкой языка (рекомендую RU+EN с бейджем)?
4. Прогресс-подсветка в v1 или потом? (стоит почти ничего — рекомендую сразу)
