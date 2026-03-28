# FinModPro Admin Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 FinModPro 增加适合毕设演示的管理员仪表盘与用户管理子页面，支持管理员查看用户列表并对用户进行多角色增删。

**Architecture:** 后端继续复用 Django `User / Group / Permission` 与现有 JWT 认证闭环，在现有 RBAC 基础上新增管理员用户列表、Group 列表与用户角色更新接口。前端在现有认证页面基础上扩展管理员入口、仪表盘、用户管理页与角色编辑交互，通过局部刷新更新用户行数据。

**Tech Stack:** Django 5, Django auth Group/Permission, JWT, Vue 3, Vite, JavaScript

---

## Planned File Structure

### Backend
- Modify: `projects/finmodpro-backend/rbac/tests.py`
- Create: `projects/finmodpro-backend/rbac/controllers/admin_controller.py`
- Modify: `projects/finmodpro-backend/rbac/controllers/__init__.py`
- Modify: `projects/finmodpro-backend/rbac/services/rbac_service.py`
- Modify: `projects/finmodpro-backend/rbac/services/authz_service.py`
- Modify: `projects/finmodpro-backend/rbac/urls.py`
- Modify: `projects/finmodpro-backend/README.md`

### Frontend
- Create: `projects/finmodpro/src/api/admin.js`
- Create: `projects/finmodpro/src/components/AdminDashboard.vue`
- Create: `projects/finmodpro/src/components/UserManagementTable.vue`
- Create: `projects/finmodpro/src/components/RoleEditorDrawer.vue`
- Modify: `projects/finmodpro/src/lib/permission.js`
- Modify: `projects/finmodpro/src/lib/auth-storage.js`
- Modify: `projects/finmodpro/src/App.vue`
- Modify: `projects/finmodpro/FRONTEND_PROGRESS.md`

---

### Task 1: Add failing backend tests for admin RBAC management APIs

**Files:**
- Modify: `projects/finmodpro-backend/rbac/tests.py`

- [ ] **Step 1: Add a failing test for `GET /api/admin/users` requiring `view_user` and returning RBAC-aware user rows**
- [ ] **Step 2: Add a failing test for `GET /api/admin/groups` requiring `view_role` and returning available groups**
- [ ] **Step 3: Add a failing test for `PUT /api/admin/users/{id}/groups` requiring `assign_role` and replacing the user group set**
- [ ] **Step 4: Add a failing test that a low-privilege `member` receives `403` on admin APIs**
- [ ] **Step 5: Run `python manage.py test rbac -v 2` and confirm the new admin tests fail for the expected missing behavior**
- [ ] **Step 6: Commit the backend red test state**

### Task 2: Implement backend admin user, group, and role assignment endpoints

**Files:**
- Create: `projects/finmodpro-backend/rbac/controllers/admin_controller.py`
- Modify: `projects/finmodpro-backend/rbac/services/rbac_service.py`
- Modify: `projects/finmodpro-backend/rbac/services/authz_service.py`
- Modify: `projects/finmodpro-backend/rbac/urls.py`
- Modify: `projects/finmodpro-backend/rbac/controllers/__init__.py`

- [ ] **Step 1: Add service helpers for serializing admin user rows including `id`, `username`, `email`, `groups`, `permissions`, `is_superuser`, `is_staff`, and `date_joined`**
- [ ] **Step 2: Add a service helper that returns all assignable groups in a simple API-friendly structure**
- [ ] **Step 3: Add a service helper that replaces a user’s groups from a submitted group-name list and returns the updated serialized row**
- [ ] **Step 4: Implement `GET /api/admin/users` protected by `view_user`**
- [ ] **Step 5: Implement `GET /api/admin/groups` protected by `view_role`**
- [ ] **Step 6: Implement `PUT /api/admin/users/<id>/groups` protected by `assign_role`**
- [ ] **Step 7: Re-run `python manage.py test rbac -v 2` and verify the admin API tests pass**
- [ ] **Step 8: Commit the backend admin management API layer**

### Task 3: Update backend docs for the admin demo flow

**Files:**
- Modify: `projects/finmodpro-backend/README.md`

- [ ] **Step 1: Document the new admin APIs and their permission requirements**
- [ ] **Step 2: Document the expected payload for role replacement (`groups: [...]`)**
- [ ] **Step 3: Document the intended demo flow: admin login -> dashboard -> user management -> role update**
- [ ] **Step 4: Run `python manage.py check` and confirm the documented routes remain valid**
- [ ] **Step 5: Commit the backend documentation update**

### Task 4: Add frontend API helpers and red-path UI expectations for admin demo pages

**Files:**
- Create: `projects/finmodpro/src/api/admin.js`
- Modify: `projects/finmodpro/src/lib/permission.js`
- Modify: `projects/finmodpro/src/App.vue`

- [ ] **Step 1: Define admin API helper functions for fetching users, fetching groups, and updating user groups**
- [ ] **Step 2: Extend permission helpers with clear admin-entry checks (for example, `canViewAdminArea`)**
- [ ] **Step 3: Add or update a lightweight verification checklist describing expected admin UI behavior before implementation**
- [ ] **Step 4: Commit the frontend expectation state if code-based tests are not added**

### Task 5: Implement the admin dashboard shell and routing state in the frontend

**Files:**
- Create: `projects/finmodpro/src/components/AdminDashboard.vue`
- Modify: `projects/finmodpro/src/App.vue`
- Modify: `projects/finmodpro/src/lib/auth-storage.js`
- Modify: `projects/finmodpro/src/lib/permission.js`

- [ ] **Step 1: Add a minimal app-state mode or route-like state that can switch between auth view, admin dashboard, and user management view**
- [ ] **Step 2: Create `AdminDashboard.vue` with identity card, overview cards, RBAC summary, and user-management entry action**
- [ ] **Step 3: Gate admin dashboard entry behind role/permission checks so ordinary users cannot reach it**
- [ ] **Step 4: Preserve the current authentication flow and UI styling language while extending it**
- [ ] **Step 5: Build locally with `npm run build` to catch integration issues early**
- [ ] **Step 6: Commit the admin dashboard shell**

### Task 6: Implement the user management page and role editor interaction

**Files:**
- Create: `projects/finmodpro/src/components/UserManagementTable.vue`
- Create: `projects/finmodpro/src/components/RoleEditorDrawer.vue`
- Create: `projects/finmodpro/src/api/admin.js`
- Modify: `projects/finmodpro/src/App.vue`

- [ ] **Step 1: Build `UserManagementTable.vue` for a near-admin-style user table with search, role filter, and action column**
- [ ] **Step 2: Build `RoleEditorDrawer.vue` or modal for multi-role add/remove editing**
- [ ] **Step 3: Load `/api/admin/users` and `/api/admin/groups` when the user management page opens**
- [ ] **Step 4: Wire the role editor to submit `PUT /api/admin/users/{id}/groups` with the full selected group list**
- [ ] **Step 5: Update only the edited user row after success instead of reloading the entire table**
- [ ] **Step 6: Surface backend errors clearly in the role editor or page status area**
- [ ] **Step 7: Run `npm run build` and verify the user management experience still bundles successfully**
- [ ] **Step 8: Commit the user management UI and role editing flow**

### Task 7: Update frontend docs and verify the full admin demo chain

**Files:**
- Modify: `projects/finmodpro/FRONTEND_PROGRESS.md`
- Modify if needed: `projects/finmodpro/src/App.vue`

- [ ] **Step 1: Update `FRONTEND_PROGRESS.md` with the new admin dashboard and user management capabilities**
- [ ] **Step 2: Document the backend dependencies: `/api/admin/users`, `/api/admin/groups`, `PUT /api/admin/users/{id}/groups`**
- [ ] **Step 3: Manually verify the demo chain: ordinary user hides admin entry, admin sees dashboard, admin edits a user’s roles, UI updates locally**
- [ ] **Step 4: Re-run backend tests and frontend build together to validate the full feature set**
- [ ] **Step 5: Commit the final admin demo verification pass**
