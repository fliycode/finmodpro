# FinModPro Risk Analytics And Export Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing risk extraction and report flow into a richer analytics loop with chart-ready summaries, stronger filtering, and export capabilities for reports and event summaries.

**Architecture:** Keep the risk domain inside the existing `risk` app. Add aggregation services and export-oriented controllers on top of current `RiskEvent` and `RiskReport` models, then extend `RiskSummary.vue` to consume chart-ready backend data rather than generating pseudo-analytics client-side.

**Tech Stack:** Django, existing risk app, Vue 3, current risk UI, Django test runner, frontend build/test flow

---

## Scope

### In Scope

- Risk event analytics overview
- Risk type/level distribution
- Time-trend summaries
- Report export endpoint
- UI charts and export actions

### Out of Scope

- Multi-tenant approval workflow
- PDF rendering engine if Markdown/text export is sufficient for first pass
- Advanced BI dashboarding

## Locked Decisions

- Analytics data comes from backend aggregation, not frontend recomputation.
- Export format may start with JSON/Markdown/text payloads if PDF is not yet practical.
- Charts stay inside the current risk workspace page.

## File Structure

- `backend/risk/services/analytics_service.py`
- `backend/risk/controllers/analytics_controller.py`
- `backend/risk/controllers/report_controller.py`
- `backend/risk/urls.py`
- `backend/risk/tests.py`
- `frontend/src/api/risk.js`
- `frontend/src/components/RiskSummary.vue`
- `frontend/src/views/workspace/WorkspaceRiskView.vue`

## API Contract

- `GET /api/risk/analytics/overview`
- `GET /api/risk/reports/<id>/export`

Analytics response:

```json
{
  "risk_level_distribution": [{"key": "high", "value": 6}],
  "risk_type_distribution": [{"key": "liquidity", "value": 4}],
  "trend": [{"date": "2026-04-10", "value": 3}]
}
```

## Task 1: Add failing backend tests

**Files:**
- Modify: `backend/risk/tests.py`

- [ ] **Step 1: Add analytics aggregation tests**
- [ ] **Step 2: Add report export tests**
- [ ] **Step 3: Run failing tests**

```bash
cd backend && python manage.py test risk -v 2
```

Expected: FAIL on missing analytics/export APIs

## Task 2: Implement backend analytics and export

**Files:**
- Create: `backend/risk/services/analytics_service.py`
- Create: `backend/risk/controllers/analytics_controller.py`
- Modify: `backend/risk/controllers/report_controller.py`
- Modify: `backend/risk/urls.py`

- [ ] **Step 1: Add aggregation service**
- [ ] **Step 2: Add overview controller**
- [ ] **Step 3: Add export endpoint for reports**
- [ ] **Step 4: Verify backend**

```bash
cd backend && python manage.py test risk -v 2
```

Expected: PASS

## Task 3: Implement frontend charts and export controls

**Files:**
- Modify: `frontend/src/api/risk.js`
- Modify: `frontend/src/components/RiskSummary.vue`
- Modify: `frontend/src/views/workspace/WorkspaceRiskView.vue`

- [ ] **Step 1: Add analytics/export API calls**
- [ ] **Step 2: Render summary cards, chart-ready sections, and export actions**
- [ ] **Step 3: Verify frontend**

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS

## Task 4: Final verification and commit

- [ ] **Step 1: Run combined verification**

```bash
cd backend && python manage.py test risk -v 2
cd frontend && npm test
cd frontend && npm run build
```

- [ ] **Step 2: Commit**

```bash
git add backend/risk frontend/src/api/risk.js frontend/src/components/RiskSummary.vue frontend/src/views/workspace/WorkspaceRiskView.vue docs/superpowers/plans/2026-04-13-finmodpro-risk-analytics-phase4.md
git commit -m "feat(platform): add risk analytics and export"
```

## Acceptance Checklist

- [ ] Risk analytics endpoint exists
- [ ] Risk page shows chart-ready backend data
- [ ] Reports can be exported
- [ ] Event filtering and statistics are richer than the current baseline
