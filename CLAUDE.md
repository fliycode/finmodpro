# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Test, and Run Commands

### Frontend (`frontend/`)
- Install: `npm install`
- Dev server: `npm run dev -- --host 127.0.0.1 --port 5173`
- Full test suite: `npm test`
- Single test: `npm test -- src/lib/__tests__/auth-form.test.js`
- Production build: `npm run build`

### Backend (`backend/`)
- Create venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Load env: `cp .env.example .env && set -a && source .env && set +a`
- Migrate + seed: `python manage.py migrate && python manage.py seed_rbac`
- Run server: `python manage.py runserver 127.0.0.1:8000`
- Full tests: `python manage.py test`
- Single app: `python manage.py test authentication`
- Single test: `python manage.py test authentication.tests.AuthenticationApiTests.test_login_returns_access_token_for_valid_credentials`

### Production Deploy
- Deploy: `./scripts/deploy.sh` (runs from `/opt/finmodpro` on the server)
- Smoke check: `./scripts/smoke-check.sh`

## Production Environment

**127.0.0.1 is the production server.** The deployment target is `root@47.85.103.76`, and all services run on that single machine. Nginx on the frontend container reverse-proxies `/api/` to the backend container over the Docker network, so both frontend and backend are accessed via 127.0.0.1 from the host. The deploy script at `/opt/finmodpro/scripts/deploy.sh` handles the full `git pull -> docker compose up -> migrate -> smoke check` pipeline. Never edit files directly on the server — changes flow through `main` on GitHub, then are pulled and deployed.

## Architecture

FinModPro is a monorepo: Vue 3 + Vite frontend in `frontend/`, Django 5 + DRF backend in `backend/`.

### Frontend
- **Shells:** Two layout modes — `/workspace` (analyst "Study" — warm parchment tones) and `/admin` (operator "War Room" — dark navy tones). Both share `AppSidebar`, `AppTopbar`, `AppSectionCard` primitives.
- **Auth:** Access token stored in-memory only (`frontend/src/lib/auth-storage.js`), refresh token via HTTP-only cookie. `frontend/src/lib/auth-session.js` bootstraps sessions; `frontend/src/api/config.js` retries 401s once with refresh.
- **Routing:** `frontend/src/router/index.js` enforces auth/admin guards via `meta.requiresAuth` / `meta.requiresAdmin`. Landing route derived from user's groups/permissions.
- **Design:** `frontend/src/style.css` holds shared tokens and shell rules. Page-specific styles stay with their component. No TypeScript — pure JavaScript ES modules.

### Backend
- **URLs:** `backend/config/urls.py` mounts all app routes. Key areas: `/api/auth/`, `/api/systemcheck/`, `/api/knowledgebase/`, `/api/rag/`, `/api/chat/`, `/api/risk/`, `/api/ops/`.
- **Pattern:** Each Django app follows controllers/services layout (not class-based views): `models.py`, `urls.py`, `controllers/`, `services/`, `tasks.py`, `tests.py`.
- **LLM stack:** LiteLLM gateway (port 4000) + Langfuse observability + DeepSeek models + DashScope embeddings/rerank. The `llm` Django app manages model configs, prompts, evaluations, and fine-tune registry.
- **Auth:** Custom JWT backend in `authentication/`. Three RBAC roles seeded by `seed_rbac`: `super_admin`, `admin`, `member`.

### Docker Compose (production)
`docker-compose.prod.yml` runs 10 services: frontend (nginx), backend (gunicorn), celery-worker, unstructured-api, mysql:8.4, redis:7-alpine, litellm, etcd, minio, milvus standalone.

## Key Conventions

- **Code is the source of truth.** `README.md` describes SQLite defaults, but `settings.py` now requires `DB_ENGINE=mysql`.
- **`.env` is never auto-loaded.** Always `source .env` explicitly before Django commands.
- **Preserve both trailing-slash and non-trailing-slash API routes** when extending Django URL modules.
- **Conventional Commits:** `type(scope): summary` — scopes: `frontend`, `backend`, or a backend app name.
- **Git Author:** All commits MUST use `fliycode <112712652+fliycode@users.noreply.github.com>` as the author. This is enforced by git config. Never use other author names (Dora, Codex, etc.).
- **Design system:** Two-Desk Rule (warm tones in workspace, cool tones in admin, only Command Blue #2457c5 crosses both). One Accent Rule (Command Blue ≤10% of any screen). 24px card radius. No pure black/white, no nested cards, no gradient heroes.
- **Frontend tests** live in `__tests__/` next to source, run with `node --test`.
- **Backend tests** live in each app's `tests.py`, run with Django's test runner.

See `AGENTS.md` for additional conventions and `DESIGN.md` for the full design system specification.
