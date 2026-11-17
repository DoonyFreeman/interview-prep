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

# Serialize deployments on the Linux production host, including rollback.
if command -v flock >/dev/null 2>&1; then
  exec 9<.
  flock -x 9
fi

IMAGE_REPOSITORY="ghcr.io/doonyfreeman/interview-prep"
revision=""
digest=""
pin_pattern='^([0-9a-f]{40}) (sha256:[0-9a-f]{64})$'
ssh_prefix='cd /opt/interview-prep && ./scripts/deploy.sh'
if [[ -n "${SSH_ORIGINAL_COMMAND:-}" ]]; then
  if [[ "$SSH_ORIGINAL_COMMAND" != "$ssh_prefix" ]]; then
    if [[ "$SSH_ORIGINAL_COMMAND" != "$ssh_prefix "* || ! "${SSH_ORIGINAL_COMMAND#"$ssh_prefix "}" =~ $pin_pattern ]]; then
      echo "[deploy] ERROR: invalid pinned SSH deployment command" >&2
      exit 1
    fi
    revision="${BASH_REMATCH[1]}"
    digest="${BASH_REMATCH[2]}"
  fi
elif [[ $# -gt 0 ]]; then
  if [[ $# -ne 2 || ! "$*" =~ $pin_pattern ]]; then
    echo "[deploy] ERROR: expected a commit revision and image digest" >&2
    exit 1
  fi
  revision="${BASH_REMATCH[1]}"
  digest="${BASH_REMATCH[2]}"
fi
if [[ -n "$digest" ]]; then
  export IPREP_APP_IMAGE="${IMAGE_REPOSITORY}@${digest}"
fi
IMAGE="${IPREP_APP_IMAGE:-${IMAGE_REPOSITORY}:latest}"

setup_compose() {
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
  if [[ -f .assistant/current/app.env ]]; then
    COMPOSE+=(-f docker-compose.assistant.yml)
  fi
}

assistant_generation=""
on_deploy_exit() {
  local status=$?
  if [[ "$status" -ne 0 && -n "$assistant_generation" ]]; then
    if python3 scripts/assistant_provision.py rollback "$assistant_generation" >/dev/null 2>&1; then
      setup_compose
      if "${COMPOSE[@]}" up -d --no-build --force-recreate app >/dev/null 2>&1; then
        echo "[deploy] Previous assistant configuration restored and app recreated" >&2
      else
        echo "[deploy] ERROR: previous assistant configuration restored but app recreation failed" >&2
      fi
    else
      echo "[deploy] ERROR: could not roll back assistant configuration" >&2
    fi
  fi
  exit "$status"
}
trap on_deploy_exit EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

assistant_smoke() {
  local status=0
  "${COMPOSE[@]}" exec -T app python - >/dev/null 2>&1 <<'PYTHON' || status=$?
import asyncio

from app.assistant.provider import AssistantModelError
from app.assistant.runtime import AssistantRuntime, AssistantUnavailable
from app.config import get_settings


async def ignore_event(_event, _data):
    pass


async def check_answer():
    settings = get_settings()
    if not settings.assistant_enabled:
        return 10
    runtime = AssistantRuntime(settings)
    answer, metadata = await asyncio.wait_for(
        runtime.answer(
            [{"role": "user", "content": "Как multi-stage сборка уменьшает размер Docker-образа?"}],
            course_slug="docker", lesson_slug="compose-best-practices",
            owner_id=0, session=None, use_web=False, on_event=ignore_event,
        ),
        timeout=90,
    )
    cited_lesson = any(
        source.kind == "lesson" and source.url.startswith("/courses/docker/lessons/compose-best-practices#")
        for source in metadata.sources
    )
    return 0 if answer.strip() and cited_lesson else 11


try:
    raise SystemExit(asyncio.run(check_answer()))
except AssistantUnavailable as exc:
    cause = exc.__cause__
    if not isinstance(cause, AssistantModelError):
        raise SystemExit(12) from None
    message = str(cause)
    if message in {
        "GigaChat could not load CA certificates. Check GIGACHAT_CA_FILE or SSL_CERT_FILE",
        "GigaChat OAuth TLS certificate verification failed. Check GIGACHAT_CA_FILE",
        "GigaChat API TLS certificate verification failed. Check GIGACHAT_CA_FILE",
    }:
        raise SystemExit(14) from None
    if message in {
        f"GigaChat {stage} failed (HTTP {status})"
        for stage in ("authorization", "completion")
        for status in (401, 403)
    }:
        raise SystemExit(15) from None
    raise SystemExit(16) from None
except TimeoutError:
    raise SystemExit(13) from None
PYTHON
  case "$status" in
    0)  ;;
    10) echo "[deploy] ERROR: assistant smoke feature disabled" >&2 ;;
    11) echo "[deploy] ERROR: assistant smoke missing answer or lesson citation" >&2 ;;
    12) echo "[deploy] ERROR: assistant smoke runtime unavailable" >&2 ;;
    13) echo "[deploy] ERROR: assistant smoke timed out" >&2 ;;
    14) echo "[deploy] ERROR: assistant smoke provider TLS or CA verification failed" >&2 ;;
    15) echo "[deploy] ERROR: assistant smoke provider authentication rejected" >&2 ;;
    16) echo "[deploy] ERROR: assistant smoke provider request failed" >&2 ;;
    *)  echo "[deploy] ERROR: assistant smoke execution failed" >&2 ;;
  esac
  return "$status"
}

echo "[deploy] 1/5 backup database"
./scripts/backup.sh </dev/null || echo "[deploy] WARN: backup failed, continuing"

echo "[deploy] 2/5 git pull (compose / Caddyfile / scripts)"
git pull --ff-only </dev/null

if [[ -n "$revision" && "$(git rev-parse HEAD </dev/null)" != "$revision" ]]; then
  echo "[deploy] ERROR: server revision differs from the CI build" >&2
  exit 1
fi
if [[ -z "$revision" ]]; then
  if [[ -f .assistant/current/app.env ]]; then
    echo "[deploy] ERROR: saved assistant configuration requires a pinned deployment" >&2
    exit 1
  fi
  if [[ ! -t 0 ]]; then
    python3 scripts/assistant_provision.py check-empty
  fi
fi

setup_compose
echo "[deploy] 3/5 pull image: ${IMAGE}"
"${COMPOSE[@]}" pull app </dev/null
if [[ -n "$revision" ]]; then
  image_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$IMAGE" </dev/null)"
  if [[ "$image_revision" != "$revision" ]]; then
    echo "[deploy] ERROR: pulled image revision differs from the CI build" >&2
    exit 1
  fi
fi

if [[ -n "$revision" && ! -t 0 ]]; then
  assistant_generation="$(python3 scripts/assistant_provision.py prepare)"
  setup_compose
fi
if [[ -z "$assistant_generation" && -f .assistant/current/previous ]]; then
  echo "[deploy] ERROR: an assistant configuration update is still pending" >&2
  exit 1
fi

echo "[deploy] 4/5 recreate app (no build)"
UP=(up -d --no-build)
if [[ -n "$assistant_generation" ]]; then
  UP+=(--force-recreate)
fi
"${COMPOSE[@]}" "${UP[@]}" app
echo "[deploy] 5/5 health check"
for _ in $(seq 1 20); do
  st="$(docker inspect -f '{{.State.Health.Status}}' interview-prep 2>/dev/null || echo '')"
  echo "  health: ${st:-unknown}"
  if [ "$st" = "healthy" ]; then
    if [[ -n "$assistant_generation" ]]; then
      assistant_smoke
      python3 scripts/assistant_provision.py commit "$assistant_generation"
      assistant_generation=""
      echo "[deploy] assistant smoke: enabled, answered, cited lesson"
    fi
    echo "[deploy] OK — live on the new image"
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 3
done

echo "[deploy] ERROR: app did not become healthy."
echo "[deploy] Inspect: ${COMPOSE[*]} logs --tail=50 app"
echo "[deploy] Roll back: edit image tag to a previous :<sha> in docker-compose.yml and re-run, or:"
echo "         ${COMPOSE[*]} pull app && ${COMPOSE[*]} up -d --no-build app"
exit 1
