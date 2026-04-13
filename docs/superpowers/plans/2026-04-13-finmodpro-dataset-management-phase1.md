# FinModPro Dataset Management Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dataset management as the new root concept for the knowledgebase so documents, retrieval, and later evaluation/fine-tune workflows can be organized around explicit datasets instead of a flat document list.

**Architecture:** Keep dataset management inside the existing `knowledgebase` app. Introduce a lightweight `Dataset` model plus a nullable `dataset` foreign key on `Document`, then extend current document APIs and the knowledgebase UI to support dataset-scoped listing, upload, and selection. Do not introduce document versioning, complex sharing rules, or cross-app refactors in this phase.

**Tech Stack:** Django, Django ORM, existing JWT/RBAC permission layer, Vue 3, existing knowledgebase API/UI modules, Django test runner, Node test runner

---

## Scope

### In Scope

- Dataset entity creation and listing
- Document-to-dataset association
- Dataset-scoped document listing
- Uploading a document into the active dataset
- Displaying dataset information in the knowledgebase UI
- Minimal dataset-aware retrieval filter plumbing for future use

### Out of Scope

- Document version management
- Data lineage graph
- Dataset collaboration or team sharing model
- Dataset deletion and archival workflow
- Admin-only dataset governance console
- Fine-tune dataset preparation
- Sentiment analysis

## Phase Boundary Decisions

To avoid implementation drift, this phase locks the following decisions:

- `Dataset` is an application-level entity stored inside `knowledgebase`, not a new Django app.
- Datasets are visible to authenticated users who already have document viewing access.
- Dataset creation is allowed to users who can upload documents.
- Dataset selection happens in the existing workspace knowledge page, not a new admin page.
- Existing document APIs remain valid; they are extended, not replaced.
- A document may belong to zero or one dataset in this phase.
- If no dataset is selected, the knowledgebase page falls back to the current all-visible-documents behavior.

## File Structure

- `backend/knowledgebase/models.py`
  - Add `Dataset` and add `dataset` FK to `Document`.
- `backend/knowledgebase/services/dataset_service.py`
  - Add dataset create/list/detail/serialize helpers.
- `backend/knowledgebase/controllers/dataset_controller.py`
  - Add API views for dataset management.
- `backend/knowledgebase/services/document_service.py`
  - Extend upload/list/detail serialization and filtering to include dataset.
- `backend/knowledgebase/urls.py`
  - Mount dataset routes.
- `backend/knowledgebase/tests.py`
  - Add dataset creation/list/filter tests and document association tests.
- `frontend/src/api/knowledgebase.js`
  - Add dataset list/create calls and dataset-aware document listing/upload calls.
- `frontend/src/components/KnowledgeBase.vue`
  - Add active dataset selection, dataset creation entry, and scoped document list behavior.
- `frontend/src/views/workspace/WorkspaceKnowledgeView.vue`
  - Update page copy if necessary to reflect dataset-centered workflow.
- `frontend/src/lib/__tests__/knowledgebase-actions.test.js`
  - Add small frontend helper coverage if a dataset selection helper is introduced.

## API Contract

### Dataset list

`GET /api/knowledgebase/datasets`

Response:

```json
{
  "datasets": [
    {
      "id": 1,
      "name": "2025 年报数据集",
      "description": "用于年报问答与风险提取",
      "owner": {
        "id": 2,
        "username": "alice",
        "email": "alice@example.com"
      },
      "document_count": 4,
      "created_at": "2026-04-13T10:00:00+08:00",
      "updated_at": "2026-04-13T10:10:00+08:00"
    }
  ],
  "total": 1
}
```

### Dataset create

`POST /api/knowledgebase/datasets`

Request:

```json
{
  "name": "2025 年报数据集",
  "description": "用于年报问答与风险提取"
}
```

Response:

```json
{
  "dataset": {
    "id": 1,
    "name": "2025 年报数据集",
    "description": "用于年报问答与风险提取",
    "owner": {
      "id": 2,
      "username": "alice",
      "email": "alice@example.com"
    },
    "document_count": 0,
    "created_at": "2026-04-13T10:00:00+08:00",
    "updated_at": "2026-04-13T10:00:00+08:00"
  }
}
```

### Dataset detail

`GET /api/knowledgebase/datasets/<id>`

Response:

```json
{
  "dataset": {
    "id": 1,
    "name": "2025 年报数据集",
    "description": "用于年报问答与风险提取",
    "owner": {
      "id": 2,
      "username": "alice",
      "email": "alice@example.com"
    },
    "document_count": 4,
    "created_at": "2026-04-13T10:00:00+08:00",
    "updated_at": "2026-04-13T10:10:00+08:00"
  }
}
```

### Extended document list

`GET /api/knowledgebase/documents?dataset_id=1`

Add dataset summary to each document:

```json
{
  "id": 11,
  "title": "2025Q1 风险纪要",
  "dataset": {
    "id": 1,
    "name": "2025 年报数据集"
  }
}
```

### Extended document upload

`POST /api/knowledgebase/documents`

Multipart field additions:

- `dataset_id`

Behavior:

- if `dataset_id` is present, the uploaded document is attached to that dataset
- if absent, behavior remains backward compatible

## Permissions

Use existing permission boundaries instead of inventing new ones:

- list datasets: requires current document-view access path
- create dataset: requires `auth.upload_document`
- dataset detail: requires current document-view access path

Do not introduce new custom permissions in this phase unless existing permissions prove insufficient.

## Data Model Decision

Add the following model in `backend/knowledgebase/models.py`:

```python
class Dataset(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_datasets",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
```

Extend `Document`:

```python
dataset = models.ForeignKey(
    Dataset,
    related_name="documents",
    on_delete=models.SET_NULL,
    blank=True,
    null=True,
)
```

## UI Behavior

The knowledgebase page should support:

- dataset dropdown or segmented selector near the page toolbar
- default state:
  - `全部文档`
- create-dataset action:
  - small modal or inline panel
- upload flow:
  - uploads into the currently selected dataset when one is active
- list rows:
  - show dataset name when available
- detail panel:
  - show dataset name

Do not redesign the whole page. Keep the current layout and add dataset behavior incrementally.

## Task 1: Add failing backend tests for dataset behavior

**Files:**
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Add a test for dataset creation and listing**

Add a Django test that:

- authenticates as an admin-capable uploader
- posts to `/api/knowledgebase/datasets`
- verifies the dataset is returned by `/api/knowledgebase/datasets`

Example shape:

```python
def test_dataset_create_and_list_flow(self):
    create_response = self.client.post(
        "/api/knowledgebase/datasets",
        data=json.dumps({"name": "2025 年报数据集", "description": "用于年报问答"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
    )

    self.assertEqual(create_response.status_code, 201)
    list_response = self.client.get(
        "/api/knowledgebase/datasets",
        HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
    )
    self.assertEqual(list_response.status_code, 200)
```

- [ ] **Step 2: Add a test for dataset-scoped document filtering**

Create one document in dataset A and one in dataset B, then assert:

```python
response = self.client.get(
    "/api/knowledgebase/documents?dataset_id=1",
    HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
)
```

returns only dataset A documents.

- [ ] **Step 3: Add a permission test for dataset creation**

Assert a `member` user without upload permission gets `403` on dataset creation.

- [ ] **Step 4: Run the backend tests and confirm failure**

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
```

Expected: FAIL because dataset model/routes/services do not exist yet

## Task 2: Implement backend dataset model and service layer

**Files:**
- Modify: `backend/knowledgebase/models.py`
- Create: `backend/knowledgebase/services/dataset_service.py`

- [ ] **Step 1: Add the `Dataset` model and `Document.dataset` foreign key**

Update `backend/knowledgebase/models.py` with the agreed model shapes and create a migration.

- [ ] **Step 2: Add dataset serialization helpers**

In `dataset_service.py`, add:

```python
def serialize_dataset(dataset): ...
def list_datasets_for_user(user): ...
def create_dataset(*, user, name, description=""): ...
def get_dataset_for_user(user, dataset_id): ...
```

Include `document_count` in serialized output.

- [ ] **Step 3: Add migration files**

Run:

```bash
cd backend && python manage.py makemigrations knowledgebase
```

Expected: a migration file adding `Dataset` and `Document.dataset`

- [ ] **Step 4: Run model-level verification**

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
```

Expected: still failing, but now for missing controller/routes integration rather than missing models

## Task 3: Add backend dataset APIs and document filtering

**Files:**
- Create: `backend/knowledgebase/controllers/dataset_controller.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/urls.py`

- [ ] **Step 1: Add dataset controller functions**

Implement:

```python
@require_GET
@permission_required("auth.view_document")
def dataset_list_view(request): ...

@csrf_exempt
@require_POST
@permission_required("auth.upload_document")
def dataset_create_view(request): ...

@require_GET
@permission_required("auth.view_document")
def dataset_detail_view(request, dataset_id): ...
```

- [ ] **Step 2: Extend document service for dataset filtering**

In `document_service.py`:

- allow dataset filtering in document list query
- include dataset summary in serialized document output
- support `dataset_id` during upload

Add validation:

- invalid `dataset_id` returns `400`
- unknown `dataset_id` returns `400` or `404`, but pick one and keep it consistent

- [ ] **Step 3: Mount the dataset routes**

Add to `backend/knowledgebase/urls.py`:

```python
path("datasets", dataset_list_create_view, name="knowledgebase-dataset-list-create")
path("datasets/<int:dataset_id>", dataset_detail_view, name="knowledgebase-dataset-detail")
```

Use either separate views or a combined GET/POST view consistent with the current controller style.

- [ ] **Step 4: Run the knowledgebase test suite**

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
```

Expected: PASS for the new dataset behavior

## Task 4: Add frontend dataset API support

**Files:**
- Modify: `frontend/src/api/knowledgebase.js`

- [ ] **Step 1: Add dataset fetch and create methods**

Extend `kbApi` with:

```js
async listDatasets() { ... }
async createDataset(payload) { ... }
```

Normalize dataset payloads into:

```js
{
  id,
  name,
  description,
  ownerName,
  documentCount,
  createdAt,
  updatedAt,
}
```

- [ ] **Step 2: Add dataset-aware document methods**

Extend:

- `listDocuments({ datasetId })`
- `uploadDocument(file, { datasetId })`

Keep backward compatibility so current callers without dataset args still work.

- [ ] **Step 3: Add or extend a small helper test if a normalization helper is extracted**

Run:

```bash
cd frontend && node --test src/lib/__tests__/knowledgebase-actions.test.js
```

Expected: PASS

## Task 5: Add dataset selection and creation to the knowledgebase UI

**Files:**
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Modify: `frontend/src/views/workspace/WorkspaceKnowledgeView.vue`

- [ ] **Step 1: Add failing UI wiring check**

Before implementing, verify the current component does not yet contain dataset controls.

Run:

```bash
cd frontend && rg -n "dataset|数据集" src/components/KnowledgeBase.vue
```

Expected: no dataset-specific management controls

- [ ] **Step 2: Add active dataset state and loading flow**

Inside `KnowledgeBase.vue`, add:

- `datasets`
- `activeDatasetId`
- dataset load on mount
- dataset-aware document reload when selection changes

- [ ] **Step 3: Add dataset creation interaction**

Add one compact create flow:

- inline form, drawer, or dialog

The first version only needs:

- dataset name
- description

Do not overbuild with tags, access levels, or lifecycle states.

- [ ] **Step 4: Show dataset context in list/detail**

Update the UI so users can see:

- active dataset filter
- each document’s dataset
- selected document dataset in detail view

- [ ] **Step 5: Update view copy if needed**

Adjust `WorkspaceKnowledgeView.vue` hero/subtitle only if it improves clarity around dataset-centered knowledge management.

- [ ] **Step 6: Run frontend verification**

Run:

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: both pass

## Task 6: Add final slice verification and handoff notes

**Files:**
- Modify: `docs/platform-finish-direction.md` only if the phase scope needs correction
- Modify: `docs/superpowers/plans/2026-04-13-finmodpro-platform-finish.md` only if the completed phase changes later sequencing

- [ ] **Step 1: Run combined verification**

Run:

```bash
cd backend && python manage.py test knowledgebase -v 2
cd frontend && npm test
cd frontend && npm run build
```

Expected:

- backend knowledgebase suite passes
- frontend tests pass
- frontend build succeeds

- [ ] **Step 2: Confirm acceptance criteria**

Check all:

- datasets can be created
- datasets can be listed
- documents can be attached to datasets
- document list can be filtered by dataset
- knowledgebase UI supports active dataset selection
- upload respects active dataset
- no unrelated route or module regressions appear

- [ ] **Step 3: Commit**

```bash
git add backend/knowledgebase frontend/src/api/knowledgebase.js frontend/src/components/KnowledgeBase.vue frontend/src/views/workspace/WorkspaceKnowledgeView.vue docs/superpowers/plans/2026-04-13-finmodpro-dataset-management-phase1.md
git commit -m "feat(platform): add phase-1 dataset management"
```

---

## Acceptance Checklist

- [ ] `Dataset` exists in the knowledgebase domain model
- [ ] `Document` can reference a dataset
- [ ] Dataset APIs are available and permission-checked
- [ ] Document APIs are dataset-aware while staying backward compatible
- [ ] Workspace knowledgebase page can create/select datasets
- [ ] Upload and list flows respect active dataset context
- [ ] Backend knowledgebase tests pass
- [ ] Frontend tests and build pass

## Follow-up After This Phase

Only after this phase is complete should development move to:

1. Document versioning and provenance
2. Dataset-aware chat history and export
3. Dataset-aware evaluation and fine-tune data organization
