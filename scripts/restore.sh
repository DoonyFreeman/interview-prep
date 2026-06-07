#!/usr/bin/env bash
#
# Restore the app's SQLite database from a snapshot produced by backup.sh.
#
# Stops the app, replaces the database on the named volume (clearing any stale
# WAL sidecars), then restarts it. The app re-seeds content on startup; only
# user state (accounts, attempts, progress) comes from the snapshot.
#
# Usage:   scripts/restore.sh backups/app-YYYYMMDD-HHMMSS.db
set -euo pipefail

cd "$(dirname "$0")/.."

SNAP="${1:?usage: scripts/restore.sh <path-to-snapshot.db>}"
[ -f "$SNAP" ] || { echo "restore: no such file: $SNAP" >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi

# Compose prefixes volume names with the project (dir) name: <project>_app-data.
PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$(pwd)")}"
VOLUME="${PROJECT}_app-data"

echo "restore: stopping app..."
$COMPOSE stop app

echo "restore: writing snapshot into volume '${VOLUME}'..."
docker run --rm \
  -v "${VOLUME}:/data" \
  -v "$(cd "$(dirname "$SNAP")" && pwd):/snap:ro" \
  alpine sh -c "rm -f /data/app.db /data/app.db-wal /data/app.db-shm && \
                cp /snap/$(basename "$SNAP") /data/app.db"

echo "restore: starting app..."
$COMPOSE up -d app
echo "restore: done."
