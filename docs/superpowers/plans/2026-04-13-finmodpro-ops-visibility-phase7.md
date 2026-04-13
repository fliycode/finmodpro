# FinModPro Ops Visibility And Audit Phase 7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve operational visibility with task backlog/failure visibility, retry hooks for feasible background workflows, and lightweight audit records for key platform actions.

**Architecture:** Keep this phase intentionally lightweight. Reuse `systemcheck` as the surface for admin visibility and add small audit/task summaries rather than a heavyweight observability stack. Extend existing ingestion and extraction paths only where current architecture can actually retry work.

**Tech Stack:** Django, existing `systemcheck`, `knowledgebase`, and `risk` apps, Vue 3 admin dashboard, Django test runner, frontend build/test flow

---

## Scope

### In Scope

- Recent operational failures
- Retryable ingestion/extraction actions
- Lightweight audit records
- Dashboard visibility for backlog/failure state

### Out of Scope

- Full log aggregation stack
- Metrics agent/exporter ecosystem
- Resource-level host monitoring

## Locked Decisions

- Keep audit storage simple and application-level.
- Retry only operations that are already rerunnable in current code.
- Surface operational data in the existing admin overview.

## File Structure

- `backend/systemcheck/services/audit_service.py`
- `backend/systemcheck/controllers/audit_controller.py`
- `backend/systemcheck/urls.py`
- `backend/systemcheck/tests.py`
- `backend/knowledgebase/controllers/ingest_controller.py`
- `backend/risk/controllers/extract_controller.py`
- `backend/risk/controllers/batch_extract_controller.py`
- `frontend/src/api/dashboard.js`
- `frontend/src/components/OpsDashboard.vue`

## Task 1: Add failing backend tests

**Files:**
- Modify: `backend/systemcheck/tests.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Add audit list tests**
- [ ] **Step 2: Add retry action tests for failed tasks**
- [ ] **Step 3: Run failing tests**

```bash
cd backend && python manage.py test systemcheck knowledgebase risk -v 2
```

Expected: FAIL on missing audit/retry support

## Task 2: Implement backend audit and retry support

**Files:**
- Create: `backend/systemcheck/services/audit_service.py`
- Create: `backend/systemcheck/controllers/audit_controller.py`
- Modify: `backend/systemcheck/urls.py`
- Modify: `backend/knowledgebase/controllers/ingest_controller.py`
- Modify: `backend/risk/controllers/extract_controller.py`
- Modify: `backend/risk/controllers/batch_extract_controller.py`

- [ ] **Step 1: Add lightweight audit record service/model if needed**
- [ ] **Step 2: Record key operations**
- [ ] **Step 3: Add retry entry points for failed work**
- [ ] **Step 4: Verify backend**

```bash
cd backend && python manage.py test systemcheck knowledgebase risk -v 2
```

Expected: PASS

## Task 3: Extend admin dashboard visibility

**Files:**
- Modify: `frontend/src/api/dashboard.js`
- Modify: `frontend/src/components/OpsDashboard.vue`

- [ ] **Step 1: Add API support for audit/task visibility**
- [ ] **Step 2: Show recent failures, retry counts, and audit snippets**
- [ ] **Step 3: Verify frontend**

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS

## Task 4: Final verification and commit

- [ ] **Step 1: Run combined verification**

```bash
cd backend && python manage.py test systemcheck knowledgebase risk -v 2
cd frontend && npm test
cd frontend && npm run build
```

- [ ] **Step 2: Commit**

```bash
git add backend/systemcheck backend/knowledgebase backend/risk frontend/src/api/dashboard.js frontend/src/components/OpsDashboard.vue docs/superpowers/plans/2026-04-13-finmodpro-ops-visibility-phase7.md
git commit -m "feat(platform): add ops visibility and light audit"
```

## Acceptance Checklist

- [ ] Admin can see recent failures and backlog signals
- [ ] Retry hooks exist for realistic failure cases
- [ ] Lightweight audit records are queryable
- [ ] Dashboard exposes the new operational information
