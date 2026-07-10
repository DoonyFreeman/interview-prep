# Статика, TLS и лимиты

> Цель урока: три ежедневные задачи nginx. Отдать статику и SPA (root vs alias,
> try_files, gzip, кэш-заголовки), терминировать TLS (сертификаты, редирект
> 80→443, HSTS) и защитить бэкенд лимитами (размер тела, таймауты — откуда
> берутся 502/504, rate limiting с burst).

## Статика, gzip и кэширование

Статику (собранный фронтенд, картинки) отдаёт nginx, не Python. Два способа
указать, откуда брать файлы:

- **`root`** — путь **приклеивается** к URI: `root /var/www;` +
  `GET /assets/app.js` → файл `/var/www/assets/app.js`.
- **`alias`** — путь **заменяет** совпавший префикс location:
  `location /assets/ { alias /var/www/dist/; }` + `GET /assets/app.js` →
  `/var/www/dist/app.js` (без `/assets`). Классика путаницы — помнить разницу.

Для SPA (наш React-фронтенд) нужен **fallback на index.html**: маршруты вроде
`/courses/kafka` существуют только в клиентском роутере, на диске такого файла
нет. Решение — `try_files`:

```nginx
server {
    listen 80;
    root /var/www/dist;               # собранный фронтенд (vite build)

    location / {
        # 1) точный файл  2) папка  3) отдать SPA-шелл
        try_files $uri $uri/ /index.html;
    }

    location /assets/ {               # хэшированные бандлы vite
        expires 1y;                               # Cache-Control: max-age=…
        add_header Cache-Control "public, immutable";
    }

    gzip on;                          # сжатие текстовых ответов
    gzip_types text/css application/javascript application/json;
    gzip_min_length 1024;             # мелкое сжимать нет смысла
}
```

Кэш-стратегия SPA: бандлы с хэшем в имени (`index-BdF1I_W2.js`) кэшируются
«навечно» (`immutable`) — новая сборка меняет имя файла; а сам `index.html` не
кэшируется, чтобы клиент сразу увидел новые имена бандлов. Это ровно то, что в
нашем проекте делает FastAPI-fallback в Docker-образе, — nginx-вариант той же
схемы.

**Аналогия.** `root` — «склад один, номер стеллажа в заявке»; `alias` —
«для заявок этого отдела ходи на другой склад». `try_files … /index.html` —
консьерж: нет такого кабинета — проводи гостя в холл (SPA), дальше он сам.
Кэш с хэшем — книги с уникальным ISBN: новую версию не перепутать со старой.

## TLS и HTTPS

**TLS-терминация**: nginx принимает HTTPS-соединение, расшифровывает его и
дальше говорит с бэкендом по HTTP внутри доверенной сети. Плюсы: сертификаты и
шифры в одном месте, бэкенд-код про TLS не знает.

```nginx
server {                              # редирект всего HTTP на HTTPS
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;                         # HTTP/2: мультиплексирование запросов
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    # HSTS: браузер запоминает "только https" на год
    add_header Strict-Transport-Security "max-age=31536000" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Forwarded-Proto $scheme;   # бэкенд знает: https
    }
}
```

Откуда берётся сертификат: **Let's Encrypt** выдаёт бесплатные на 90 дней;
`certbot` проходит ACME-проверку (кладёт файл в `/.well-known/acme-challenge/`
или DNS-запись), устанавливает сертификат и обновляет по расписанию. **Caddy**
делает всё это автоматически без строчки конфига — поэтому наш прод на Caddy, а
nginx-вариант надо уметь читать, потому что он повсюду.

`X-Forwarded-Proto: https` здесь критичен: без него FastAPI генерирует ссылки
и редиректы на `http://`, и посреди HTTPS-сайта появляется mixed content.

**Аналогия.** TLS-терминация — досмотр на входе в бизнес-центр: проверка и
«расшифровка» происходят один раз на проходной (nginx), внутри здания
сотрудники ходят свободно (HTTP во внутренней сети). HSTS — заметка в телефоне
посетителя: «в это здание — только через главный вход, год минимум».

## Таймауты, лимиты и rate limiting

nginx — линия обороны бэкенда. Три группы настроек:

**Размер тела.** `client_max_body_size` (по умолчанию **1m**!) — больше →
клиенту вернётся **413 Request Entity Too Large**. Классика: «файл не
загружается на прод, локально всё ок» — забыли поднять лимит.

**Таймауты к бэкенду** — откуда берутся 5xx на проксировании:

- `proxy_connect_timeout` — не успели установить соединение с бэкендом;
- `proxy_read_timeout` (по умолчанию 60s) — бэкенд думает дольше → nginx
  разрывает и отдаёт **504 Gateway Timeout**;
- бэкенд вовсе не отвечает/сбрасывает соединение (упал, не слушает порт) →
  **502 Bad Gateway**.

**Rate limiting** — ограничение частоты запросов (по IP, токену и т.п.):

```nginx
http {
    # зона на 10 МБ состояния; ключ — IP; скорость — 10 запросов/сек
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        location /api/ {
            # burst: очередь на всплеск; nodelay: не растягивать очередь
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://127.0.0.1:8000;

            client_max_body_size 10m;      # загрузки до 10 МБ
            proxy_read_timeout   30s;      # дольше 30с — 504
        }
    }
}
```

Алгоритм — «дырявое ведро»: `rate` — скорость утечки, `burst` — объём ведра.
Всплеск до 20 запросов пройдёт (с `nodelay` — сразу), всё сверх — **503**
(у `limit_req` именно 503, часто переопределяют в 429 через
`limit_req_status 429;`). Проверка руками:

```bash
for i in $(seq 1 40); do curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.example.com/api/health; done | sort | uniq -c
#   30 200      ← rate+burst пропустили
#   10 503      ← лимит сработал (или 429, если переопределили)
```

**Аналогия.** Клуб с фейс-контролем: вместимость гардероба —
`client_max_body_size` (с чемоданом не пустят — 413), терпение официанта —
`proxy_read_timeout` (кухня молчит полчаса — приносит извинения, 504), а на
входе пускают 10 человек в минуту с запасом на подъехавший автобус (rate +
burst); остальным — «приходите позже» (503/429).

---

## Памятка для собеседования

- **Статика**: `root` приклеивает URI к пути, `alias` заменяет префикс
  location. SPA — `try_files $uri $uri/ /index.html`. Хэшированные бандлы —
  `expires 1y` + `immutable`; `index.html` не кэшировать. `gzip on` +
  `gzip_types` для текста.
- **TLS**: терминация на nginx (внутрь — HTTP), редирект `return 301
  https://…`, HSTS-заголовок, `http2 on`. Let's Encrypt + certbot (ACME,
  90 дней, авто-обновление); Caddy делает это сам. Не забыть
  `X-Forwarded-Proto`, иначе редиректы приложения ведут на http.
- **Лимиты**: `client_max_body_size` (дефолт 1m!) → **413**; бэкенд молчит
  дольше `proxy_read_timeout` → **504**; бэкенд недоступен → **502**.
  `limit_req_zone` + `limit_req burst=… nodelay` — «дырявое ведро», сверх
  лимита **503** (переопределяют в 429).

## Частые ошибки в ответах

- Путать `root` и `alias` (или не знать, зачем try_files для SPA — «почему
  F5 на /courses/... даёт 404»).
- Кэшировать `index.html` навечно — пользователи «залипают» на старой версии
  фронтенда после деплоя.
- Не различать 502 (бэкенд недоступен/оборвал) и 504 (бэкенд не успел до
  таймаута) — это разные диагнозы.
- Забывать, что дефолтный `client_max_body_size` — 1 МБ, и дебажить «загрузку
  файлов» на уровне приложения.
- Называть лимит запросов «nginx вернёт 429»: по умолчанию `limit_req` отдаёт
  **503**, 429 — через `limit_req_status`.
