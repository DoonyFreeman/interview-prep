#!/usr/bin/env bash
#
# Offsite copy of the app's SQLite backups.
#
# Pushes the newest N local snapshots (produced by backup.sh) to an *orphan*
# branch of the GitHub repo, as a single force-pushed commit. Because the branch
# is rebuilt from scratch every run, its git history never grows — only the
# latest commit (with the newest N snapshots) is reachable, so binary blobs don't
# pile up in the repo over time. This is the offsite half of the backup story:
# even if the server is wiped, the snapshots live in the repo.
#
# Run AFTER backup.sh (which creates + prunes ./backups). Cron:
#   0 3 * * *  cd /opt/interview-prep && scripts/backup.sh && scripts/backup-offsite.sh >> backups/backup.log 2>&1
#
# Requires PUSH (write) access from this host to the repo — a GitHub deploy key
# with write access, or a PAT in the remote URL / a git credential helper.
#
# Env overrides:
#   KEEP_OFFSITE  snapshots to keep in the branch   (default: 7)
#   OUT_DIR       host backups dir                  (default: ./backups)
#   BRANCH        orphan branch name                (default: backups)
#   REMOTE        git remote URL                    (default: origin's URL)
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

KEEP_OFFSITE="${KEEP_OFFSITE:-7}"
OUT_DIR="${OUT_DIR:-./backups}"
BRANCH="${BRANCH:-backups}"
REMOTE="${REMOTE:-$(git -C "$REPO_ROOT" remote get-url origin)}"

# Collect the newest N snapshots. backup.sh names them app-YYYYMMDD-HHMMSS.db, so
# a lexical sort is chronological. (Portable to bash 3.2 — no mapfile.)
snaps=()
while IFS= read -r f; do
  [ -n "$f" ] && snaps+=("$f")
done < <(ls -1 "${OUT_DIR}"/app-*.db 2>/dev/null | sort | tail -n "$KEEP_OFFSITE")

if [ "${#snaps[@]}" -eq 0 ]; then
  echo "[offsite] no snapshots in ${OUT_DIR} (run backup.sh first)" >&2
  exit 1
fi

# Fail early with a clear message if we can't reach the remote (no push access is
# the common cause — read-only deploy key, missing PAT, etc.).
if ! git ls-remote "$REMOTE" >/dev/null 2>&1; then
  echo "[offsite] cannot reach remote '${REMOTE}' — check push access (deploy key/PAT)" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "[offsite] staging ${#snaps[@]} snapshot(s)..."
for f in "${snaps[@]}"; do
  cp "$f" "$TMP/"
done

cat > "$TMP/README.md" <<EOF
# Database backups (offsite)

Automated offsite copies of the interview-prep SQLite database, pushed daily by
\`scripts/backup-offsite.sh\`. This is an **orphan branch**, force-pushed every
run — it holds only the newest ${KEEP_OFFSITE} snapshots and has no history.

Restore the newest snapshot onto a fresh/wiped server with:

    scripts/restore-offsite.sh

Updated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

# Build the orphan commit in the temp dir and force-push it as the whole branch.
git -C "$TMP" init -q
git -C "$TMP" checkout -q -b "$BRANCH"
git -C "$TMP" add -A
git -C "$TMP" -c user.name="backup-bot" -c user.email="backup-bot@localhost" \
  commit -q -m "backup $(date -u +%Y%m%d-%H%M%S) (${#snaps[@]} snapshots)"

echo "[offsite] force-pushing to '${BRANCH}'..."
git -C "$TMP" push --force "$REMOTE" "HEAD:${BRANCH}"

echo "[offsite] done. Branch '${BRANCH}' now holds ${#snaps[@]} snapshot(s)."
