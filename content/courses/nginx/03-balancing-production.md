# Балансировка и продакшен

> Цель урока: собрать продакшен-схему. Балансировка на несколько инстансов
> (upstream, алгоритмы, health-чеки), WebSocket/SSE через прокси (Upgrade и
> буферизация), полный docker-compose «nginx + FastAPI» и отладка: nginx -t,
> reload без даунтайма, чтение логов и диагноз типичных 502/504/413.

## Upstream и балансировка

Когда один процесс перестаёт вывозить, инстансов становится несколько, и nginx
превращается в **балансировщик**. Группа бэкендов описывается блоком
**upstream**:

```nginx
upstream backend {
    # round-robin по умолчанию: запросы по кругу
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003 weight=2;   # этому — вдвое больше запросов

    # альтернативы:
    # least_conn;   — новому запросу тот, у кого меньше активных соединений
    # ip_hash;      — клиент прилипает к инстансу по IP (sticky по-бедному)
}

server {
    location / {
        proxy_pass http://backend;    # имя upstream вместо адреса
        # если инстанс не ответил/5xx — попробовать следующий:
        proxy_next_upstream error timeout http_502 http_503;
    }
}
```

Алгоритмы: **round-robin** (по умолчанию, равномерно по кругу, `weight` задаёт
пропорции), **least_conn** (кому сейчас легче — хорош при разной длительности
запросов), **ip_hash** (стабильный инстанс для клиента — костыльный
sticky-session, ломается за NAT, где у тысяч людей один IP).

**Health-чеки в open-source nginx — пассивные**: он не пингует бэкенды заранее,
а помечает инстанс упавшим **после** неудачных запросов (`max_fails=1
fail_timeout=10s` по умолчанию) и на время убирает из ротации; живые запросы
при этом спасает `proxy_next_upstream`. Активные проверки (фоновый опрос
`/health`) — в коммерческом NGINX Plus или в HAProxy/Traefik/Caddy.

Важно для Python: балансировка nginx **не заменяет** воркеры. Типовая схема —
несколько uvicorn-воркеров (или инстансов контейнера) за одним nginx; stateless
Python-процессы масштабируются просто добавлением `server` в upstream.

**Аналогия.** Диспетчер такси: заказы по очереди всем водителям (round-robin),
или тому, кто свободнее (least_conn), или «ваш постоянный водитель» (ip_hash).
Пассивный health-чек — водителя убирают из ротации после того, как он не взял
пару заказов, а не потому, что диспетчер обзванивает всех каждое утро.

## WebSocket и SSE через nginx

FastAPI умеет WebSocket и Server-Sent Events, но через прокси они требуют
внимания.

**WebSocket** начинается как HTTP-запрос с «рукопожатием» **Upgrade**: клиент
просит переключить протокол (101 Switching Protocols), дальше соединение
становится двусторонним и долгоживущим. Заголовки `Upgrade`/`Connection` —
**hop-by-hop**: nginx не передаёт их дальше сам, это надо сделать явно:

```nginx
location /ws/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;                    # Upgrade есть только в HTTP/1.1
    proxy_set_header Upgrade $http_upgrade;     # пробросить "upgrade: websocket"
    proxy_set_header Connection "upgrade";      # и намерение переключиться
    proxy_read_timeout 3600s;                   # молчаливые сокеты живут долго
}
```

Без этих строк рукопожатие ломается, клиент получает ошибку подключения.
`proxy_read_timeout` важен: дефолтные 60 секунд тишины — и nginx разорвёт
«молчащий» сокет (поэтому же в WebSocket-приложениях делают ping/pong).

**SSE** (Server-Sent Events) — обычный HTTP-ответ, который сервер пишет
бесконечно (`text/event-stream`). Здесь враг — **буферизация**: nginx по
умолчанию копит тело ответа в буфер, и события «зависают», не доходя до
клиента. Для стриминга её выключают:

```nginx
location /events/ {
    proxy_pass http://backend;
    proxy_buffering off;            # события уходят клиенту сразу
    proxy_read_timeout 3600s;
}
```

(Приложение может попросить то же заголовком ответа `X-Accel-Buffering: no`.)

**Аналогия.** Обычный HTTP — обмен письмами через секретаря. WebSocket — просьба
«соедините нас напрямую и не кладите трубку» (Upgrade): секретарь должен
передать именно эту просьбу, а не пересказать её своими словами. SSE — диктовка
по телефону: если секретарь записывает всё в блокнот и пересказывает раз в час
(буферизация), «прямой эфир» теряет смысл.

## nginx и FastAPI в docker-compose

Полная связка нашего стека: контейнер приложения не публикует порт наружу,
наружу смотрит только nginx.

```yaml
# docker-compose.yml
services:
  app:
    build: .
    # порт наружу НЕ публикуем — к app ходит только nginx по внутренней сети
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      retries: 5

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro   # наш конфиг
      - ./certs:/etc/nginx/certs:ro                       # сертификаты
    depends_on:
      app:
        condition: service_healthy
```

```nginx
# nginx.conf — проксируем на имя сервиса из compose-сети
upstream app {
    server app:8000;              # DNS-имя "app" резолвит docker-сеть
}
server {
    listen 80;
    location / {
        proxy_pass http://app;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ключевые детали: адрес бэкенда — **имя сервиса** (`app:8000`), его резолвит
встроенный DNS docker-сети; `expose` вместо `ports` у приложения (не торчит в
интернет — то же самое мы сделали в нашем проде, привязав app к 127.0.0.1);
`depends_on: service_healthy`, чтобы nginx не стартовал раньше живого бэкенда
(иначе первые запросы — 502). В нашем реальном проде роль nginx играет Caddy —
конфиг другой, топология та же.

**Аналогия.** Офис с одной проходной: у кабинетов (app) нет дверей на улицу
(`expose`, не `ports`), вход только через ресепшен (nginx, 80/443), который
знает сотрудников по именам (docker-DNS `app:8000`), и открывается офис только
когда сотрудники на местах (healthcheck + depends_on).

## Отладка: логи и типичные ошибки

Рабочий цикл изменения конфига:

```bash
nginx -t                  # проверить синтаксис И валидность (пути, зоны)
nginx -s reload           # применить БЕЗ даунтайма: старые воркеры дорабатывают
                          # свои соединения, новые берут новый конфиг
docker compose exec nginx nginx -t          # то же в контейнере
docker compose exec nginx nginx -s reload
```

`reload` — graceful: мастер-процесс читает конфиг, поднимает новых воркеров,
старые дозакрывают активные соединения. Ошибка в конфиге при reload не роняет
работающий nginx — он остаётся на старом конфиге (а вот `restart` с битым
конфигом просто не поднимется — поэтому всегда сначала `nginx -t`).

Два лога: **access.log** — каждый запрос (код, время, апстрим), **error.log** —
причины ошибок. Диагноз всегда начинается с error.log:

- **502 Bad Gateway** — nginx не смог поговорить с бэкендом: `connection
  refused` (процесс не слушает порт — упал/не поднялся/не тот адрес в
  proxy_pass), `no live upstreams` (все инстансы помечены упавшими).
- **504 Gateway Timeout** — соединение есть, но бэкенд не ответил за
  `proxy_read_timeout`: долгий запрос/блокировка в приложении. Чинится
  оптимизацией эндпоинта или осознанным поднятием таймаута.
- **413 Request Entity Too Large** — тело больше `client_max_body_size`
  (помним про дефолт 1m).
- **404 на маршрутах SPA** — забыли `try_files … /index.html`.
- **Бесконечный редирект-цикл** — редирект на https при потерянном
  `X-Forwarded-Proto`: приложение думает, что оно на http, и снова редиректит.

**Аналогия.** `nginx -t` + `reload` — репетиция и пересменка: новый состав
выходит на сцену, старый доигрывает акт; если новый сценарий с ошибками —
спектакль продолжается по старому. 502 — «абонент недоступен», 504 — «абонент
взял трубку и молчит»: лечатся по-разному, различать их — первый шаг отладки.

---

## Памятка для собеседования

- **Upstream**: round-robin (+`weight`) / least_conn / ip_hash (sticky
  по-бедному). Health-чеки в OSS nginx **пассивные** (max_fails/fail_timeout +
  `proxy_next_upstream`); активные — Plus/HAProxy. Балансировка не заменяет
  uvicorn-воркеры.
- **WebSocket**: `proxy_http_version 1.1` + проброс `Upgrade`/`Connection`
  (hop-by-hop!) + большой `proxy_read_timeout` (и ping/pong). **SSE**:
  `proxy_buffering off`, иначе события застревают в буфере.
- **Compose**: nginx наружу (80/443), app — только `expose` во внутренней
  сети; `proxy_pass http://app:8000` через docker-DNS; `depends_on:
  service_healthy` против 502 на старте.
- **Отладка**: `nginx -t` → `nginx -s reload` (graceful, без даунтайма; битый
  конфиг не применится). error.log первым. **502** — бэкенд недоступен, **504**
  — не успел за таймаут, **413** — тело больше лимита, SPA-404 — нет try_files,
  redirect-цикл — потерян `X-Forwarded-Proto`.

## Частые ошибки в ответах

- Верить, что open-source nginx активно пингует бэкенды: health-чеки пассивные,
  по реальным неудачам.
- Использовать ip_hash как «настоящие» sticky-sessions и не знать про NAT.
- Забывать `proxy_http_version 1.1` + `Upgrade/Connection` для WebSocket
  («через nginx сокеты не работают») или буферизацию для SSE.
- Публиковать порт приложения наружу вместе с nginx (`ports` вместо `expose`) —
  прокси легко обойти.
- Не различать 502/504 и лечить оба «перезагрузкой»; править конфиг на проде
  без `nginx -t` и graceful reload.
