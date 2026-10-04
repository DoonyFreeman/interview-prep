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

## Updates (CI/CD via GitHub Actions + GHCR)

The image is built **in CI**, not on the host — the small VPS OOMs on a Vite
build. On every push to `master`, `.github/workflows/build.yml` builds the
`linux/amd64` image and pushes it to GHCR
(`ghcr.io/doonyfreeman/interview-prep:{latest,<sha>}`, a private package). The
host only ever **pulls** that image:

```bash
cd /opt/interview-prep
./scripts/deploy.sh
```

`deploy.sh` does: backup DB → `git pull` (configs) → `docker compose pull app` →
`up -d --no-build` → health check. It never builds and never touches the data
volume. Content is re-seeded idempotently on startup; user state on the volume
is untouched.

### One-time setup

**On the host** (so it can pull code + the private image):

```bash
# 1. Read-only GitHub deploy key (for `git pull` of the private repo):
ssh-keygen -t ed25519 -f ~/.ssh/gh_deploy -N "" -C "interview-prep-deploy"
cat ~/.ssh/gh_deploy.pub        # add in GitHub → repo → Settings → Deploy keys (read-only)
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/gh_deploy
  IdentitiesOnly yes
EOF

# 2. Turn /opt/interview-prep into a git checkout in place (keeps .env, backups/):
cd /opt/interview-prep
git init -q && git remote add origin git@github.com:DoonyFreeman/interview-prep.git
git fetch origin && git reset --hard origin/master
git checkout -B master --track origin/master

# 3. Log in to GHCR to pull the private image (PAT with read:packages scope):
echo "<PAT>" | docker login ghcr.io -u DoonyFreeman --password-stdin
```

**In GitHub** (repo → Settings):
- **Deploy keys:** add `gh_deploy.pub` (read-only).
- **Personal access token** (classic, scope `read:packages`) for the host's
  `docker login` above.

### Continuous deployment (auto-deploy on push) — opt-in

The `deploy` job in the workflow is **skipped** until you enable it:

1. Create a CI SSH key pair; put its **public** key in the host's
   `~/.ssh/authorized_keys`, restricted to only run the deploy:
   `command="/opt/interview-prep/scripts/deploy.sh",no-port-forwarding,no-pty ssh-ed25519 AAAA...`
2. In GitHub → repo → Settings:
   - Secret `DEPLOY_SSH_KEY` = the CI **private** key.
   - Variables: `CD_ENABLED=true`, `DEPLOY_HOST=176.123.168.87`, `DEPLOY_USER=root`.
   - (Optional) Environment `production` with a required reviewer → deploys wait
     for your approval in the Actions tab.

With that set, `git push` → CI builds the image → SSHes the host → `deploy.sh`.
The forced-command key means a leaked secret can at most trigger a deploy of the
current `master`, not get a shell.

## Backups

**Automatic backups are off.** This is a portfolio project — losing the SQLite
file costs a re-register, not a business. Nothing runs on cron; take a snapshot
by hand when you actually care:

```bash
scripts/backup.sh                 # one-off snapshot into ./backups/ (host-local)
```

> **Never push a snapshot to this repo.** The repo is **public** and the dump
> contains user emails + bcrypt password hashes. An earlier `backup-offsite.sh`
> force-pushed snapshots to an orphan `backups` branch (that script is removed
> and the branch deleted). If you ever want offsite copies, use a **private**
> bucket (S3/R2) or a private repo — and encrypt the dump (`age`/`gpg`) first.

### Restore

From a local snapshot:

```bash
scripts/restore.sh backups/app-YYYYMMDD-HHMMSS.db
```

It stops the app, replaces the DB on the volume (clearing stale WAL sidecars),
and restarts. Re-seeds content automatically; user state comes from the snapshot.

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
