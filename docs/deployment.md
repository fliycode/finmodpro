# FinModPro Deployment Guide

## Deployment Contract

- Deploy path: `/opt/finmodpro`
- Deploy branch: `main`
- Frontend public port: `80`
- Backend public port: `8000`
- Backend health check: `http://127.0.0.1:8000/api/health/`
- Compose entrypoint: `/opt/finmodpro/docker-compose.prod.yml`
- Server-side deploy script: `/opt/finmodpro/scripts/deploy.sh`
- Server-side smoke check script: `/opt/finmodpro/scripts/smoke-check.sh`

This first version uses Docker Compose directly on the target server. Production secrets stay in GitHub Secrets or server-managed env files and must not be committed into the repository.

## GitHub Secrets

The workflow only requires these repository secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`

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

## First Deploy Preconditions

Before the first GitHub Actions deploy, confirm the target host has:

- `git`
- `docker`
- `docker compose` plugin
- a clone of this repository at `/opt/finmodpro`
- permission to pull the repository
- the server-side env files listed above
- ports `80` and `8000` available

## Local Validation Boundary

The minimum local validation for this first version is:

```bash
docker compose -f docker-compose.prod.yml config
```

This validates Compose syntax and variable interpolation only. It does not prove a live deployment can:

- pull code from GitHub on the target host
- start the full stack successfully
- pass smoke checks under production network conditions
- satisfy MySQL / Redis / Milvus / Ollama runtime requirements

## Script Source And Execution

The first deployment requires a manual clone into `/opt/finmodpro`. After that, the GitHub Actions workflow SSHes to the server and executes:

```bash
/opt/finmodpro/scripts/deploy.sh
```

The latest repo version of `scripts/deploy.sh` becomes the source of truth after each `git pull`.

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
- `http://127.0.0.1:80/`

It retries and exits non-zero if either endpoint never returns `200`.

## GitHub Actions Workflow

`.github/workflows/ci-cd.yml` runs:

- backend `python manage.py check`
- backend `python manage.py test`
- frontend `npm run build`
- deploy over SSH after a successful `push` to `main`

Failure visibility is separated by stage:

- backend checks
- frontend build
- SSH connection / remote deploy
- smoke check

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
