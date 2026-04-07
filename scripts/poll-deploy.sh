#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/finmodpro"
STATE_DIR="$APP_DIR/.deploy-state"
LOCK_DIR="$STATE_DIR/poll.lock"
LAST_SUCCESS_FILE="$STATE_DIR/last_successful_deploy_commit"
BRANCH="main"
REMOTE="origin"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$STATE_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "another deployment poll is already running; exiting"
  exit 0
fi

cd "$APP_DIR"

git fetch "$REMOTE" "$BRANCH" --prune
REMOTE_HEAD="$(git rev-parse "$REMOTE/$BRANCH")"
log "remote $REMOTE/$BRANCH: $REMOTE_HEAD"

LAST_SUCCESS=""
if [ -f "$LAST_SUCCESS_FILE" ]; then
  LAST_SUCCESS="$(<"$LAST_SUCCESS_FILE")"
fi
log "last successful deploy: ${LAST_SUCCESS:-<none>}"

if [ "$REMOTE_HEAD" = "$LAST_SUCCESS" ]; then
  log "no new commit to deploy"
  exit 0
fi

log "starting deployment"
"$APP_DIR/scripts/deploy.sh"

DEPLOYED_HEAD="$(git rev-parse HEAD)"
log "deployed HEAD: $DEPLOYED_HEAD"

printf '%s\n' "$DEPLOYED_HEAD" > "$LAST_SUCCESS_FILE"
log "deployment succeeded for commit $DEPLOYED_HEAD"
