# FinModPro Deployment Guide

## Deployment Contract

- Deploy path: `/opt/finmodpro`
- Deploy branch: `main`
- Repo host: GitHub (`https://github.com/fliycode/finmodpro.git`)
- Frontend public port: `5173`
- Backend public port: `8000`
- Backend health check: `http://127.0.0.1:8000/api/health/`
- Compose entrypoint: `/opt/finmodpro/docker-compose.prod.yml`
- Server-side deploy script: `/opt/finmodpro/scripts/deploy.sh`
- Polling script: `/opt/finmodpro/scripts/poll-deploy.sh`
- Server-side smoke check script: `/opt/finmodpro/scripts/smoke-check.sh`
- systemd service: `/etc/systemd/system/finmodpro-poll-deploy.service`
- systemd timer: `/etc/systemd/system/finmodpro-poll-deploy.timer`

Deployment is server-driven and executed directly on the current server. GitHub remains the source-of-truth repo host, but the deploy path is `server pull main -> run deploy.sh`, not a GitHub Actions workflow.

## Server-side Environment Files

Prepare these files on the server before the first live deploy:

- `/opt/finmodpro/.env.backend`
- `/opt/finmodpro/.env.frontend`
- optional `/opt/finmodpro/.env.deploy`

Recommended split:

- `.env.backend`: Django, DB, Redis, Celery, Milvus, JWT, media settings
- `.env.frontend`: `VITE_API_BASE_URL`
- `.env.deploy`: optional deploy-time overrides only

These files are sourced by `scripts/deploy.sh` before `docker compose -f docker-compose.prod.yml up -d --build`.

For the current public deployment entrypoint at `http://47.85.103.76:5173`, `.env.backend` must allow that host and origin:

- `DJANGO_ALLOWED_HOSTS=47.85.103.76,127.0.0.1,localhost`
- `DJANGO_CSRF_TRUSTED_ORIGINS=http://47.85.103.76:5173,http://127.0.0.1:5173,http://localhost:5173`
- `DJANGO_CORS_ALLOWED_ORIGINS=http://47.85.103.76:5173,http://127.0.0.1:5173,http://localhost:5173`

If these values only contain localhost, Django will reject proxied requests with an HTML `400 Bad Request` before `login/register` reaches the auth controller.

## First Deploy Preconditions

Before the first live deploy, confirm the target host has:

- `git`
- `docker`
- `docker compose` plugin
- a clone of this repository at `/opt/finmodpro`
- permission to pull the repository
- the server-side env files listed above
- ports `5173` and `8000` available

## Polling Auto-Deploy

The host-local polling loop is an optional auto-deploy entrypoint:

```bash
/opt/finmodpro/scripts/poll-deploy.sh
```

It does the following:

1. `cd /opt/finmodpro`
2. `git fetch origin main --prune`
3. read `/opt/finmodpro/.deploy-state/last_successful_deploy_commit` if it exists
4. compare `origin/main` to the last successful deployed SHA
5. if unchanged, exit cleanly with `no new commit to deploy`
6. if changed, run `/opt/finmodpro/scripts/deploy.sh`
7. only after a successful deploy, write the deployed SHA to `/opt/finmodpro/.deploy-state/last_successful_deploy_commit`

Failed deploys do not advance the success marker.

## systemd Timer

Install these units on the host:

- `/etc/systemd/system/finmodpro-poll-deploy.service`
- `/etc/systemd/system/finmodpro-poll-deploy.timer`

Recommended cadence: once per minute when you want automatic polling deploys enabled.

After writing or updating the unit files:

```bash
systemctl daemon-reload
systemctl enable --now finmodpro-poll-deploy.timer
```

## Deploy Script Behavior

`/opt/finmodpro/scripts/deploy.sh` does the following:

1. `cd /opt/finmodpro`
2. records the current commit into `/opt/finmodpro/.last_deployed_commit`
3. runs `git fetch --all --prune`
4. runs `git checkout main`
5. runs `git pull --ff-only origin main`
6. runs `docker compose -f docker-compose.prod.yml up -d --build`
7. executes `/opt/finmodpro/scripts/smoke-check.sh`

The script exits non-zero on any failure.

## Smoke Check Behavior

`/opt/finmodpro/scripts/smoke-check.sh` checks:

- `http://127.0.0.1:8000/api/health/`
- `http://127.0.0.1:5173/`

It retries and exits non-zero if either endpoint never returns `200`.

## Manual Operations

Direct deploy on the current server:

```bash
cd /opt/finmodpro
./scripts/deploy.sh
```

Manual poll run:

```bash
/opt/finmodpro/scripts/poll-deploy.sh
```

## Rollback Baseline

Each deploy writes the previous revision into:

```text
/opt/finmodpro/.last_deployed_commit
```

Manual rollback baseline command:

```bash
cd /opt/finmodpro
git checkout "$(cat .last_deployed_commit)"
docker compose -f docker-compose.prod.yml up -d --build
```

This restores application code and containers only. It does not automatically roll back database state.
