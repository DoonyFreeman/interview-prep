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

`scripts/backup.sh` takes a consistent online SQLite snapshot from the running
container into `./backups/` and prunes old ones (keeps 14 by default).

```bash
scripts/backup.sh                 # one-off
# Cron (daily 03:00):
0 3 * * * cd /opt/interview-prep && scripts/backup.sh >> backups/backup.log 2>&1
```

### Offsite copy (survive host loss)

Local snapshots live on the same server — if it's wiped (e.g. the host is
deleted), they're gone too. `scripts/backup-offsite.sh` pushes the newest 7
snapshots to an **orphan `backups` branch** of this private repo, as a single
force-pushed commit so the branch never accumulates git history (binary blobs
don't pile up — the old commit becomes unreachable and is GC'd).

```bash
scripts/backup-offsite.sh         # one-off (run after backup.sh)
# Cron (daily 03:00) — chain both:
0 3 * * * cd /opt/interview-prep && scripts/backup.sh && scripts/backup-offsite.sh >> backups/backup.log 2>&1
```

**Prerequisite — push (write) access from the server to the repo.** The script
`git push`es to `origin`, so the host needs write credentials, one of:

- a **GitHub deploy key with "Allow write access"** on this repo, added to the
  server's SSH agent / `~/.ssh` (origin stays the SSH URL); or
- a **fine-grained PAT** (Contents: read+write, this repo only) baked into an
  HTTPS remote or a git credential helper.

The script fails early with a clear message if the remote is unreachable.
Tunables via env: `KEEP_OFFSITE` (7), `BRANCH` (`backups`), `REMOTE`, `OUT_DIR`.

> The dump is **unencrypted** — it contains user emails + bcrypt hashes. This is
> acceptable only because the repo is private. Keep it private.

### Restore

From a local snapshot:

```bash
scripts/restore.sh backups/app-YYYYMMDD-HHMMSS.db
```

On a fresh/wiped server (no local snapshots) — pull the newest from the offsite
branch and restore it in one step:

```bash
scripts/restore-offsite.sh
```

Both stop the app, replace the DB on the volume (clearing stale WAL sidecars),
and restart. Re-seeds content automatically; user state comes from the snapshot.

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
