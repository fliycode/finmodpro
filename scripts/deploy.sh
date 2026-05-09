#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/finmodpro"
COMPOSE_FILE="docker-compose.prod.yml"
LAST_DEPLOY_FILE=".last_deployed_commit"
DOCKER_PRUNE_UNTIL="${DEPLOY_DOCKER_PRUNE_UNTIL:-24h}"
MIN_FREE_DISK_MB="${DEPLOY_MIN_FREE_DISK_MB:-4096}"
REBUILD_LLAMAINDEX_INDEX_ON_DEPLOY="${REBUILD_LLAMAINDEX_INDEX_ON_DEPLOY:-true}"

cd "$APP_DIR"

load_env_files() {
  for env_file in .env .env.backend .env.frontend .env.deploy; do
    if [ -f "$env_file" ]; then
      set -a
      # shellcheck disable=SC1090
      . "$env_file"
      set +a
    fi
  done
}

require_non_empty_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Deploy aborted: required environment variable $name is not set. Define it in .env, .env.backend, .env.frontend, or .env.deploy, or export it before running deploy.sh." >&2
    exit 1
  fi
}

require_not_placeholder_env() {
  local name="$1"
  local placeholder="$2"
  if [ "${!name:-}" = "$placeholder" ]; then
    echo "Deploy aborted: environment variable $name is still using the placeholder value '$placeholder'." >&2
    exit 1
  fi
}

validate_runtime_env() {
  require_non_empty_env DJANGO_SECRET_KEY
  require_not_placeholder_env DJANGO_SECRET_KEY "change-me-in-.env.backend"
  require_non_empty_env JWT_SECRET_KEY
  require_not_placeholder_env JWT_SECRET_KEY "change-me-jwt-in-.env.backend"
  require_non_empty_env DEEPSEEK_API_KEY
  require_non_empty_env DASHSCOPE_API_KEY
}

free_disk_mb() {
  df -Pm "$APP_DIR" | awk 'NR==2 {print $4}'
}

prune_recent_deploy_leftovers() {
  echo "Pruning dangling Docker build cache from recent deploys..."
  docker builder prune -f
  echo "Pruning dangling Docker images from recent deploys..."
  docker image prune -f
}

prune_docker_artifacts() {
  echo "Pruning unused Docker build cache older than ${DOCKER_PRUNE_UNTIL}..."
  docker builder prune -af --filter "until=${DOCKER_PRUNE_UNTIL}"
  echo "Pruning unused Docker images older than ${DOCKER_PRUNE_UNTIL}..."
  docker image prune -af --filter "until=${DOCKER_PRUNE_UNTIL}"
}

ensure_disk_headroom() {
  local available_mb
  available_mb="$(free_disk_mb)"

  if [ "$available_mb" -ge "$MIN_FREE_DISK_MB" ]; then
    return
  fi

  echo "Only ${available_mb}MB free on disk; pruning Docker artifacts before deploy..."
  prune_docker_artifacts

  available_mb="$(free_disk_mb)"
  if [ "$available_mb" -lt "$MIN_FREE_DISK_MB" ]; then
    echo "Deploy aborted: only ${available_mb}MB free after cleanup; require at least ${MIN_FREE_DISK_MB}MB." >&2
    exit 1
  fi
}

load_env_files
validate_runtime_env

printf '%s\n' "$(git rev-parse HEAD)" > "$LAST_DEPLOY_FILE"

git fetch --all --prune
git checkout main
git pull --ff-only origin main

ensure_disk_headroom
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans
docker compose -f "$COMPOSE_FILE" exec -T backend python3 manage.py migrate
if [ "$REBUILD_LLAMAINDEX_INDEX_ON_DEPLOY" = "true" ]; then
  docker compose -f "$COMPOSE_FILE" exec -T backend python3 manage.py rebuild_llamaindex_index
fi

"$APP_DIR/scripts/smoke-check.sh"
prune_recent_deploy_leftovers
prune_docker_artifacts

echo "Deploy completed at commit $(git rev-parse HEAD)"
echo "Previous commit recorded in $APP_DIR/$LAST_DEPLOY_FILE"
