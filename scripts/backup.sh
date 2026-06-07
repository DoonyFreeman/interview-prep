#!/usr/bin/env bash
#
# Online backup of the app's SQLite database from the running container.
#
# Uses SQLite's online backup API (via the app image's stdlib `sqlite3`), which
# produces a consistent snapshot even with WAL mode and concurrent writes — much
# safer than copying app.db while the app is running. The snapshot is pulled to
# ./backups/ on the host, and old snapshots are pruned.
#
# Usage:   scripts/backup.sh
# Cron:    0 3 * * *  cd /opt/interview-prep && scripts/backup.sh >> backups/backup.log 2>&1
#
# Env overrides:
#   SERVICE   compose service name           (default: app)
#   KEEP      number of snapshots to retain  (default: 14)
#   OUT_DIR   host output directory          (default: ./backups)
set -euo pipefail

cd "$(dirname "$0")/.."

SERVICE="${SERVICE:-app}"
KEEP="${KEEP:-14}"
OUT_DIR="${OUT_DIR:-./backups}"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="${OUT_DIR}/app-${TS}.db"

# Pick the compose command (plugin vs legacy binary).
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi

mkdir -p "$OUT_DIR"

echo "[backup] online snapshot from service '${SERVICE}'..."
# Run inside the container: write a consistent copy to /tmp, then stream it out.
$COMPOSE exec -T "$SERVICE" python -c "
import sqlite3
src = sqlite3.connect('data/app.db')
dst = sqlite3.connect('/tmp/backup.db')
with dst:
    src.backup(dst)
dst.close(); src.close()
"
$COMPOSE cp "${SERVICE}:/tmp/backup.db" "$DEST"
$COMPOSE exec -T "$SERVICE" rm -f /tmp/backup.db

echo "[backup] wrote ${DEST} ($(du -h "$DEST" | cut -f1))"

# Prune: keep the newest $KEEP snapshots. (Portable to bash 3.2 — no mapfile.)
pruned=0
while IFS= read -r old; do
  [ -n "$old" ] || continue
  rm -f "$old"
  pruned=$((pruned + 1))
done < <(ls -1t "${OUT_DIR}"/app-*.db 2>/dev/null | tail -n "+$((KEEP + 1))")
[ "$pruned" -gt 0 ] && echo "[backup] pruned ${pruned} old snapshot(s)"

echo "[backup] done. Restore with: scripts/restore.sh ${DEST}  (see DEPLOY.md)"
