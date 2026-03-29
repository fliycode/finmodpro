# FinModPro CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-pass CI/CD pipeline for FinModPro using GitHub Actions for test/build validation and Docker Compose deployment to the current server over SSH.

**Architecture:** GitHub Actions runs backend tests and frontend build checks on every push to `main`. When checks pass, the workflow SSHes into the production server, updates the checked-out repository in `/opt/finmodpro`, and runs `docker compose -f docker-compose.prod.yml up -d --build` followed by smoke checks. First version uses frontend-on-port-80 and backend-on-port-8000 directly, with no extra gateway container.

**Tech Stack:** GitHub Actions, Docker, Docker Compose, Django, Vite, Nginx, SSH, MySQL, Redis, Milvus, Ollama

---

## File Map

### New files expected
- `.github/workflows/ci-cd.yml` — unified CI/CD workflow for backend test, frontend build, and production deploy
- `docker-compose.prod.yml` — production container orchestration
- `backend/Dockerfile` — backend production image
- `frontend/Dockerfile` — frontend production image
- `frontend/nginx.conf` — frontend static hosting + SPA fallback config
- `scripts/deploy.sh` — server-side deployment entrypoint
- `scripts/smoke-check.sh` — post-deploy health checks
- `docs/deployment.md` — production deployment and rollback notes

### Existing files likely to change
- `backend/.env.example` — production-oriented variable notes if missing
- `frontend/.env.example` — production API base URL guidance
- `backend/README.md` — container / deployment references
- `README.md` — add deployment doc links
- `frontend/src/api/config.js` — remove unsafe localhost production fallback and keep build-time `VITE_API_BASE_URL`
- `frontend/vite.config.js` — verify build output works with SPA fallback assumptions
- `backend/config/settings.py` — only minimal env-driven startup fixes required for container boot

---

## Assumptions Locked For This Plan

- Production deployment directory: `/opt/finmodpro`
- Branch to deploy: `main`
- First version deploys directly on the current server, not via image registry
- GitHub Secrets hold only SSH connection info; app env files stay on the server
- First version targets a single production environment only
- Public entry points are:
  - frontend: `http://127.0.0.1/`
  - backend health: `http://127.0.0.1:8000/api/health/`
- Frontend production API config uses **build-time env** via `VITE_API_BASE_URL`; no runtime template injection in this version
- CI uses repo-friendly checks only: backend `manage.py check` + tests that run under current local defaults, plus frontend build

If any assumption changes, update the design doc and regenerate this plan before implementation.

---

## Ownership Rules

- **Dora** owns final scope, deployment contract, and `docs/deployment.md` final merge outcome.
- **Codex** owns backend containerization, compose, deploy scripts, and GitHub Actions deployment wiring.
- **Gemini** owns frontend containerization, Nginx static hosting config, and production frontend config alignment.
- If multiple tasks touch `docs/deployment.md`, each worker may append/update their section, but **Dora performs final consolidation before completion claim**.

---

### Task 1: Establish deployment contract and preflight checklist

**Owner:** Dora  
**Files:**
- Create: `docs/deployment.md`
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `backend/.env.example`
- Modify: `frontend/.env.example`

- [ ] **Step 1: Write the deployment contract section in `docs/deployment.md`**

Include:
- deployment target = current server
- deploy path = `/opt/finmodpro`
- branch = `main`
- public ports = frontend `80`, backend `8000`
- required GitHub Secrets = `DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
- required server-side env files

- [ ] **Step 2: Add first-live-deploy preflight checklist**

Document these must exist before first deployment:
- Git installed
- Docker installed
- Docker Compose plugin installed
- repo clone exists at `/opt/finmodpro`
- server can pull the GitHub repo
- env files exist
- ports 80 and 8000 are available

- [ ] **Step 3: Add environment-file expectations**

Document server-side env files:
- `/opt/finmodpro/.env.backend`
- `/opt/finmodpro/.env.frontend`

State clearly that production secrets must not be committed to git.

- [ ] **Step 4: Update top-level docs references**

Modify `README.md` and `backend/README.md` to link to `docs/deployment.md`.

- [ ] **Step 5: Update example env docs**

Add comments in `.env.example` files showing which values are expected to differ in production.

- [ ] **Step 6: Commit**

```bash
git add docs/deployment.md README.md backend/README.md backend/.env.example frontend/.env.example
git commit -m "docs: define production deployment contract"
```

---

### Task 2: Containerize the Django backend for production

**Owner:** Codex  
**Files:**
- Create: `backend/Dockerfile`
- Modify: `backend/requirements.txt` (only if image build exposes missing deps)
- Modify: `backend/config/settings.py`
- Test: `backend/manage.py`

- [ ] **Step 1: Write backend image validation notes**

Use these exact validation commands later:

```bash
docker build -t finmodpro-backend:test ./backend
docker run --rm \
  --env DJANGO_SECRET_KEY=test-secret \
  --env JWT_SECRET_KEY=test-jwt-secret \
  finmodpro-backend:test python manage.py check
```

Expected:
- image builds successfully
- `python manage.py check` exits 0 with no issues

- [ ] **Step 2: Create `backend/Dockerfile`**

The Dockerfile should:
- use a Python 3.12 base image
- set a working directory
- copy `requirements.txt` first for cache reuse
- install requirements
- copy project files
- expose backend port `8000`
- use a production-ready command

- [ ] **Step 3: Make only minimal startup config fixes**

Check `backend/config/settings.py` and confirm:
- `ALLOWED_HOSTS` is env-driven
- CORS / CSRF trusted origins are env-driven
- DB / Redis / Celery / Milvus config reads from env cleanly

Do **not** introduce a new settings framework or broad refactor.

- [ ] **Step 4: Build the backend image**

Run:

```bash
docker build -t finmodpro-backend:test ./backend
```

Expected: successful build.

- [ ] **Step 5: Run backend self-check inside container**

Run:

```bash
docker run --rm \
  --env DJANGO_SECRET_KEY=test-secret \
  --env JWT_SECRET_KEY=test-jwt-secret \
  finmodpro-backend:test python manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile backend/config/settings.py backend/requirements.txt
git commit -m "feat(deploy): containerize backend for production"
```

---

### Task 3: Containerize the Vite frontend for production

**Owner:** Gemini  
**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Modify: `frontend/src/api/config.js`
- Modify: `frontend/vite.config.js`
- Test: `frontend/package.json`

- [ ] **Step 1: Lock the frontend production config strategy**

Document and implement this rule:
- production API base URL comes from `VITE_API_BASE_URL`
- no runtime template injection in v1
- no deployed-build fallback to `http://localhost:8000`

- [ ] **Step 2: Create `frontend/Dockerfile`**

The Dockerfile should:
- use a Node build stage
- install deps with `npm ci`
- run `npm run build`
- copy built assets into an Nginx image
- use `frontend/nginx.conf`

- [ ] **Step 3: Create `frontend/nginx.conf`**

Config must include:
- static file serving on port `80`
- `try_files $uri /index.html` for SPA fallback
- optional `/healthz` endpoint if convenient

- [ ] **Step 4: Adjust frontend runtime config**

Verify `frontend/src/api/config.js` and `frontend/vite.config.js` so that:
- production builds read `VITE_API_BASE_URL`
- localhost fallback is only acceptable for explicit local dev behavior, not silent production fallback
- built assets work correctly for SPA route refresh

- [ ] **Step 5: Build frontend image**

Run:

```bash
docker build -t finmodpro-frontend:test ./frontend
```

Expected: successful build.

- [ ] **Step 6: Smoke-check static container**

Run:

```bash
docker run --rm -d -p 18080:80 --name finmodpro-frontend-test finmodpro-frontend:test
curl -I http://127.0.0.1:18080
curl -I http://127.0.0.1:18080/some/spa/route
```

Expected:
- root returns `200`
- SPA route returns HTML instead of `404`

- [ ] **Step 7: Stop test container**

Run:

```bash
docker rm -f finmodpro-frontend-test
```

- [ ] **Step 8: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf frontend/src/api/config.js frontend/vite.config.js
git commit -m "feat(deploy): containerize frontend for production"
```

---

### Task 4: Create production Docker Compose orchestration

**Owner:** Codex  
**Files:**
- Create: `docker-compose.prod.yml`
- Modify: `docs/deployment.md`
- Test: `docker-compose.prod.yml`

- [ ] **Step 1: Define services and ports**

Compose file must cover at minimum:
- `backend` → host `8000`
- `frontend` → host `80`
- `mysql`
- `redis`
- `milvus`
- `ollama`

- [ ] **Step 2: Add named volumes / bind mounts**

Include persistence for:
- MySQL data
- Milvus data
- Ollama model cache
- backend media/static if required

- [ ] **Step 3: Wire service env files**

Reference server-managed env files rather than committing secrets.

- [ ] **Step 4: Validate compose syntax**

Run:

```bash
docker compose -f docker-compose.prod.yml config
```

Expected: expanded compose config with no errors.

- [ ] **Step 5: Define local-vs-live verification boundary**

Document clearly in `docs/deployment.md`:
- local validation minimum = `docker compose config` + individual frontend/backend image builds
- first full-stack proof = first live deployment on the target server

This avoids pretending local full-stack startup is guaranteed on a development box.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.prod.yml docs/deployment.md
git commit -m "feat(deploy): add production docker compose stack"
```

---

### Task 5: Add server deployment and smoke-check scripts

**Owner:** Codex  
**Files:**
- Create: `scripts/deploy.sh`
- Create: `scripts/smoke-check.sh`
- Modify: `docs/deployment.md`

- [ ] **Step 1: Create `scripts/deploy.sh`**

The script should:
- `cd /opt/finmodpro`
- write current commit to `.last_deployed_commit` before updating
- `git fetch --all --prune`
- `git checkout main`
- `git pull origin main`
- run `docker compose -f docker-compose.prod.yml up -d --build`
- invoke smoke check script
- exit non-zero on any failure

- [ ] **Step 2: Clarify script source-of-truth behavior**

Document in `docs/deployment.md`:
- first deployment requires a manual clone to `/opt/finmodpro`
- later deployments use the latest repo version of `scripts/deploy.sh` after `git pull`

- [ ] **Step 3: Create `scripts/smoke-check.sh`**

The script should check at minimum:
- backend health endpoint returns 200 from `http://127.0.0.1:8000/api/health/`
- frontend root page returns 200 from `http://127.0.0.1/`
- optionally one known API endpoint responds without 5xx

- [ ] **Step 4: Make scripts executable**

Run:

```bash
chmod +x scripts/deploy.sh scripts/smoke-check.sh
```

- [ ] **Step 5: Add manual rollback command template**

Document this exact baseline pattern in `docs/deployment.md`:

```bash
cd /opt/finmodpro
git checkout <previous-commit>
docker compose -f docker-compose.prod.yml up -d --build
```

Also document how to read `.last_deployed_commit`.

- [ ] **Step 6: Commit**

```bash
git add scripts/deploy.sh scripts/smoke-check.sh docs/deployment.md
git commit -m "feat(deploy): add server deploy and smoke check scripts"
```

---

### Task 6: Implement GitHub Actions CI/CD workflow

**Owner:** Codex with Gemini review for frontend steps  
**Files:**
- Create: `.github/workflows/ci-cd.yml`
- Modify: `docs/deployment.md`
- Test: `.github/workflows/ci-cd.yml`

- [ ] **Step 1: Add backend CI job**

Workflow job should:
- checkout repo
- set up Python
- install backend deps
- run `python manage.py check`
- run backend tests that are stable under current repo defaults

Suggested commands:

```bash
cd backend
python -m pip install -r requirements.txt
python manage.py check
python manage.py test
```

If some tests require external services, split them out or document why they are excluded from CI.

- [ ] **Step 2: Add frontend CI job**

Workflow job should:
- set up Node
- install deps via `npm ci`
- run frontend build

Suggested commands:

```bash
cd frontend
npm ci
npm run build
```

- [ ] **Step 3: Add deploy job gated on CI success**

Deploy job should:
- run only on `push` to `main`
- use GitHub Secrets for SSH connection
- connect to the server
- run `/opt/finmodpro/scripts/deploy.sh`

- [ ] **Step 4: Add failure visibility**

Ensure logs clearly show which stage failed:
- backend check/test
- frontend build
- SSH connection
- deploy script
- smoke check

- [ ] **Step 5: Validate workflow syntax**

If no local linter is available, validate by:
- careful YAML inspection
- checking generated workflow in git diff
- first GitHub run result

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci-cd.yml docs/deployment.md
git commit -m "feat(ci): add github actions deployment workflow"
```

---

### Task 7: Live deployment verification and final handoff

**Owner:** Dora  
**Files:**
- Modify: `docs/deployment.md`
- Modify: `README.md`

- [ ] **Step 1: Prepare GitHub Secrets on the repository**

Set:
- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`

- [ ] **Step 2: Prepare server deployment directory**

Run on server:

```bash
sudo mkdir -p /opt/finmodpro
sudo chown -R $USER:$USER /opt/finmodpro
git clone <repo-url> /opt/finmodpro
```

Then place env files under `/opt/finmodpro`.

- [ ] **Step 3: Verify server prerequisites**

Confirm manually:
- `git --version`
- `docker --version`
- `docker compose version`
- repo pull access works
- env files exist
- ports 80 and 8000 are usable

- [ ] **Step 4: Execute first live deployment from GitHub Actions**

Trigger by pushing the workflow branch merge to `main`.

Expected:
- backend CI passes
- frontend build passes
- deploy job runs
- containers restart successfully

- [ ] **Step 5: Verify live smoke checks**

Check:
- `http://127.0.0.1/` loads
- `http://127.0.0.1:8000/api/health/` returns 200
- one real frontend API call reaches the backend successfully

- [ ] **Step 6: Update docs with final proven commands**

If any command differs from plan assumptions after real deployment, update `docs/deployment.md` and `README.md` immediately.

- [ ] **Step 7: Commit**

```bash
git add docs/deployment.md README.md
git commit -m "docs: finalize deployment verification notes"
```

---

## Suggested execution split

### Codex task batch
1. Task 2 — backend containerization
2. Task 4 — production compose
3. Task 5 — deploy/smoke scripts
4. Task 6 — GitHub Actions workflow

### Gemini task batch
1. Task 3 — frontend containerization
2. frontend review input for Task 6

### Dora task batch
1. Task 1 — deployment contract docs
2. Task 7 — live verification / final handoff

---

## Verification checklist before claiming completion

- [ ] `docker build -t finmodpro-backend:test ./backend` succeeds
- [ ] `docker build -t finmodpro-frontend:test ./frontend` succeeds
- [ ] `docker compose -f docker-compose.prod.yml config` succeeds
- [ ] GitHub Actions workflow file is present and readable
- [ ] One GitHub Actions run reaches deploy stage successfully
- [ ] `http://127.0.0.1:8000/api/health/` passes after deployment
- [ ] `http://127.0.0.1/` passes after deployment
- [ ] Deployment docs are accurate enough for reuse

---

## Notes for agentic workers

- Do not commit production secrets.
- Do not silently change `/opt/finmodpro` without updating the plan.
- Keep the first version simple: one workflow, one compose file, one deploy script.
- Prefer minimal safe changes over ambitious infra refactors.
- Commit after each task; push after each reviewed task batch.
