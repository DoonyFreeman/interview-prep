# Glossary Plan — словарь Python backend разработчика

План отдельной фичи **«Глоссарий»**: справочный раздел со всеми терминами, за
которые должен «шарить» Python backend middle (и не только). Цель — быстрый
просмотр, поиск, повторение перед собесом; каждый термин раскрыт коротко, с
аналогией и пометкой «зачем спрашивают».

Это **план**, не реализация. Здесь зафиксировано: куда фича встаёт в архитектуру и
роадмап, как устроены данные/API/страница, и сам список терминов с приоритетами.

---

## Зачем и почему именно сейчас

- **Высокая ценность / низкая трудоёмкость.** Глубокие уроки (Фаза 6) — долгая
  работа; пока есть только 1 урок (GIL). Глоссарий даёт «быструю победу»: 150–250
  терминов с короткими определениями полезны сразу, даже без полных уроков.
- **Площадка для накопления.** Авторя уроки, термины удобно сразу складывать в
  глоссарий и линковать на разделы теории (через существующий механизм
  `anchor`/`slugify`).
- **Отдельный режим собеса.** «Объясни термин» — другой формат, чем «ответь на
  вопрос по уроку»; хорошо дополняет квиз.

## Куда встаёт в роадмап (очередность)

Рекомендация — **разбить на «тонкий слайс фичи» + «наполнение»**:

1. **Фаза 5c (NEW) — механика глоссария** (маленькая инженерная задача, ~1 заход):
   модель + сид + API + страница со списком/поиском/фильтром по категориям. Едет
   **после текущей 5b, до/вместо части Фазы 6**, т.к. даёт ценность немедленно.
2. **Фаза 6 — наполнение глоссария идёт параллельно с авторингом уроков**: каждый
   новый урок добавляет 10–20 терминов; глоссарий линкуется на теорию.
3. **Фаза 7–8 (Docker/деплой)** — без изменений; глоссарий едет в том же образе
   (контент запекается, сидируется на старте — как и уроки).

Итог: вставляем **Фазу 5c** между 5b и 6; контентную часть тянем в 6.

## Куда встаёт в архитектуру

Глоссарий — **новый тип контента**, отдельный от `courses → lessons → concepts`,
потому что должен быть полным и плоским даже когда уроков ещё нет. Повторяем
существующий паттерн «markdown/JSON — источник правды, зеркало в БД, сид на старте».

- **Данные (источник правды):** `content/glossary.json` — массив терминов:
  `{ slug, term, aliases[], category, short_md, links[] }`, где
  `links[] = { course_slug, lesson_slug, anchor }` (опционально, для «к теории»).
  Альтернатива при росте — markdown-файл на термин; начать с одного JSON.
- **Модель** (`app/models.py`, рядом с контентными): новая таблица
  `glossary_terms` (`id, slug unique, term, category, short_md, aliases (Text/JSON),
  order_index`). Контентная таблица — **никакого user-state**. Линки на уроки можно
  хранить как JSON-поле или отдельной таблицей `glossary_links` (начать с JSON).
- **Сид** (`app/content/`): добавить парс `glossary.json` в `loader.py` и
  идемпотентный upsert по `slug` в `seed.py` (как у концептов — заменяем wholesale).
- **Репозиторий** `GlossaryRepository` (`get_all`, `get_by_slug`, `search`,
  `by_category`) — единственное место с `select(...)`.
- **Сервис** `services/glossary.py` — чтение + ORM→schema; категории как enum/набор.
- **API** (`api/endpoints/glossary.py`, **без auth** — справочник публичный, как
  каталог): `GET /api/glossary` (список, опц. `?category=&q=`),
  `GET /api/glossary/{slug}`.
- **Схемы** (`app/schemas.py`): `GlossaryTermOut`, `GlossaryListOut`.
- **Фронтенд:** страница `/glossary` (`pages/GlossaryPage.tsx`) — поиск по
  term/aliases, чипы-категории, группировка; рендер `short_md` тем же markdown +
  Shiki; кнопка «к теории» по `links` (deep-link через `slugify`). Хук
  `useGlossary` (`api/hooks.ts`) + типы (`api/types.ts`). Пункт в навигации
  `Layout.tsx`, строки в `locales/{en,ru}.json`.
- **Тесты:** `tests/test_glossary.py` — сид/список/поиск/фильтр; проверка, что
  endpoint открыт без токена.

## Принципы авторинга термина (коротко)

Каждый термин (`short_md`) — 2–5 предложений, не пересказ доки:
1. **Что это** одним-двумя предложениями (модель в голове).
2. **Аналогия / суть** — почему так, когда применяют.
3. **Подвох** — что путают / типичная ошибка на собесе (если есть).
4. Опц. крошечный фрагмент кода.
5. `links` — на полный разбор в уроке, если он есть.

Приоритеты ниже: **P0** — обязан знать любой middle (спрашивают почти всегда);
**P1** — часто; **P2** — плюсом / для уверенного middle→senior.

---

## Список терминов (что описать), по категориям

### 1. Python language & runtime internals
**P0:** GIL, байткод, CPython, интерпретатор vs компилятор, reference counting,
garbage collector (generational), мутабельность/иммутабельность, hashable,
`is` vs `==`, идентичность объекта (`id`), namespace/scope (LEGB), замыкание
(closure), late binding в замыканиях, `*args`/`**kwargs`, распаковка, генератор,
итератор, протокол итератора (`__iter__`/`__next__`), `yield`, ленивые вычисления,
list/dict/set comprehension, slice, `None`, truthiness, deep vs shallow copy,
exception (иерархия), `try/except/else/finally`, контекстный менеджер (`with`,
`__enter__/__exit__`), декоратор, `functools.wraps`, аргументы по умолчанию
(mutable default ловушка).
**P1:** PEP / PEP 8, виртуальное окружение (venv), pip, wheel, `__slots__`,
дескриптор, property, метакласс, MRO (C3), duck typing, EAFP vs LBYL, `*` и `/`
в сигнатуре (keyword-only/positional-only), f-strings, walrus `:=`, pattern
matching (`match`), `dataclass`, `namedtuple`, `enum`, type hints / typing,
`Optional`/`Union`/`|`, generics (`TypeVar`, `Generic`), `Protocol`, mypy.
**P2:** GC циклические ссылки, `weakref`, `__del__` и его опасности,
интернирование строк/малых int, `sys.intern`, frame/stack, `dis`, bytecode cache
(`__pycache__`), сборка C-расширений, ABI, `ctypes`/`cffi`, free-threaded build
(PEP 703, «no-GIL»), subinterpreters.

### 2. ООП и принципы дизайна
**P0:** класс vs объект, инкапсуляция, наследование, полиморфизм, абстракция,
композиция vs наследование, `self`, `__init__`, `classmethod`, `staticmethod`,
магические/dunder методы, `__repr__` vs `__str__`, `__eq__`/`__hash__`, интерфейс /
ABC (`abc`), SOLID (S/O/L/I/D по отдельности), DRY, KISS, YAGNI.
**P1:** mixin, множественное наследование, паттерны: Singleton, Factory,
Strategy, Observer, Adapter, Decorator (паттерн vs питон-декоратор), Repository,
Dependency Injection, IoC, фабричный метод, value object, DTO.
**P2:** Law of Demeter, tell-don't-ask, anemic vs rich domain model, DDD (entity,
aggregate, bounded context), CQRS, event sourcing, hexagonal/clean architecture.

### 3. Конкурентность и асинхронность
**P0:** процесс vs поток, параллелизм vs конкурентность, асинхронность, event
loop, корутина, `async/await`, `asyncio`, `await`-able, блокирующий vs
неблокирующий I/O, CPU-bound vs I/O-bound, почему GIL мешает потокам на CPU,
`threading`, `multiprocessing`, race condition, гонка данных, deadlock, lock /
mutex, GIL и потоки.
**P1:** `asyncio.gather`/`TaskGroup`, `Task` vs корутина, `run_in_executor`,
ThreadPool/ProcessPool, `concurrent.futures`, семафор, очередь (`queue.Queue`,
`asyncio.Queue`), backpressure, отмена задач (`CancelledError`), таймауты,
green threads, кооперативная многозадачность, контекст-переключение.
**P2:** структурированная конкурентность, `contextvars`, atomic-операции, CAS,
spinlock, starvation, livelock, ASGI vs WSGI (как раз про конкурентность),
`uvloop`, `anyio`, gevent/eventlet.

### 4. Web, HTTP, API
**P0:** HTTP методы (GET/POST/PUT/PATCH/DELETE), идемпотентность, статус-коды
(2xx/3xx/4xx/5xx, 200/201/204/301/302/304/400/401/403/404/409/422/429/500/502/503),
заголовки, query vs path vs body, REST, ресурс, stateless, cookie, сессия,
CORS, content negotiation, JSON, request/response, URL/URI, API, endpoint,
client-server.
**P1:** аутентификация vs авторизация, JWT, OAuth2, OpenID Connect, Bearer-токен,
refresh token, CSRF, XSS, rate limiting, pagination (offset vs cursor),
versioning API, OpenAPI/Swagger, webhook, WebSocket, SSE, long polling,
gRPC, GraphQL, REST vs RPC, HATEOAS, ETag, кэш-заголовки (Cache-Control),
TLS/HTTPS, mTLS.
**P2:** HTTP/1.1 vs HTTP/2 vs HTTP/3, keep-alive, chunked transfer, multipart,
gzip/brotli, CDN, reverse proxy, load balancer, sticky sessions, API gateway,
BFF, idempotency key, HMAC-подпись вебхуков.

### 5. Фреймворки (FastAPI / Django / Flask)
**P0:** FastAPI, Flask, Django, маршрут/роутинг, middleware, dependency injection
(Depends), Pydantic, валидация, сериализация, ORM (общее), миграции (общее),
шаблон MVC/MTV, request lifecycle.
**P1:** ASGI/WSGI сервер (uvicorn/gunicorn), Pydantic v2 (`BaseModel`,
`Field`, `model_validator`), Pydantic Settings, фоновые задачи (BackgroundTasks),
тэги/документация OpenAPI, response_model, статус-коды в роутах, Django ORM,
Django REST Framework, Flask blueprints, lifespan/startup-shutdown.
**P2:** Starlette (под капотом FastAPI), middleware-стек, ASGI-приложение как
callable, кастомные dependency-scopes, Django signals, Django admin, ninja.

### 6. Базы данных, SQL, ORM
**P0:** реляционная БД, таблица/строка/столбец, primary key, foreign key, индекс,
SQL (SELECT/INSERT/UPDATE/DELETE), JOIN (inner/left/right/full), GROUP BY,
агрегатные функции, WHERE vs HAVING, нормализация (1NF/2NF/3NF), денормализация,
транзакция, ACID, ORM, N+1 проблема, миграция, ROLLBACK/COMMIT, NULL.
**P1:** ACID по буквам, уровни изоляции (read uncommitted/committed, repeatable
read, serializable), грязное/неповторяемое чтение, фантомное чтение, блокировки
(row/table), оптимистичная vs пессимистичная блокировка, deadlock в БД,
connection pool, prepared statement, SQL-инъекция, EXPLAIN/план запроса,
composite index, covering index, B-tree индекс, уникальный constraint, каскады,
lazy vs eager loading, SQLAlchemy session/unit of work, identity map.
**P2:** MVCC, WAL, vacuum (Postgres), партиционирование, шардирование, репликация
(master-slave, read replica), CAP-теорема, BASE, CTE, оконные функции, материал.
view, full-text search, JSONB, GIN-индекс, sequence/serial, NoSQL (document/
key-value/column/graph), MongoDB, eventual consistency, 2PC, saga.

### 7. Кэш, очереди, брокеры
**P0:** кэш, Redis, TTL, инвалидация кэша, cache hit/miss, очередь сообщений,
брокер, producer/consumer, фоновая задача, Celery.
**P1:** стратегии кэширования (cache-aside, write-through, write-back), LRU/LFU,
memcached, Redis-структуры (string/hash/list/set/zset), pub/sub, RabbitMQ, Kafka,
AMQP, at-least-once / at-most-once / exactly-once, ack, dead-letter queue,
idempotent consumer, Celery worker/beat/broker/backend, распределённый лок.
**P2:** consistent hashing, Redis Cluster/Sentinel, persistence (RDB/AOF),
Kafka partition/offset/consumer group, log compaction, event-driven архитектура,
outbox pattern, CDC, stream processing, thundering herd, cache stampede.

### 8. Архитектура и системный дизайн
**P0:** монолит vs микросервисы, API, слоистая архитектура, масштабирование
(вертикальное vs горизонтальное), stateless-сервис, балансировка нагрузки,
SLA/SLO, latency vs throughput.
**P1:** load balancer, reverse proxy, CDN, репликация, шардирование, очередь как
буфер, идемпотентность, отказоустойчивость, single point of failure,
graceful degradation, circuit breaker, retry с backoff, rate limiting,
bottleneck, capacity planning, 12-factor app.
**P2:** CAP/PACELC, consistency models, service mesh, sidecar, saga, CQRS, event
sourcing, eventual consistency, idempotency key, distributed tracing, bulkhead,
back-pressure, leader election, consensus (Raft/Paxos), quorum.

### 9. Тестирование
**P0:** unit-тест, интеграционный тест, e2e, pytest, fixture, assert, mock/stub,
покрытие (coverage), AAA (arrange-act-assert), TDD, регрессия.
**P1:** `unittest.mock`, monkeypatch, parametrize, тестовая пирамида, flaky test,
фабрики данных (factory_boy), `pytest`-маркеры, тест-дабл (mock/stub/fake/spy),
контрактные тесты, snapshot-тест, нагрузочное тестирование (locust), property-based
(hypothesis).
**P2:** mutation testing, BDD, тест-контейнеры (testcontainers), CI-прогон,
изоляция тестов, тест БД (транзакционный rollback), golden master.

### 10. DevOps, деплой, observability
**P0:** Docker, контейнер vs образ, Dockerfile, CI/CD, git, переменные окружения,
лог, deploy, environment (dev/stage/prod).
**P1:** docker-compose, volume, образ-слои, registry, Kubernetes (под/деплоймент/
сервис), оркестрация, reverse proxy (nginx/Caddy), TLS-сертификат, healthcheck,
12-factor, blue-green / canary деплой, rollback, мониторинг, метрики
(Prometheus), Grafana, structured logging, log level, трейсинг (OpenTelemetry).
**P2:** IaC (Terraform), Ansible, secrets management (Vault), service discovery,
ingress, HPA, helm, immutable infra, observability (logs/metrics/traces),
SLI/SLO/error budget, on-call, chaos engineering, GitOps.

### 11. Сеть и безопасность
**P0:** TCP vs UDP, IP, порт, DNS, HTTP vs HTTPS, TLS/SSL, симметричное vs
асимметричное шифрование, хеширование vs шифрование, хеш пароля (bcrypt/argon2),
соль (salt), HTTPS-handshake (база), firewall.
**P1:** TCP-handshake, OSI/TCP-IP модель, латентность/RTT, NAT, проксирование,
JWT-подпись (HS/RS), CORS, CSRF, XSS, SQL-инъекция, OWASP Top 10,
rate limiting, DDoS, идемпотентность как защита, секреты в env, least privilege.
**P2:** mTLS, PKI, сертификатные цепочки, perfect forward secrecy, JWT-уязвимости
(alg=none), CSP, SSRF, IDOR, supply-chain атаки, токены доступа vs API-ключи,
zero trust.

### 12. CS-основы и алгоритмы (для собеса)
**P0:** массив/список, словарь/хеш-таблица, множество, стек, очередь, дерево,
связный список, O-нотация (big-O), сложность по времени/памяти, рекурсия,
сортировка (общая идея), бинарный поиск, хеш-функция, коллизия.
**P1:** амортизированная сложность, граф (BFS/DFS), куча (heap/priority queue),
двоичное дерево поиска, сбалансированное дерево, хеш-таблица (открытая адресация
vs цепочки), быстрая сортировка / слияние, динамическое программирование,
жадный алгоритм, two pointers, sliding window.
**P2:** trie, B-дерево (зачем в БД), bloom filter, LRU-реализация (dict+linked
list), топологическая сортировка, union-find, хеширование (consistent),
NP-полнота (на уровне «что это»).

---

## Definition of done (Фаза 5c — механика)

- `content/glossary.json` с **минимум всеми P0** терминами (старт ~80–120 шт).
- Таблица `glossary_terms` + сид (идемпотентный upsert по slug).
- `GET /api/glossary`(+`?category=&q=`) и `GET /api/glossary/{slug}` — без auth.
- Страница `/glossary`: поиск, фильтр по категориям, markdown-рендер, «к теории».
- i18n-строки (ru/en) для UI раздела (термины — только ru на старте).
- Тест `tests/test_glossary.py` (сид/список/поиск/публичность endpoint) зелёный.
- Затем P1/P2 наполняются в Фазе 6 вместе с уроками.
