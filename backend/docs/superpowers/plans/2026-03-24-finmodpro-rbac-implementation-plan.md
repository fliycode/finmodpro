# FinModPro RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 FinModPro 增加基于 Django Group / Permission 的 RBAC 最小可演示闭环，覆盖默认角色初始化、注册默认角色、`/api/auth/me`、后端权限校验与前端权限消费。

**Architecture:** 继续复用现有 Django `User` 与 JWT 认证闭环，不自建独立 RBAC 域模型；角色直接映射到 Django `Group`，权限直接使用 `Permission`。后端新增独立 `rbac` 模块封装 Group / Permission 查询与鉴权逻辑，前端通过 `/api/auth/me` 获取当前用户角色和权限并控制基础可见性。

**Tech Stack:** Django 5, Django auth Group/Permission, JWT, Vue 3, Vite, JavaScript

---

## Planned File Structure

### Backend
- Create: `projects/finmodpro-backend/rbac/__init__.py`
- Create: `projects/finmodpro-backend/rbac/apps.py`
- Create: `projects/finmodpro-backend/rbac/urls.py`
- Create: `projects/finmodpro-backend/rbac/controllers/__init__.py`
- Create: `projects/finmodpro-backend/rbac/controllers/profile_controller.py`
- Create: `projects/finmodpro-backend/rbac/services/__init__.py`
- Create: `projects/finmodpro-backend/rbac/services/rbac_service.py`
- Create: `projects/finmodpro-backend/rbac/services/authz_service.py`
- Create: `projects/finmodpro-backend/rbac/tests.py`
- Create: `projects/finmodpro-backend/rbac/management/__init__.py`
- Create: `projects/finmodpro-backend/rbac/management/commands/__init__.py`
- Create: `projects/finmodpro-backend/rbac/management/commands/seed_rbac.py`
- Modify: `projects/finmodpro-backend/config/settings.py`
- Modify: `projects/finmodpro-backend/config/urls.py`
- Modify: `projects/finmodpro-backend/authentication/services/auth_service.py`
- Modify: `projects/finmodpro-backend/authentication/tests.py`
- Modify: `projects/finmodpro-backend/README.md`
- Modify: `projects/finmodpro-backend/.env.example`

### Frontend
- Create: `projects/finmodpro/src/lib/auth-storage.js`
- Create: `projects/finmodpro/src/lib/permission.js`
- Modify: `projects/finmodpro/src/api/auth.js`
- Modify: `projects/finmodpro/src/App.vue`
- Modify: `projects/finmodpro/FRONTEND_PROGRESS.md`

---

### Task 1: Add failing backend tests for RBAC profile and default member assignment

**Files:**
- Modify: `projects/finmodpro-backend/authentication/tests.py`
- Create: `projects/finmodpro-backend/rbac/tests.py`

- [ ] **Step 1: Add a failing registration test that asserts new users are added to the `member` group**
- [ ] **Step 2: Add a failing authenticated test for `GET /api/auth/me` returning `id`, `username`, `email`, `groups`, and `permissions`**
- [ ] **Step 3: Add a failing permission-protected test for a dummy protected view or service-level permission check**
- [ ] **Step 4: Run `python manage.py test authentication rbac -v 2` and verify the new tests fail for the expected missing RBAC behavior**
- [ ] **Step 5: Commit the red test state**

### Task 2: Create RBAC app and seedable Group / Permission services

**Files:**
- Create: `projects/finmodpro-backend/rbac/__init__.py`
- Create: `projects/finmodpro-backend/rbac/apps.py`
- Create: `projects/finmodpro-backend/rbac/services/__init__.py`
- Create: `projects/finmodpro-backend/rbac/services/rbac_service.py`
- Create: `projects/finmodpro-backend/rbac/management/__init__.py`
- Create: `projects/finmodpro-backend/rbac/management/commands/__init__.py`
- Create: `projects/finmodpro-backend/rbac/management/commands/seed_rbac.py`
- Modify: `projects/finmodpro-backend/config/settings.py`

- [ ] **Step 1: Register the new `rbac` app in Django settings**
- [ ] **Step 2: Implement role seed definitions for `super_admin`, `admin`, and `member`**
- [ ] **Step 3: Implement permission seed definitions using Django-style permission names plus custom `assign_role` if needed**
- [ ] **Step 4: Add a management command `python manage.py seed_rbac` that creates groups and assigns permissions idempotently**
- [ ] **Step 5: Run the seed command and verify groups exist in the database**
- [ ] **Step 6: Commit the RBAC app and seed command**

### Task 3: Attach default `member` group on registration and expose `/api/auth/me`

**Files:**
- Modify: `projects/finmodpro-backend/authentication/services/auth_service.py`
- Create: `projects/finmodpro-backend/rbac/controllers/__init__.py`
- Create: `projects/finmodpro-backend/rbac/controllers/profile_controller.py`
- Create: `projects/finmodpro-backend/rbac/urls.py`
- Modify: `projects/finmodpro-backend/config/urls.py`
- Modify: `projects/finmodpro-backend/rbac/services/rbac_service.py`

- [ ] **Step 1: Update user registration service so every new user is automatically added to the `member` group**
- [ ] **Step 2: Add a backend helper that serializes a user into `{id, username, email, groups, permissions}`**
- [ ] **Step 3: Add `GET /api/auth/me` that reads the current JWT-authenticated user and returns the serialized RBAC profile**
- [ ] **Step 4: Wire `rbac/urls.py` into `config/urls.py`**
- [ ] **Step 5: Run targeted tests and verify registration + `/api/auth/me` now pass**
- [ ] **Step 6: Commit the profile endpoint and default-role behavior**

### Task 4: Add reusable backend permission-check helpers

**Files:**
- Create: `projects/finmodpro-backend/rbac/services/authz_service.py`
- Modify: `projects/finmodpro-backend/rbac/tests.py`
- Optionally Modify: `projects/finmodpro-backend/rbac/controllers/profile_controller.py`

- [ ] **Step 1: Add a small helper for collecting `user.get_all_permissions()` and checking named permissions**
- [ ] **Step 2: Add a decorator or guard helper for permission-protected views, keeping the implementation minimal and readable**
- [ ] **Step 3: Add tests covering allowed and denied permission checks**
- [ ] **Step 4: Run `python manage.py test rbac -v 2` and verify the permission tests pass**
- [ ] **Step 5: Commit the permission-check helper layer**

### Task 5: Update backend docs for RBAC usage and demo flow

**Files:**
- Modify: `projects/finmodpro-backend/README.md`
- Modify: `projects/finmodpro-backend/.env.example`

- [ ] **Step 1: Document the RBAC model choice: Django `Group / Permission / User`**
- [ ] **Step 2: Document the `seed_rbac` command and default `member` registration behavior**
- [ ] **Step 3: Document the `/api/auth/me` response contract and demo usage**
- [ ] **Step 4: Keep `.env.example` aligned if any RBAC-related settings or notes are needed**
- [ ] **Step 5: Run `python manage.py check` and confirm docs match runnable behavior**
- [ ] **Step 6: Commit the backend docs update**

### Task 6: Add failing frontend tests or checklist-level verification for current-user RBAC consumption

**Files:**
- Modify: `projects/finmodpro/src/api/auth.js`
- Create: `projects/finmodpro/src/lib/auth-storage.js`
- Create: `projects/finmodpro/src/lib/permission.js`
- Modify: `projects/finmodpro/src/App.vue`

- [ ] **Step 1: Add or update a lightweight auth API test/checklist for fetching `/api/auth/me` after login**
- [ ] **Step 2: Define the frontend storage responsibilities: token, user, groups, permissions**
- [ ] **Step 3: Define permission helper expectations such as `hasPermission` and `hasGroup`**
- [ ] **Step 4: Verify the frontend task list clearly identifies what must visibly change after RBAC is wired**
- [ ] **Step 5: Commit the frontend red/expectation state if code-based tests are added; otherwise commit the verification checklist changes**

### Task 7: Implement frontend RBAC profile fetch and UI gating

**Files:**
- Create: `projects/finmodpro/src/lib/auth-storage.js`
- Create: `projects/finmodpro/src/lib/permission.js`
- Modify: `projects/finmodpro/src/api/auth.js`
- Modify: `projects/finmodpro/src/App.vue`
- Modify: `projects/finmodpro/FRONTEND_PROGRESS.md`

- [ ] **Step 1: Extend the auth API with a `me()` call for `GET /api/auth/me`**
- [ ] **Step 2: Add auth storage helpers for persisting token and RBAC profile payload**
- [ ] **Step 3: Add simple permission helper functions for checking group and permission membership**
- [ ] **Step 4: Update the login flow so login success fetches `/api/auth/me` and stores the returned profile**
- [ ] **Step 5: Update the UI to show a minimal logged-in RBAC state block or gated demo controls based on permissions**
- [ ] **Step 6: Keep the current UI structure intact; only add the minimum RBAC display/control affordances**
- [ ] **Step 7: Update `FRONTEND_PROGRESS.md` with RBAC integration details and verification steps**
- [ ] **Step 8: Run `npm run build` and confirm the frontend still bundles successfully**
- [ ] **Step 9: Commit the frontend RBAC integration**

### Task 8: End-to-end verification for the RBAC demo flow

**Files:**
- Modify if needed: `projects/finmodpro-backend/README.md`
- Modify if needed: `projects/finmodpro/FRONTEND_PROGRESS.md`

- [ ] **Step 1: Run backend verification: `python manage.py seed_rbac && python manage.py test authentication rbac systemcheck -v 2`**
- [ ] **Step 2: Run frontend verification: `npm run build`**
- [ ] **Step 3: Manually verify the happy path: register -> login -> fetch `/api/auth/me` -> render RBAC-aware UI state**
- [ ] **Step 4: Manually verify a denied-permission scenario using a low-privilege `member` user**
- [ ] **Step 5: Update docs if any verification mismatch is discovered**
- [ ] **Step 6: Commit the final verified RBAC demo flow**
