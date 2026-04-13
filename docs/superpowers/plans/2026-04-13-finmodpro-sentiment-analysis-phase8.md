# FinModPro Sentiment Analysis Phase 8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sentiment analysis as the single new high-signal business scenario after the core platform skeleton is stable, reusing the existing knowledge, retrieval, and risk infrastructure instead of creating a detached mini-product.

**Architecture:** Implement sentiment analysis inside the existing `risk` domain because it is adjacent to text-based risk understanding. Reuse current document scope selection, llm runtime, and workspace shell. Keep the first version dataset/document-scoped and summary-driven.

**Tech Stack:** Django, existing risk and llm apps, Vue 3 workspace shell, Django test runner, frontend build/test flow

---

## Scope

### In Scope

- Dataset/document-scoped sentiment analysis
- Sentiment/risk-tendency summary
- Chart-ready sentiment distribution or timeline
- One new workspace page and nav item

### Out of Scope

- Real-time web crawling
- External news subscription pipeline
- Multiple new scenario modules

## Locked Decisions

- Build exactly one new scenario: sentiment analysis.
- Keep it in the workspace, not admin.
- First version can analyze existing uploaded text/document content rather than external live feeds.

## File Structure

- `backend/risk/services/sentiment_service.py`
- `backend/risk/controllers/sentiment_controller.py`
- `backend/risk/urls.py`
- `backend/risk/tests.py`
- `frontend/src/api/sentiment.js`
- `frontend/src/components/SentimentAnalysis.vue`
- `frontend/src/views/workspace/WorkspaceSentimentView.vue`
- `frontend/src/router/routes.js`
- `frontend/src/config/navigation.js`

## API Contract

- `POST /api/risk/sentiment/analyze`

Request:

```json
{
  "dataset_id": 1,
  "document_ids": [3, 4]
}
```

Response:

```json
{
  "summary": {
    "overall_sentiment": "negative",
    "risk_tendency": "elevated"
  },
  "distribution": [
    {"key": "negative", "value": 6}
  ],
  "items": []
}
```

## Task 1: Add failing backend tests

**Files:**
- Modify: `backend/risk/tests.py`

- [ ] **Step 1: Add sentiment analyze tests**
- [ ] **Step 2: Run failing tests**

```bash
cd backend && python manage.py test risk -v 2
```

Expected: FAIL on missing sentiment endpoint/service

## Task 2: Implement backend sentiment service

**Files:**
- Create: `backend/risk/services/sentiment_service.py`
- Create: `backend/risk/controllers/sentiment_controller.py`
- Modify: `backend/risk/urls.py`

- [ ] **Step 1: Add dataset/document scoped sentiment service**
- [ ] **Step 2: Add controller and route**
- [ ] **Step 3: Verify backend**

```bash
cd backend && python manage.py test risk -v 2
```

Expected: PASS

## Task 3: Implement workspace sentiment page

**Files:**
- Create: `frontend/src/api/sentiment.js`
- Create: `frontend/src/components/SentimentAnalysis.vue`
- Create: `frontend/src/views/workspace/WorkspaceSentimentView.vue`
- Modify: `frontend/src/router/routes.js`
- Modify: `frontend/src/config/navigation.js`

- [ ] **Step 1: Add frontend API wrapper**
- [ ] **Step 2: Build a single workspace page with dataset/document scope selection**
- [ ] **Step 3: Add navigation entry after route exists**
- [ ] **Step 4: Verify frontend**

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
git add backend/risk frontend/src/api/sentiment.js frontend/src/components/SentimentAnalysis.vue frontend/src/views/workspace/WorkspaceSentimentView.vue frontend/src/router/routes.js frontend/src/config/navigation.js docs/superpowers/plans/2026-04-13-finmodpro-sentiment-analysis-phase8.md
git commit -m "feat(platform): add sentiment analysis scenario"
```

## Acceptance Checklist

- [ ] One new scenario module exists
- [ ] It reuses dataset/document scope rather than inventing a parallel data flow
- [ ] Workspace navigation includes the new page
- [ ] Sentiment summaries are backend-generated and chart-ready
