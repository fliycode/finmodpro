#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/finmodpro"
COMPOSE_FILE="docker-compose.prod.yml"
LAST_DEPLOY_FILE=".last_deployed_commit"

cd "$APP_DIR"

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

docker compose -f "$COMPOSE_FILE" up -d --build

"$APP_DIR/scripts/smoke-check.sh"

echo "Deploy completed at commit $(git rev-parse HEAD)"
echo "Previous commit recorded in $APP_DIR/$LAST_DEPLOY_FILE"
