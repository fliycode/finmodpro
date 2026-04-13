# FinModPro Dataset-Aware Chat And History Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make QA, retrieval, and chat history explicitly dataset-aware, and complete standalone history browsing plus transcript export so the workspace can preserve context and be reused across knowledge domains.

**Architecture:** Reuse `ChatSession.context_filters` as the main context carrier and pass dataset-aware filters through `qaApi`, `chatApi`, `chat.services.ask_service`, and `rag.services.retrieval_service`. Do not introduce a second session system or split history into another app.

**Tech Stack:** Django, existing `chat` and `rag` apps, Vue 3, current QA/history components, Django test runner, Node test runner

---

## Scope

### In Scope

- Dataset-aware chat session creation
- Dataset-aware retrieval filter propagation
- Standalone history page real data loading
- Session filtering/search
- Session transcript export

### Out of Scope

- Collaborative chat sessions
- Rich file export formats beyond JSON/Markdown-ready payloads
- Cross-dataset answer comparison UI

## Locked Decisions

- Keep session context in `ChatSession.context_filters`.
- Export is a backend API, not frontend-only formatting.
- History page remains under `/workspace/history`.
- Dataset selection from QA should drive session context and retrieval filters.

## File Structure

- `backend/chat/models.py`
- `backend/chat/services/session_service.py`
- `backend/chat/services/ask_service.py`
- `backend/chat/controllers/session_controller.py`
- `backend/chat/tests.py`
- `backend/rag/services/retrieval_service.py`
- `frontend/src/api/chat.js`
- `frontend/src/api/qa.js`
- `frontend/src/components/FinancialQA.vue`
- `frontend/src/components/ChatHistory.vue`
- `frontend/src/views/workspace/WorkspaceHistoryView.vue`
- `frontend/src/lib/workspace-qa.js`
- `frontend/src/lib/__tests__/workspace-qa.test.js`

## API Contract

- `GET /api/chat/sessions?dataset_id=1&keyword=流动性`
- `GET /api/chat/sessions/<id>/export`

Export response:

```json
{
  "session": {
    "id": 3,
    "title": "流动性风险讨论",
    "context_filters": {"dataset_id": 1},
    "messages": [
      {"role": "user", "content": "这份纪要提到了哪些风险？"}
    ]
  },
  "exported_at": "2026-04-13T12:00:00+08:00"
}
```

## Task 1: Add failing backend tests for dataset-aware session behavior

**Files:**
- Modify: `backend/chat/tests.py`
- Modify: `backend/rag/tests.py` if retrieval propagation coverage is needed there

- [ ] **Step 1: Add session creation/list/filter/export tests**
- [ ] **Step 2: Add retrieval filter propagation tests**
- [ ] **Step 3: Run failing tests**

```bash
cd backend && python manage.py test chat rag -v 2
```

Expected: FAIL on missing export and dataset filter behavior

## Task 2: Implement backend session/export behavior

**Files:**
- Modify: `backend/chat/services/session_service.py`
- Modify: `backend/chat/controllers/session_controller.py`
- Modify: `backend/chat/services/ask_service.py`
- Modify: `backend/rag/services/retrieval_service.py`

- [ ] **Step 1: Extend session service with filter/export helpers**
- [ ] **Step 2: Add session export endpoint**
- [ ] **Step 3: Pass dataset filters through ask/stream flows**
- [ ] **Step 4: Verify backend**

```bash
cd backend && python manage.py test chat rag -v 2
```

Expected: PASS

## Task 3: Complete frontend history and dataset-aware QA

**Files:**
- Modify: `frontend/src/api/chat.js`
- Modify: `frontend/src/api/qa.js`
- Modify: `frontend/src/components/FinancialQA.vue`
- Modify: `frontend/src/components/ChatHistory.vue`
- Modify: `frontend/src/views/workspace/WorkspaceHistoryView.vue`
- Modify: `frontend/src/lib/workspace-qa.js`
- Modify: `frontend/src/lib/__tests__/workspace-qa.test.js`

- [ ] **Step 1: Add active dataset flow into QA state**
- [ ] **Step 2: Make standalone history load real session data**
- [ ] **Step 3: Add export action in history or session view**
- [ ] **Step 4: Update helper tests**

```bash
cd frontend && node --test src/lib/__tests__/workspace-qa.test.js
cd frontend && npm run build
```

Expected: PASS

## Task 4: Final verification and commit

- [ ] **Step 1: Run combined verification**

```bash
cd backend && python manage.py test chat rag -v 2
cd frontend && npm test
cd frontend && npm run build
```

- [ ] **Step 2: Commit**

```bash
git add backend/chat backend/rag frontend/src/api/chat.js frontend/src/api/qa.js frontend/src/components/FinancialQA.vue frontend/src/components/ChatHistory.vue frontend/src/views/workspace/WorkspaceHistoryView.vue frontend/src/lib/workspace-qa.js frontend/src/lib/__tests__/workspace-qa.test.js docs/superpowers/plans/2026-04-13-finmodpro-dataset-aware-chat-phase3.md
git commit -m "feat(platform): add dataset-aware chat history and export"
```

## Acceptance Checklist

- [ ] Session context stores dataset selection
- [ ] QA requests propagate dataset filters
- [ ] Standalone history page uses real backend data
- [ ] Sessions can be filtered and exported
- [ ] Existing QA flow still works without dataset selection
