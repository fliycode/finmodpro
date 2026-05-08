# FinModPro Copilot Instructions

## Build, test, and run commands

### Frontend (`frontend/`)

- Install: `npm install`
- Local dev server: `npm run dev -- --host 127.0.0.1 --port 5173`
- Full test suite: `npm test`
- Single test file: `npm test -- src/api/__tests__/auth.test.js`
- Production build: `npm run build`

There is currently **no dedicated frontend lint script** in `frontend/package.json`.

### Backend (`backend/`)

- Create venv: `python3 -m venv .venv`
- Activate venv: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Load env file explicitly:
  ```bash
  cp .env.example .env
  set -a
  source .env
  set +a
  ```
- Apply schema and seed RBAC: `python manage.py migrate && python manage.py seed_rbac`
- Run server: `python manage.py runserver 127.0.0.1:8000`
- Django checks: `python manage.py check`
- Full test suite: `python manage.py test`
- Single app: `python manage.py test authentication`
- Single test class: `python manage.py test authentication.tests.AuthenticationApiTests`
- Single test method: `python manage.py test authentication.tests.AuthenticationApiTests.test_login_returns_access_token_for_valid_credentials`

There is currently **no dedicated backend lint command** checked into the repo.

### Deployment scripts

- Production deploy entrypoint: `./scripts/deploy.sh`
- Post-deploy smoke checks: `./scripts/smoke-check.sh`

`deploy.sh` is designed to run from `/opt/finmodpro` on the server. It renders LiteLLM config first, then runs `docker compose -f docker-compose.prod.yml up -d --build`, then runs the smoke checks.

## High-level architecture

FinModPro is a monorepo with a Vue 3 + Vite frontend in `frontend/` and a Django + DRF backend in `backend/`. The frontend is organized around two shells: `/workspace` for regular users and `/admin` for administrators. Route access is enforced in the router with `meta.requiresAuth` / `meta.requiresAdmin`, and the landing route is derived from the current profile's groups and permissions.

Authentication is split between an in-memory access token on the frontend and a refresh-cookie flow on the backend. `frontend/src/lib/auth-storage.js` keeps the access token and profile only in memory, `frontend/src/lib/auth-session.js` bootstraps or refreshes the session, and `frontend/src/api/config.js` retries authenticated requests once after a 401 by invoking the registered refresh handler. In production, the same API config also prefers a same-origin proxy when `VITE_API_BASE_URL` points at a private or loopback host.

The backend is mounted by Django app in `backend/config/urls.py`. The main API areas are:

- `/api/auth/` for login, registration, refresh, logout, and profile
- `/api/` and `/api/systemcheck/` for health and dashboard stats
- `/api/knowledgebase/` for document ingestion flows
- `/api/rag/` for retrieval
- `/api/chat/` for conversation/session APIs
- `/api/risk/` for risk extraction and reporting
- `/api/ops/` for model configs, prompts, evaluations, fine-tunes, and the LiteLLM admin console

The LLM admin surface is a cross-stack feature: frontend admin routes such as `/admin/llm`, `/admin/llm/models`, and `/admin/llm/observability` map to `/api/ops/llm/*`, `/api/ops/model-configs*`, and related endpoints in the `llm` Django app. If you change these surfaces, inspect both the frontend route/view layer and the backend `llm` controllers/URLs together.

## Key conventions for this repository

- **Use code as the source of truth when docs disagree.** `README.md` still describes older SQLite-based local defaults, but the current `backend/config/settings.py` raises `ImproperlyConfigured` unless `DB_ENGINE` is `mysql`.
- **Do not assume `.env` files are auto-loaded.** The backend reads environment variables from the shell; local sessions must explicitly `source .env` before running Django commands.
- **Preserve both trailing-slash and non-trailing-slash API routes when extending existing Django URL modules.** For example, `backend/llm/urls.py` intentionally defines both forms for the same endpoint to keep older callers working.
- **Follow the frontend shell pattern.** Admin and workspace pages are expected to reuse the shared shell primitives (`AppSidebar`, `AppTopbar`, `AppSectionCard`) instead of introducing a new top-level layout style.
- **Keep page-specific styling local.** Shared tokens and shell rules belong in `frontend/src/style.css`; view- or component-specific styles should stay with the owning file.
- **Frontend tests live near the source in `__tests__/` and run with `node --test`.** When changing frontend behavior, prefer adding or updating a nearby file-scoped test rather than creating a central test harness.
- **Backend tests are app-local.** Most apps keep tests in `tests.py`, and targeted Django test invocations by app/class/method are the fastest way to iterate.
- **The deployment workflow is GitHub -> pull on server -> deploy script.** Avoid “manual server hotfix” thinking unless the task explicitly requires it; repository changes should normally flow through `main` and `scripts/deploy.sh`.
- **Commit messages follow Conventional Commits** such as `feat(frontend): ...`, `fix(frontend): ...`, or `fix(llm): ...`.
