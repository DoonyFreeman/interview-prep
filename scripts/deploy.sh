#!/usr/bin/env bash
#
# Production deploy: pull the prebuilt GHCR image and recreate the app.
#
# Designed for a small host: it NEVER builds on the box (a Vite build OOMs it)
# and NEVER touches the SQLite data volume (user progress). Backs up the DB
# first, then swaps the running image for the freshly-pulled one.
#
# Usage (on the server, inside /opt/interview-prep):
#   ./scripts/deploy.sh
# Also invoked by CI (.github/workflows/build.yml) over SSH when CD is enabled.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="ghcr.io/doonyfreeman/interview-prep:latest"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "[deploy] 1/5 backup database"
./scripts/backup.sh || echo "[deploy] WARN: backup failed, continuing"

echo "[deploy] 2/5 git pull (compose / Caddyfile / scripts)"
git pull --ff-only

echo "[deploy] 3/5 pull image: ${IMAGE}"
$COMPOSE pull app

echo "[deploy] 4/5 recreate app (no build)"
$COMPOSE up -d --no-build app

echo "[deploy] 5/5 health check"
for _ in $(seq 1 20); do
  st="$(docker inspect -f '{{.State.Health.Status}}' interview-prep 2>/dev/null || echo '')"
  echo "  health: ${st:-unknown}"
  if [ "$st" = "healthy" ]; then
    echo "[deploy] OK — live on the new image"
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 3
done

echo "[deploy] ERROR: app did not become healthy."
echo "[deploy] Inspect: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 app"
echo "[deploy] Roll back: edit image tag to a previous :<sha> in docker-compose.yml and re-run, or:"
echo "         $COMPOSE pull app && $COMPOSE up -d --no-build app"
exit 1
