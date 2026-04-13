# FinModPro Platform Finish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue evolving FinModPro from a working RAG and risk-extraction demo into a more complete financial risk-control platform with stronger data organization, model adaptation, evaluation, and one additional high-signal business scenario.

**Architecture:** Keep the existing monorepo split of Vue frontend plus Django backend and evolve the platform in four layers: data organization, knowledge/risk workflow, model/evaluation workflow, and scenario expansion. Reuse the current authentication, knowledgebase, chat, risk, and llm modules rather than introducing parallel systems, and land each phase as an independently testable slice.

**Tech Stack:** Vue 3, Vite, Django, Django ORM, existing JWT/RBAC layer, current knowledgebase/risk/chat/llm apps, existing Node test runner, Django test runner

---

## Scope Reference

- Direction doc: `docs/platform-finish-direction.md`
- Current capability inventory: `docs/current-feature-inventory.md`

## Delivery Strategy

- Land work in independent phases.
- Do not start `P2` scenario expansion before `P0` platform skeleton is stable.
- Favor additive schema changes over rewrites.
- Keep every phase deployable on its own.
- Add or update tests with every behavior change.

## File Structure

### Backend

- `backend/knowledgebase/models.py`
  - Add dataset and document-version/provenance entities.
- `backend/knowledgebase/controllers/`
  - Add dataset and version management endpoints.
- `backend/knowledgebase/services/`
  - Add dataset query/command helpers and provenance/versioning helpers.
- `backend/knowledgebase/urls.py`
  - Mount new dataset/version routes.
- `backend/knowledgebase/tests.py`
  - Cover dataset, version, provenance, and filtered query behavior.
- `backend/chat/models.py`
  - Extend session context metadata and export-related storage if needed.
- `backend/chat/controllers/session_controller.py`
  - Complete history and export-oriented APIs.
- `backend/chat/services/session_service.py`
  - Add filtered list/detail/export helpers.
- `backend/rag/services/retrieval_service.py`
  - Support dataset-aware and metadata-aware retrieval.
- `backend/risk/models.py`
  - Add report export metadata and richer aggregation support where needed.
- `backend/risk/controllers/`
  - Add analytics/export endpoints.
- `backend/risk/services/`
  - Add aggregation, export, and chart-ready summary helpers.
- `backend/llm/models.py`
  - Add fine-tune run / model lineage / richer evaluation support.
- `backend/llm/controllers/`
  - Add fine-tune registry and enhanced evaluation APIs.
- `backend/llm/services/`
  - Add evaluation comparison, fine-tune registration, and experiment management helpers.
- `backend/systemcheck/services/dashboard_service.py`
  - Extend metrics after new entities are introduced.
- `backend/*/tests.py`
  - Keep focused coverage inside each app rather than creating a new cross-app test package.

### Frontend

- `frontend/src/api/knowledgebase.js`
  - Add dataset, version, provenance, and filtered query calls.
- `frontend/src/api/chat.js`
  - Add session export and improved history list calls.
- `frontend/src/api/risk.js`
  - Add analytics/export calls.
- `frontend/src/api/llm.js`
  - Add fine-tune registry and enhanced evaluation calls.
- `frontend/src/components/KnowledgeBase.vue`
  - Add dataset selector, provenance/version display, and filtered views.
- `frontend/src/components/FinancialQA.vue`
  - Add dataset-aware querying and export actions.
- `frontend/src/components/ChatHistory.vue`
  - Complete standalone history page data/render contract.
- `frontend/src/components/RiskSummary.vue`
  - Add chart, export, and richer filtering surfaces.
- `frontend/src/components/ModelConfig.vue`
  - Extend model view for fine-tune lineage and version selection.
- `frontend/src/components/EvaluationResult.vue`
  - Show baseline/RAG/fine-tuned comparison metrics.
- `frontend/src/views/workspace/WorkspaceHistoryView.vue`
  - Stop treating history as a shell-only stub and wire real data loading.
- `frontend/src/views/workspace/WorkspaceKnowledgeView.vue`
  - Reflect the upgraded dataset-centric knowledge workflow.
- `frontend/src/views/workspace/WorkspaceRiskView.vue`
  - Reflect richer analytics/export flow.
- `frontend/src/views/workspace/`
  - Add one new scenario view for sentiment analysis in the final phase.
- `frontend/src/config/navigation.js`
  - Add navigation entries only after the corresponding features exist.
- `frontend/src/lib/__tests__/`
  - Add or extend lightweight tests for helper logic and state normalization.

---

### Task 1: Introduce dataset management as the new knowledgebase root

**Files:**
- Modify: `backend/knowledgebase/models.py`
- Create: `backend/knowledgebase/controllers/dataset_controller.py`
- Create: `backend/knowledgebase/services/dataset_service.py`
- Modify: `backend/knowledgebase/urls.py`
- Modify: `backend/knowledgebase/tests.py`
- Modify: `frontend/src/api/knowledgebase.js`
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Modify: `frontend/src/views/workspace/WorkspaceKnowledgeView.vue`
- Modify: `frontend/src/config/navigation.js` only if a dedicated dataset entry becomes necessary
- Test: `backend/knowledgebase/tests.py`
- Test: `frontend/src/lib/__tests__/knowledgebase-actions.test.js`

- [ ] **Step 1: Add the failing backend dataset tests**

Add Django tests that assert:

- datasets can be created and listed
- uploaded documents can belong to a dataset
- list endpoints can be filtered by `dataset_id`
- unauthorized users cannot manage datasets

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
```

Expected: failures referencing missing dataset model, service, or routes

- [ ] **Step 2: Add dataset persistence and service layer**

Implement a minimal dataset model and service API in the existing knowledgebase app instead of creating a new app.

Target shape:

```python
class Dataset(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Then add a nullable `dataset` foreign key onto `Document`.

- [ ] **Step 3: Add dataset endpoints and document filtering**

Expose routes equivalent to:

- `GET /api/knowledgebase/datasets`
- `POST /api/knowledgebase/datasets`
- `GET /api/knowledgebase/datasets/<id>`

Update document list/detail/create logic so dataset filtering is supported through request params and the response includes dataset summary fields.

- [ ] **Step 4: Add the frontend dataset selector and filtered list flow**

Extend `frontend/src/api/knowledgebase.js` and `frontend/src/components/KnowledgeBase.vue` so users can:

- view datasets
- choose the active dataset
- upload a document into the active dataset
- see document lists scoped to that dataset

Keep the page inside the existing workspace shell; do not create a separate admin-only feature unless the backend contract forces it.

- [ ] **Step 5: Add lightweight frontend normalization tests**

Add or extend a Node test around list normalization or dataset selection helpers.

Run:

```bash
cd frontend && node --test src/lib/__tests__/knowledgebase-actions.test.js
```

Expected: pass

- [ ] **Step 6: Run full verification for this slice**

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
cd frontend && npm test
```

Expected: updated knowledgebase tests pass and frontend test suite stays green

- [ ] **Step 7: Commit**

```bash
git add backend/knowledgebase frontend/src/api/knowledgebase.js frontend/src/components/KnowledgeBase.vue frontend/src/views/workspace/WorkspaceKnowledgeView.vue
git commit -m "feat(platform): add dataset-centric knowledgebase workflow"
```

### Task 2: Add document versioning and provenance without breaking current ingestion

**Files:**
- Modify: `backend/knowledgebase/models.py`
- Create: `backend/knowledgebase/controllers/version_controller.py`
- Create: `backend/knowledgebase/services/version_service.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/urls.py`
- Modify: `backend/knowledgebase/tests.py`
- Modify: `frontend/src/api/knowledgebase.js`
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Test: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Add failing version/provenance tests**

Cover:

- uploading a replacement version for an existing document lineage
- retrieving current version and history
- storing provenance fields such as source type, source label, and processing notes

Run:

```bash
cd backend && python manage.py test knowledgebase.tests.KnowledgebaseApiTests -v 2
```

Expected: failures due to missing version/provenance fields and APIs

- [ ] **Step 2: Add version lineage models and serialization**

Choose the smallest model set that fits the current app:

- either add `root_document`, `version_number`, `is_current`, `source_metadata`
- or introduce a `DocumentVersion` table linked to `Document`

Do not rewrite current ingestion storage or chunk storage.

- [ ] **Step 3: Add replace-version and version-history endpoints**

Expose endpoints equivalent to:

- `POST /api/knowledgebase/documents/<id>/versions`
- `GET /api/knowledgebase/documents/<id>/versions`

Ensure the current version remains obvious in list/detail responses.

- [ ] **Step 4: Render provenance and version history in the knowledge UI**

Update `KnowledgeBase.vue` detail panels to show:

- dataset
- current version
- source metadata
- version history
- latest processing step and failure information

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
cd frontend && npm test
```

Expected: version/provenance behavior is covered and the frontend remains build-safe

- [ ] **Step 6: Commit**

```bash
git add backend/knowledgebase frontend/src/api/knowledgebase.js frontend/src/components/KnowledgeBase.vue
git commit -m "feat(platform): add document versioning and provenance"
```

### Task 3: Make RAG and chat session behavior dataset-aware and export-ready

**Files:**
- Modify: `backend/chat/models.py`
- Modify: `backend/chat/controllers/session_controller.py`
- Modify: `backend/chat/services/session_service.py`
- Modify: `backend/chat/services/ask_service.py`
- Modify: `backend/rag/services/retrieval_service.py`
- Modify: `backend/rag/urls.py` if extra retrieval endpoints are needed
- Modify: `backend/chat/tests.py`
- Modify: `frontend/src/api/chat.js`
- Modify: `frontend/src/api/qa.js`
- Modify: `frontend/src/components/FinancialQA.vue`
- Modify: `frontend/src/components/ChatHistory.vue`
- Modify: `frontend/src/views/workspace/WorkspaceHistoryView.vue`
- Modify: `frontend/src/lib/workspace-qa.js`
- Modify: `frontend/src/lib/__tests__/workspace-qa.test.js`
- Test: `backend/chat/tests.py`
- Test: `frontend/src/lib/__tests__/workspace-qa.test.js`

- [ ] **Step 1: Add failing session filter/export tests**

Cover:

- session creation with dataset context
- listing sessions filtered by dataset or keyword
- exporting a session transcript
- question answering passing dataset-aware filters into retrieval

Run:

```bash
cd backend && python manage.py test chat -v 2
```

Expected: failures around missing export or dataset-aware session behavior

- [ ] **Step 2: Persist session context and export contract**

Reuse `ChatSession.context_filters` for dataset-aware history instead of inventing a second context model. Add export helpers that produce a stable payload:

```json
{
  "session": {
    "id": 1,
    "title": "流动性风险讨论",
    "context_filters": {"dataset_id": 3},
    "messages": [...]
  },
  "exported_at": "2026-04-13T12:00:00Z"
}
```

- [ ] **Step 3: Complete the standalone history page**

Update frontend history flow so `WorkspaceHistoryView.vue` loads real history data instead of rendering `ChatHistory` as a mostly static shell. Add search/filter state and export actions.

- [ ] **Step 4: Pass dataset and metadata filters through QA**

Update `qaApi` and `FinancialQA.vue` so the active dataset, date filters, or future tags can flow into `/api/chat/ask` and `/api/chat/ask/stream`.

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && python manage.py test chat rag -v 2
cd frontend && node --test src/lib/__tests__/workspace-qa.test.js
```

Expected: session, retrieval, and history helpers pass

- [ ] **Step 6: Commit**

```bash
git add backend/chat backend/rag frontend/src/api/chat.js frontend/src/api/qa.js frontend/src/components/FinancialQA.vue frontend/src/components/ChatHistory.vue frontend/src/views/workspace/WorkspaceHistoryView.vue frontend/src/lib/workspace-qa.js frontend/src/lib/__tests__/workspace-qa.test.js
git commit -m "feat(platform): add dataset-aware chat history and export"
```

### Task 4: Turn the risk workflow into a reportable analytics loop

**Files:**
- Modify: `backend/risk/models.py`
- Create: `backend/risk/controllers/analytics_controller.py`
- Create: `backend/risk/services/analytics_service.py`
- Modify: `backend/risk/controllers/report_controller.py`
- Modify: `backend/risk/urls.py`
- Modify: `backend/risk/tests.py`
- Modify: `frontend/src/api/risk.js`
- Modify: `frontend/src/components/RiskSummary.vue`
- Modify: `frontend/src/views/workspace/WorkspaceRiskView.vue`
- Test: `backend/risk/tests.py`

- [ ] **Step 1: Add failing analytics/export tests**

Cover:

- aggregating risk events by type, level, and period
- exporting reports in a downloadable text/markdown-friendly format
- returning chart-ready response structures

Run:

```bash
cd backend && python manage.py test risk -v 2
```

Expected: failures due to missing analytics endpoints and export payloads

- [ ] **Step 2: Add analytics service and endpoints**

Add endpoints equivalent to:

- `GET /api/risk/analytics/overview`
- `GET /api/risk/reports/<id>/export`

Return chart-ready data directly, for example:

```json
{
  "risk_level_distribution": [{"key": "high", "value": 6}],
  "risk_type_distribution": [{"key": "liquidity", "value": 4}],
  "trend": [{"date": "2026-04-01", "value": 3}]
}
```

- [ ] **Step 3: Add frontend charts and export controls**

Update `RiskSummary.vue` so users can:

- filter events
- see summary cards and chart data
- export reports and event summaries

Stay inside the existing workspace UI primitives instead of creating a detached analytics console.

- [ ] **Step 4: Verify**

Run:

```bash
cd backend && python manage.py test risk -v 2
cd frontend && npm test
```

Expected: risk suite passes and frontend stays build/test clean

- [ ] **Step 5: Commit**

```bash
git add backend/risk frontend/src/api/risk.js frontend/src/components/RiskSummary.vue frontend/src/views/workspace/WorkspaceRiskView.vue
git commit -m "feat(platform): add risk analytics and export workflow"
```

### Task 5: Upgrade evaluation from smoke records to comparison-oriented model assessment

**Files:**
- Modify: `backend/llm/models.py`
- Modify: `backend/llm/controllers/evaluation_controller.py`
- Create: `backend/llm/services/evaluation_dataset_service.py`
- Modify: `backend/llm/services/evaluation_service.py`
- Modify: `backend/llm/tests.py`
- Modify: `frontend/src/api/llm.js`
- Modify: `frontend/src/components/EvaluationResult.vue`
- Test: `backend/llm/tests.py`

- [ ] **Step 1: Add failing evaluation comparison tests**

Cover:

- recording evaluation dataset metadata
- comparing baseline vs RAG vs fine-tuned runs
- reporting task-specific metrics such as precision/recall/F1 for extraction

Run:

```bash
cd backend && python manage.py test llm -v 2
```

Expected: failures due to missing comparison metadata or metric fields

- [ ] **Step 2: Extend the evaluation model carefully**

Add only the minimum new fields needed for comparison reporting, such as:

- `evaluation_mode` (`baseline`, `rag`, `fine_tuned`)
- `precision`
- `recall`
- `f1_score`
- `dataset_name`
- `dataset_version`
- `run_notes`

Do not remove current fields; maintain backward compatibility for existing admin UI.

- [ ] **Step 3: Add comparison-oriented list/create APIs**

Support requests that can create or return grouped comparison views for the same target task/version series.

- [ ] **Step 4: Update the evaluation UI to show comparisons**

Render side-by-side comparison rows or grouped cards for:

- baseline model
- RAG-enhanced model
- fine-tuned model

This page should become the main evidence surface for later LoRA work.

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && python manage.py test llm -v 2
cd frontend && npm test
```

Expected: llm tests pass and no frontend regressions appear

- [ ] **Step 6: Commit**

```bash
git add backend/llm frontend/src/api/llm.js frontend/src/components/EvaluationResult.vue
git commit -m "feat(platform): add comparison-oriented model evaluation"
```

### Task 6: Add a manageable LoRA/fine-tune registry instead of jumping straight to full online training

**Files:**
- Modify: `backend/llm/models.py`
- Create: `backend/llm/controllers/fine_tune_controller.py`
- Create: `backend/llm/services/fine_tune_service.py`
- Modify: `backend/llm/urls.py`
- Modify: `backend/llm/tests.py`
- Modify: `frontend/src/api/llm.js`
- Modify: `frontend/src/components/ModelConfig.vue`
- Test: `backend/llm/tests.py`

- [ ] **Step 1: Add failing fine-tune registry tests**

Cover:

- creating a fine-tune run record
- registering a produced model artifact
- linking a fine-tuned model back to its base model and dataset
- listing runs and statuses in the API

Run:

```bash
cd backend && python manage.py test llm -v 2
```

Expected: failures due to missing fine-tune models and routes

- [ ] **Step 2: Introduce the smallest workable fine-tune data model**

Prefer explicit registry entities over embedding everything into `ModelConfig.options`.

Suggested shape:

```python
class FineTuneRun(models.Model):
    base_model = models.ForeignKey(ModelConfig, ...)
    dataset_name = models.CharField(max_length=255)
    dataset_version = models.CharField(max_length=128, blank=True, default="")
    strategy = models.CharField(max_length=64, default="lora")
    status = models.CharField(max_length=32, default="pending")
    artifact_path = models.CharField(max_length=500, blank=True, default="")
    metrics = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Keep actual training execution external for now; this plan only requires platform-side management and comparison.

- [ ] **Step 3: Add fine-tune APIs**

Expose routes equivalent to:

- `GET /api/ops/fine-tunes`
- `POST /api/ops/fine-tunes`
- `PATCH /api/ops/fine-tunes/<id>`

Support status progression such as `pending -> running -> completed/failed`.

- [ ] **Step 4: Extend model management UI**

Update `ModelConfig.vue` so admins can:

- see base model vs fine-tuned models
- inspect fine-tune run history
- select fine-tuned candidates for activation

Avoid building a fake “Start Training” wizard if no real backend execution exists yet; be explicit that the platform currently manages registration and tracking.

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && python manage.py test llm -v 2
cd frontend && npm test
```

Expected: registry APIs and UI integration do not break existing model management

- [ ] **Step 6: Commit**

```bash
git add backend/llm frontend/src/api/llm.js frontend/src/components/ModelConfig.vue
git commit -m "feat(platform): add fine-tune registry and model lineage"
```

### Task 7: Add task visibility, retry hooks, and light audit records for platform operations

**Files:**
- Modify: `backend/knowledgebase/models.py`
- Create: `backend/systemcheck/services/audit_service.py`
- Create: `backend/systemcheck/controllers/audit_controller.py`
- Modify: `backend/systemcheck/urls.py`
- Modify: `backend/systemcheck/tests.py`
- Modify: `backend/knowledgebase/controllers/ingest_controller.py`
- Modify: `backend/risk/controllers/extract_controller.py`
- Modify: `backend/risk/controllers/batch_extract_controller.py`
- Modify: `frontend/src/api/dashboard.js`
- Modify: `frontend/src/components/OpsDashboard.vue`
- Test: `backend/systemcheck/tests.py`

- [ ] **Step 1: Add failing audit/task tests**

Cover:

- listing recent audit entries
- retrying failed ingestion tasks
- showing recent operational failures on the dashboard

Run:

```bash
cd backend && python manage.py test systemcheck knowledgebase -v 2
```

Expected: failures due to missing audit/retry contracts

- [ ] **Step 2: Add light operational audit storage**

Do not build a heavyweight logging framework. Add a small app-level service or model-backed record that captures:

- actor
- action
- target type/id
- status
- detail payload

- [ ] **Step 3: Add retry surfaces for failed ingestion/extraction**

Support retryable operations only where the current backend can realistically rerun work.

- [ ] **Step 4: Surface the new data in the admin dashboard**

Extend `OpsDashboard.vue` and dashboard APIs with:

- recent failures
- retry counts
- task backlog
- audit summary snippets

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && python manage.py test systemcheck knowledgebase risk -v 2
cd frontend && npm test
```

Expected: task visibility and dashboard integration pass

- [ ] **Step 6: Commit**

```bash
git add backend/systemcheck backend/knowledgebase backend/risk frontend/src/api/dashboard.js frontend/src/components/OpsDashboard.vue
git commit -m "feat(platform): add task visibility and light audit workflow"
```

### Task 8: Add sentiment analysis as the single new high-signal scenario

**Files:**
- Create: `backend/risk/controllers/sentiment_controller.py`
- Create: `backend/risk/services/sentiment_service.py`
- Modify: `backend/risk/urls.py`
- Modify: `backend/risk/tests.py`
- Create: `frontend/src/api/sentiment.js`
- Create: `frontend/src/components/SentimentAnalysis.vue`
- Create: `frontend/src/views/workspace/WorkspaceSentimentView.vue`
- Modify: `frontend/src/router/routes.js`
- Modify: `frontend/src/config/navigation.js`
- Test: `backend/risk/tests.py`

- [ ] **Step 1: Add failing sentiment tests**

Cover:

- text or document-based sentiment analysis requests
- summary results with polarity/risk tendency
- timeline or source-group aggregation

Run:

```bash
cd backend && python manage.py test risk -v 2
```

Expected: failures because the sentiment endpoints do not yet exist

- [ ] **Step 2: Implement sentiment service by reusing existing model/runtime infrastructure**

Do not create a new app. Reuse:

- knowledgebase documents as source material where possible
- current chat/runtime provider layer for inference
- risk-style summary payloads for UI rendering

- [ ] **Step 3: Add a single workspace view and navigation entry**

Create one new workspace page, not a second admin system. The first version should support:

- choosing a dataset or document scope
- running sentiment/risk-tendency analysis
- viewing summary cards and trend data

- [ ] **Step 4: Verify**

Run:

```bash
cd backend && python manage.py test risk -v 2
cd frontend && npm test
```

Expected: risk suite expands cleanly and the new route/navigation compiles

- [ ] **Step 5: Commit**

```bash
git add backend/risk frontend/src/api/sentiment.js frontend/src/components/SentimentAnalysis.vue frontend/src/views/workspace/WorkspaceSentimentView.vue frontend/src/router/routes.js frontend/src/config/navigation.js
git commit -m "feat(platform): add sentiment analysis scenario"
```

---

## Execution Order

Implement in this order:

1. Task 1: Dataset management
2. Task 2: Versioning and provenance
3. Task 3: Dataset-aware RAG and history/export
4. Task 4: Risk analytics and export
5. Task 5: Evaluation comparisons
6. Task 6: Fine-tune registry
7. Task 7: Task visibility and audit
8. Task 8: Sentiment analysis

## Phase Gates

Do not begin the next phase until the current one satisfies all of:

- backend tests for touched apps pass
- frontend tests pass
- the new page/API is reachable through existing navigation or route structure
- the feature can be described in one paragraph without caveats like “UI exists but backend is fake”

## Acceptance Checklist

- [ ] Knowledgebase is dataset-centric, not just document-centric
- [ ] Documents have provenance and version history
- [ ] QA can be scoped to dataset-aware retrieval
- [ ] Standalone history is fully functional and exportable
- [ ] Risk workflow includes analytics and export
- [ ] Evaluation supports baseline/RAG/fine-tuned comparisons
- [ ] Fine-tune lineage is recorded in-platform
- [ ] Admin dashboard exposes task and audit visibility
- [ ] Exactly one new scenario is added, and it reuses the existing platform foundation
