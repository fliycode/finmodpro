#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/finmodpro"
COMPOSE_FILE="docker-compose.prod.yml"
LAST_DEPLOY_FILE=".last_deployed_commit"
DOCKER_PRUNE_UNTIL="${DEPLOY_DOCKER_PRUNE_UNTIL:-24h}"
MIN_FREE_DISK_MB="${DEPLOY_MIN_FREE_DISK_MB:-4096}"

cd "$APP_DIR"

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

for env_file in .env.backend .env.frontend .env.deploy; do
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$env_file"
    set +a
  fi
done

printf '%s\n' "$(git rev-parse HEAD)" > "$LAST_DEPLOY_FILE"

git fetch --all --prune
git checkout main
git pull --ff-only origin main

python3 "$APP_DIR/scripts/render_litellm_config.py"

ensure_disk_headroom
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py migrate
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py sync_litellm_routes
docker compose -f "$COMPOSE_FILE" up -d --force-recreate litellm

"$APP_DIR/scripts/smoke-check.sh"
prune_recent_deploy_leftovers
prune_docker_artifacts

echo "Deploy completed at commit $(git rev-parse HEAD)"
echo "Previous commit recorded in $APP_DIR/$LAST_DEPLOY_FILE"
