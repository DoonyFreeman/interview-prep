# Deployment

Single small host, Docker Compose, one app image behind a Caddy reverse proxy
with automatic TLS. SQLite lives on a named volume; content is baked into the
image and re-seeded on startup.

```
internet ──443──> caddy (TLS, Let's Encrypt) ──> app:8000 (FastAPI: SPA + /api)
                                                    └── volume app-data: SQLite
```

## Prerequisites

- A host (1 small VPS is enough) with **Docker Engine + Compose v2**.
- Ports **80 and 443** open to the internet (HTTP-01/TLS-ALPN challenge + serving).
- **For HTTPS:** either a real domain with A/AAAA record pointing at the host, OR
  use `{IP}.sslip.io` (see below) for automatic Let's Encrypt certs without
  owning a domain.

## First deploy

```bash
# 1. Get the code
git clone <repo-url> /opt/interview-prep
cd /opt/interview-prep

# 2. Configure
cp .env.docker.example .env
#    Edit .env and set at least:
#      JWT_SECRET     -> python -c "import secrets; print(secrets.token_urlsafe(48))"
#      GEMINI_API_KEY -> your key (needed for answer grading / hints)
#      DOMAIN         -> e.g. prep.example.com
#      ACME_EMAIL     -> you@example.com

# 3. Launch (base + prod overlay = app + Caddy)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. Verify
docker compose ps                 # app + caddy healthy
curl -fsS https://$DOMAIN/health  # {"status":"ok"}
#    Open https://$DOMAIN in a browser — SPA loads, login works.
```

Caddy provisions and auto-renews the certificate; certs persist in the
`caddy_data` volume, so restarts don't re-issue.

## Fast start without a domain: sslip.io

If you don't have a domain yet, use the free `sslip.io` service:

```bash
# In .env:
DOMAIN=176.123.168.87.sslip.io        # Replace IP with your host's IP
ACME_EMAIL=your-real@email.com         # Let's Encrypt notifications

# Deploy as normal:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# The domain auto-resolves to your IP; Caddy issues a real Let's Encrypt cert.
# Open https://176.123.168.87.sslip.io in your browser (no warnings).
```

Later, when you have a domain, just edit `DOMAIN` in `.env` and restart — Caddy
auto-renews the cert under the new domain.

## Updates

```bash
cd /opt/interview-prep
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Content markdown is baked into the image and re-seeded idempotently on startup
(match by slug; a concept's questions are replaced wholesale). User state on the
volume is untouched.

## Backups

`scripts/backup.sh` takes a consistent online SQLite snapshot from the running
container into `./backups/` and prunes old ones (keeps 14 by default).

```bash
scripts/backup.sh                 # one-off
# Cron (daily 03:00):
0 3 * * * cd /opt/interview-prep && scripts/backup.sh >> backups/backup.log 2>&1
```

Copy `backups/` off-box periodically (rsync/object storage) so a host loss
doesn't lose them.

### Restore

```bash
scripts/restore.sh backups/app-YYYYMMDD-HHMMSS.db
```

Stops the app, replaces the DB on the volume (clearing stale WAL sidecars),
restarts. Re-seeds content automatically; user state comes from the snapshot.

## Operations

- **Logs:** `docker compose logs -f app` / `... logs -f caddy`
- **Restart:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart`
- **Stop:** `... down` (keeps volumes) — data and certs survive.
- **Restart policy:** both services are `restart: unless-stopped` (survive reboot
  once the Docker daemon starts on boot — ensure `systemctl enable docker`).
- **Healthchecks:** app probes `/health`; Caddy probes its own `:80`.

## Local TLS test (no real domain)

To exercise the proxy + HTTPS path locally before going live:

1. In `.env`: `DOMAIN=localhost`.
2. In `Caddyfile`: uncomment `tls internal`.
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
4. `curl -k https://localhost/health` → `{"status":"ok"}`.

Public Let's Encrypt issuance can only be verified on the real host with the real
domain and open 80/443 — it is not part of the local checks.

## Security notes

- The app port is bound to `127.0.0.1:8000` (base compose), so it is never
  exposed publicly; only Caddy faces the internet.
- Keep `.env` off version control (it is git-ignored). Rotate `JWT_SECRET` only
  when you intend to invalidate all existing sessions.
