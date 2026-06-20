#!/usr/bin/env bash
#
# Restore the app's database from the OFFSITE backup branch.
#
# For a fresh or wiped server where ./backups is empty: fetch the newest snapshot
# from the orphan 'backups' branch and hand it to scripts/restore.sh (which stops
# the app, swaps the DB onto the volume, clears WAL sidecars, and restarts).
#
# Usage:   scripts/restore-offsite.sh
#
# Env overrides:
#   BRANCH   orphan branch name   (default: backups)
#   REMOTE   git remote URL       (default: origin's URL)
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

BRANCH="${BRANCH:-backups}"
REMOTE="${REMOTE:-$(git -C "$REPO_ROOT" remote get-url origin)}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "[offsite-restore] fetching '${BRANCH}' from ${REMOTE}..."
git -C "$TMP" init -q
git -C "$TMP" fetch -q --depth 1 "$REMOTE" "$BRANCH"
git -C "$TMP" checkout -q FETCH_HEAD

# Newest snapshot (app-YYYYMMDD-HHMMSS.db sorts chronologically).
newest="$(ls -1 "$TMP"/app-*.db 2>/dev/null | sort | tail -n 1 || true)"
if [ -z "$newest" ]; then
  echo "[offsite-restore] no app-*.db found on branch '${BRANCH}'" >&2
  exit 1
fi

echo "[offsite-restore] newest snapshot: $(basename "$newest")"
exec "$REPO_ROOT/scripts/restore.sh" "$newest"
