#!/usr/bin/env bash
set -euo pipefail

BACKEND_HEALTH_URL="http://127.0.0.1:8000/api/health/"
FRONTEND_URL="http://127.0.0.1:5173/"
MAX_ATTEMPTS="${SMOKE_CHECK_ATTEMPTS:-20}"
SLEEP_SECONDS="${SMOKE_CHECK_SLEEP_SECONDS:-3}"

check_url() {
  local url="$1"
  local name="$2"
  local attempt status

  for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    status="$(curl -sS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [ "$status" = "200" ]; then
      echo "$name check passed: $url"
      return 0
    fi

    echo "$name check attempt $attempt/$MAX_ATTEMPTS failed with status ${status:-n/a}: $url" >&2
    sleep "$SLEEP_SECONDS"
  done

  echo "$name check failed after $MAX_ATTEMPTS attempts: $url" >&2
  return 1
}

check_url "$BACKEND_HEALTH_URL" "backend health"
check_url "$FRONTEND_URL" "frontend root"
