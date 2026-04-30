# Repository Guidelines

## Project Structure & Module Organization
`finmodpro` is a monorepo with a Vue frontend in `frontend/` and a Django backend in `backend/`. Frontend source lives in `frontend/src`, organized by `api/`, `components/`, `layouts/`, `views/`, `lib/`, and `config/`; assets are under `frontend/public` and `frontend/src/assets`. Backend apps include `authentication`, `rbac`, `knowledgebase`, `rag`, `chat`, `risk`, `llm`, and `systemcheck`, with project settings in `backend/config`. Shared docs sit in `docs/`; deployment helpers live in `scripts/`.

## Build, Test, and Development Commands
Frontend:
- `cd frontend && npm install` installs Vite and Vue dependencies.
- `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173` starts the local UI.
- `cd frontend && npm run build` creates a production bundle.
- `cd frontend && npm test` runs the Node test suite.

Backend:
- `cd backend && python -m venv .venv` creates a virtual environment.
- `cd backend && .venv\Scripts\activate && pip install -r requirements.txt` installs Django dependencies on Windows.
- `cd backend && python manage.py migrate` applies database migrations.
- `cd backend && python manage.py seed_rbac` seeds default roles and permissions.
- `cd backend && python manage.py runserver 127.0.0.1:8000` starts the API server.
- `cd backend && python manage.py check && python manage.py test` runs framework checks and tests.

## Coding Style & Naming Conventions
Follow existing style in nearby files. Python uses 4-space indentation, snake_case modules, and app-local `tests.py` files. Vue and JavaScript use ES modules, semicolons, PascalCase component filenames such as `AdminOverviewView.vue`, and helper filenames such as `session-state.js`. Keep API wrappers in `frontend/src/api` and reusable UI in `frontend/src/components/ui`.

Frontend conventions:
- Admin and workspace pages should share the same shell primitives (`AppSidebar`, `AppTopbar`, `AppSectionCard`) even when information density differs.
- Keep page-specific styles close to the owning view or component; `frontend/src/style.css` is for shared tokens and shell rules.
- Avoid decorative dashboard heroes, fake trend charts, and gradient-heavy cards; prefer restrained institutional surfaces and evidence-driven layouts.

## Frontend design-reference workflow

- When a user explicitly asks for premium polish, stronger visual design, or inspiration from specific websites/products, use `frontend-design-reference` before `frontend-design` or implementation.
- Use `frontend-design-reference` to pick one primary style reference, at most one secondary reference, and the minimum necessary pattern categories.
- Do not paste raw `galaxy` snippets into product code; translate them into local components and existing shell patterns.

## Testing Guidelines
Backend tests use Django's test runner and `pytest` discovery settings from `backend/pytest.ini`; keep tests in each app's `tests.py` or `test_*.py`. Frontend tests run with `node --test` and are placed beside source in `__tests__/`, for example `frontend/src/lib/__tests__/auth-form.test.js`. Add or update tests with every behavior change.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commits: `feat(frontend): ...`, `fix(frontend): ...`, `refactor(frontend): ...`. Continue using `type(scope): imperative summary`, with scopes like `frontend`, `backend`, or a backend app name. PRs should include a short problem statement, a change summary, linked issues when applicable, and verification notes listing the commands you ran. Include screenshots or recordings for UI changes.

## Deployment Workflow
This repository is the live `finmodpro` project. The source of truth is GitHub, and normal delivery is `local change -> push -> pipeline deploy`; avoid manual server edits unless the task explicitly requires them. This machine IS the production server. Deployments run directly via `./scripts/deploy.sh` — no SSH needed.

## Security & Configuration Tips
Copy `frontend/.env.example` and `backend/.env.example` for local setup, but never commit real secrets. Store server passwords and similar credentials in a local password manager or other out-of-repo secret store, not in `AGENTS.md`, source files, or scripts. Default local development uses SQLite and in-memory Celery/Redis substitutes; document any required external services when changing that assumption.
