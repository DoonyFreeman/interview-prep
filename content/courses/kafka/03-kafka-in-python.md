# Kafka в Python-сервисе

> Цель урока: собрать всё в рабочий сервис. Выбор клиента (aiokafka vs
> confluent-kafka), интеграция с FastAPI через lifespan, паттерн transactional
> outbox (как не терять события при записи в БД), локальная Kafka в
> docker-compose и честная карта выбора «Kafka или Celery».

## Python-клиенты: aiokafka и confluent-kafka

Два основных клиента:

- **confluent-kafka** — обёртка над C-библиотекой librdkafka: максимальная
  производительность и полнота фич (транзакции, все тонкие настройки). API
  синхронный/callback-овый; в asyncio-приложении вызовы заворачивают в
  `run_in_executor` или выделенный поток.
- **aiokafka** — чистый asyncio-клиент (`async/await` нативно). Идеален для
  FastAPI-сервиса: producer/consumer живут в том же event loop, без потоков.
  Производительности для типичного бэкенда хватает с запасом.

Практическое правило: **asyncio-сервис → aiokafka; выжать максимум/нужны
транзакции → confluent-kafka**.

Интеграция с FastAPI — та же идея, что с пулом БД: клиент создаётся **один раз в
lifespan**, а не на запрос:

```python
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = AIOKafkaProducer(
        bootstrap_servers="kafka:9092",
        acks="all", enable_idempotence=True,
    )
    await producer.start()            # соединение с кластером — один раз
    app.state.kafka = producer
    yield
    await producer.stop()             # flush + корректное закрытие

app = FastAPI(lifespan=lifespan)

@app.post("/orders")
async def create_order(request: Request):
    order_id = await save_order()     # запись в БД
    await request.app.state.kafka.send_and_wait(
        "orders", key=order_id.encode(), value=b'{"status": "created"}'
    )
    return {"id": order_id}
```

Консьюмер в том же сервисе запускают фоновой задачей из lifespan
(`asyncio.create_task(consume())`) либо — чаще и чище — выносят в **отдельный
процесс/контейнер**: у консьюмера свой жизненный цикл (ребалансировки, retry),
и мешать его с HTTP-обработкой в одном процессе быстро становится больно.

**Аналогия.** aiokafka против confluent-kafka — как asyncpg против psycopg в
C-обёртке: первый «родной» для event loop, второй быстрее и богаче, но требует
аккуратности с потоками. А producer в lifespan — как пул соединений: телефонную
линию с брокером держат постоянно, а не набирают номер на каждый запрос.

## Transactional outbox

Классическая ловушка: обработчик должен **и** записать в БД, **и** отправить
событие. Две системы — двух-фазного коммита между ними нет:

```python
async with session.begin():
    session.add(order)          # 1) БД
await kafka.send_and_wait(...)  # 2) Kafka — а если упали между 1 и 2?
```

Упали после коммита БД, но до отправки → заказ есть, события нет, подписчики
никогда о нём не узнают. Поменять местами — событие есть, заказа нет. Любой
порядок теряет консистентность.

**Transactional outbox**: событие записывается **в ту же БД, в той же
транзакции**, что и бизнес-данные — в таблицу `outbox`. Отдельный фоновый
процесс (publisher) читает неотправленные строки и публикует их в Kafka.

```python
async with session.begin():                 # ОДНА транзакция БД
    session.add(order)
    session.add(OutboxEvent(                # событие атомарно с данными
        topic="orders", key=order.id,
        payload={"status": "created"},
    ))

# фоновый publisher (отдельная задача/процесс):
async def publish_outbox():
    while True:
        events = await fetch_unsent(limit=100)   # WHERE sent_at IS NULL
        for e in events:
            await kafka.send_and_wait(e.topic, key=e.key, value=e.payload)
            await mark_sent(e)                   # sent_at = now()
        await asyncio.sleep(0.5)
```

Гарантия: заказ закоммичен ⇔ событие закоммичено. Publisher может упасть между
отправкой и `mark_sent` → событие уйдёт повторно, т.е. итоговая семантика —
**at-least-once**, и потребители, как обычно, идемпотентны. Альтернатива
поллингу — CDC (Debezium читает WAL БД), но идея та же: источник события — БД.

**Аналогия.** Исходящая корреспонденция в канцелярии: письмо не бросают в
почтовый ящик на улице сразу (вдруг забудешь по дороге) — его кладут в лоток
«исходящие» **тем же движением**, что подшивают приказ в дело. Курьер (publisher)
регулярно забирает лоток и относит на почту; пока не отнёс — письма надёжно лежат
в лотке.

## Kafka в docker-compose

Современная Kafka работает в режиме **KRaft** — без ZooKeeper: брокер сам ведёт
метаданные кластера через встроенный Raft. Один контейнер — полноценная Kafka для
разработки:

```yaml
services:
  kafka:
    image: apache/kafka:3.8.0
    ports:
      - "9092:9092"          # для клиентов с хоста
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller   # KRaft: один узел = и брокер, и контроллер
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      # два listener'а: изнутри docker-сети и с хоста
      KAFKA_LISTENERS: INTERNAL://kafka:29092,CONTROLLER://kafka:9093,EXTERNAL://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: INTERNAL://kafka:29092,EXTERNAL://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: INTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: INTERNAL
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      # один брокер — служебным топикам хватает одной реплики
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
    healthcheck:
      test: ["CMD", "sh", "-c",
             "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list"]
      interval: 10s
      timeout: 5s
      retries: 10

  app:
    build: .
    environment:
      KAFKA_BOOTSTRAP: kafka:29092   # изнутри сети — internal listener!
    depends_on:
      kafka:
        condition: service_healthy
```

Классическая боль здесь — **advertised listeners**. Клиент подключается к
`bootstrap`-адресу, а брокер в ответ присылает адрес, по которому «на самом деле»
к нему ходить (advertised). Если брокер рекламирует `localhost:9092`, контейнер
приложения по этому адресу попадёт **в себя**, а не в Kafka — отсюда вечное
«с хоста работает, из контейнера нет». Решение как выше: два listener'а —
`INTERNAL://kafka:29092` для docker-сети, `EXTERNAL://localhost:9092` для хоста.

**Аналогия.** Advertised listener — визитка, которую брокер вручает клиенту:
«звоните мне по этому номеру». Если на визитке внутренний добавочный офиса
(localhost), звонящий с улицы не дозвонится — нужны две визитки: для своих и для
внешних.

## Kafka или Celery: карта выбора

Итоговый вопрос любого собеседования по этой теме: «у вас уже есть Celery — зачем
Kafka?» (или наоборот). Ответ — они решают **разные задачи**:

| | Celery (+ Redis/RabbitMQ) | Kafka |
|---|---|---|
| Модель | **задача**: «сделай X», адресована исполнителю | **событие**: «произошло Y», адресата нет |
| После обработки | задача исчезает из очереди | событие хранится (retention), можно перечитать |
| Потребители | один воркер выполняет задачу | много независимых групп читают один поток |
| Из коробки | retry, countdown/ETA, result backend, канвасы | порядок по ключу, реплей истории, огромный throughput |
| Типовые кейсы | письмо, PDF, thumbnail, периодика | интеграция сервисов, поток кликов/метрик, event sourcing, буфер пиков |

Правила выбора:

- Нужен **результат конкретной работы** (и её ретраи/расписание) → Celery.
- Нужно, чтобы **несколько систем узнали о факте** (сейчас или потом), нужен
  реплей/история/порядок по ключу → Kafka.
- Они **сосуществуют**: сервис публикует `order.created` в Kafka; консьюмер
  биллинга, получив событие, ставит Celery-задачу «сформировать счёт» со своими
  ретраями. События — транспорт фактов, задачи — исполнение работы.
- Честный аргумент против Kafka в маленьком проекте: операционная цена (кластер,
  мониторинг лага, ребалансировки). Для «отправить письмо в фоне» Kafka — из
  пушки по воробьям.

**Аналогия.** Celery — курьерская служба: конкретное поручение, исполнитель,
подтверждение доставки, повтор при неудаче. Kafka — новостная лента компании:
факт публикуется один раз, отделы читают её каждый в своём темпе, архив
листается назад. Прочитав новость, отдел может вызвать курьера — это и есть
«Kafka + Celery вместе».

---

## Памятка для собеседования

- **Клиенты**: aiokafka — нативный asyncio (FastAPI), confluent-kafka — обёртка
  librdkafka (макс. скорость, транзакции; в asyncio — через executor). Producer —
  **один на приложение, в lifespan** (как пул БД); консьюмер — фоновая задача или
  отдельный процесс.
- **Outbox**: «БД + Kafka» без outbox теряет события (упали между коммитом и
  send). Решение: событие пишется в таблицу `outbox` **той же транзакцией**,
  фоновый publisher доставляет; итог — at-least-once, потребители идемпотентны.
- **Docker**: KRaft (без ZooKeeper); ловушка — **advertised listeners**: для
  docker-сети и хоста нужны разные (`kafka:29092` vs `localhost:9092`).
- **Kafka vs Celery**: событие («произошло, хранится, читают многие») vs задача
  («сделай, исчезает, один исполнитель»). Часто вместе: событие в Kafka →
  консьюмер ставит Celery-задачу.

## Частые ошибки в ответах

- Создавать producer/соединение на каждый HTTP-запрос вместо lifespan-singleton.
- Не видеть проблемы в «сохранил в БД, потом отправил в Kafka» — это потеря
  событий при падении между операциями; ответ — transactional outbox (или CDC).
- Объяснять «из контейнера не подключается» чем угодно, кроме advertised
  listeners.
- На вопрос «Kafka или Celery» отвечать «Kafka круче/новее» вместо разницы
  моделей (событие vs задача) и сценариев их совместной работы.
- Забывать операционную цену Kafka и тащить её в проект ради фоновой отправки
  писем.
