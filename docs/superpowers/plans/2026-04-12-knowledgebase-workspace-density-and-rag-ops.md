# Knowledgebase Workspace Density And RAG Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the workspace knowledgebase page into a denser document-operations console with explicit filters, pagination, chunk inspection, batch re-ingest and delete actions, clearer failure handling, and a preview-driven detail workflow.

**Architecture:** Keep the existing `/workspace/knowledge` route and the current Django knowledgebase domain model, but expand the backend with filtered list, chunk, batch ingest, and batch delete endpoints. On the frontend, split the oversized `KnowledgeBase.vue` into a state container plus focused presentational components, and move the testable UI state into pure JS helpers so the current Node test stack can verify most behavior without adding a browser test harness.

**Tech Stack:** Django 5, RBAC permission seeding, Vue 3, Element Plus dialog primitives already present in shared CSS, Node test runner, Vite build

---

## File map

- Modify: `backend/rbac/services/rbac_service.py` — add `delete_document` permission and role assignments
- Modify: `backend/rbac/tests.py` — assert delete permission seeding
- Modify: `backend/knowledgebase/controllers/__init__.py` — export new views
- Modify: `backend/knowledgebase/controllers/document_controller.py` — parse list query params
- Create: `backend/knowledgebase/controllers/chunk_controller.py` — document chunk detail endpoint
- Create: `backend/knowledgebase/controllers/batch_controller.py` — batch ingest and batch delete endpoints
- Modify: `backend/knowledgebase/urls.py` — register chunk and batch routes
- Modify: `backend/knowledgebase/services/document_service.py` — filtering, pagination, chunk serialization, batch ops, delete cleanup
- Modify: `backend/knowledgebase/services/vector_service.py` — delete document vectors
- Modify: `backend/knowledgebase/tests.py` — list, chunks, batch ingest, batch delete, cleanup coverage
- Modify: `frontend/src/api/knowledgebase.js` — paginated list, chunks, batch ingest, batch delete normalization
- Modify: `frontend/src/lib/knowledgebase-actions.js` — row action derivation and retry/delete affordances
- Modify: `frontend/src/lib/__tests__/knowledgebase-actions.test.js` — row action coverage
- Create: `frontend/src/lib/knowledgebase-workspace.js` — query building, batch summaries, preview/chunk UI state helpers
- Create: `frontend/src/lib/__tests__/knowledgebase-workspace.test.js` — helper tests for pagination, preview, and batch summaries
- Modify: `frontend/src/components/KnowledgeBase.vue` — become orchestration container only
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseToolbar.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseTable.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseDetailPanel.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBasePreviewModal.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseChunksPanel.vue`

## Task 1: Add filtered list pagination and chunk inspection endpoints

**Files:**
- Modify: `backend/knowledgebase/tests.py`
- Modify: `backend/knowledgebase/controllers/document_controller.py`
- Create: `backend/knowledgebase/controllers/chunk_controller.py`
- Modify: `backend/knowledgebase/controllers/__init__.py`
- Modify: `backend/knowledgebase/urls.py`
- Modify: `backend/knowledgebase/services/document_service.py`

- [ ] **Step 1: Write failing backend tests for list filters, pagination, and chunk inspection**

Add tests like the following to `backend/knowledgebase/tests.py`:

```python
    def test_document_list_filters_and_paginates_results(self):
        old_doc = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("old.txt", b"old note", content_type="text/plain"),
            title="Old note",
            source_date="2026-03-01",
            uploaded_by=self.user,
        )
        fresh_doc = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("fresh.txt", b"cash flow stable", content_type="text/plain"),
            title="Liquidity memo",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        enqueue_document_ingestion(fresh_doc)
        old_doc.status = Document.STATUS_FAILED
        old_doc.error_message = "解析失败"
        old_doc.save(update_fields=["status", "error_message", "updated_at"])

        response = self.client.get(
            "/api/knowledgebase/documents",
            {"q": "liquidity", "status": "indexed", "time_range": "7d", "page": 1, "page_size": 1},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 1)
        self.assertEqual(payload["total_pages"], 1)
        self.assertEqual(payload["documents"][0]["title"], "Liquidity memo")

    def test_document_chunks_endpoint_returns_chunk_rows(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "chunks.txt",
                b"alpha beta gamma delta epsilon zeta eta theta",
                content_type="text/plain",
            ),
            title="Chunk source",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        enqueue_document_ingestion(document)

        response = self.client.get(
            f"/api/knowledgebase/documents/{document.id}/chunks",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("chunks", payload)
        self.assertGreaterEqual(len(payload["chunks"]), 1)
        self.assertEqual(payload["chunks"][0]["chunk_index"], 0)
        self.assertIn("vector_id", payload["chunks"][0])
        self.assertIn("content", payload["chunks"][0])
```

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
cd /root/finmodpro/backend
python manage.py test \
  knowledgebase.tests.KnowledgebaseApiTests.test_document_list_filters_and_paginates_results \
  knowledgebase.tests.KnowledgebaseApiTests.test_document_chunks_endpoint_returns_chunk_rows
```

Expected: FAIL because the list response does not yet paginate or filter, and `/chunks` does not exist.

- [ ] **Step 3: Implement filtered and paginated document listing in the service layer**

Update `backend/knowledgebase/services/document_service.py` with focused helpers:

```python
from math import ceil
from django.utils import timezone
from datetime import timedelta


def _normalize_page(value, *, default):
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return default


def _filter_documents(queryset, *, q="", status="all", time_range="all"):
    keyword = (q or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(filename__icontains=keyword)
            | Q(uploaded_by__username__icontains=keyword)
            | Q(uploaded_by__email__icontains=keyword)
        )

    normalized_status = str(status or "all").lower()
    if normalized_status == "indexed":
        queryset = queryset.filter(status=Document.STATUS_INDEXED)
    elif normalized_status == "failed":
        queryset = queryset.filter(status=Document.STATUS_FAILED)
    elif normalized_status == "processing":
        queryset = queryset.filter(
            Q(status__in=[Document.STATUS_PARSED, Document.STATUS_CHUNKED])
            | Q(ingestion_tasks__status__in=[IngestionTask.STATUS_QUEUED, IngestionTask.STATUS_RUNNING])
        ).distinct()

    normalized_time_range = str(time_range or "all").lower()
    if normalized_time_range in {"7d", "30d"}:
        cutoff = timezone.now() - timedelta(days=7 if normalized_time_range == "7d" else 30)
        queryset = queryset.filter(created_at__gte=cutoff)

    return queryset


def build_document_list_response(user, *, q="", status="all", time_range="all", page=1, page_size=10):
    queryset = _filter_documents(
        get_visible_documents_queryset(user),
        q=q,
        status=status,
        time_range=time_range,
    )
    total = queryset.count()
    safe_page_size = min(max(int(page_size), 1), 50)
    safe_page = _normalize_page(page, default=1)
    total_pages = ceil(total / safe_page_size) if total else 0
    start = (safe_page - 1) * safe_page_size
    stop = start + safe_page_size
    documents = [serialize_document(document) for document in queryset[start:stop]]
    return {
        "documents": documents,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
    }
```

- [ ] **Step 4: Implement chunk serialization and the chunk endpoint**

Add chunk helpers and a dedicated controller:

```python
def serialize_chunk(chunk):
    metadata = chunk.metadata or {}
    return {
        "id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "vector_id": chunk.vector_id or "",
        "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
        "metadata": metadata,
        "created_at": chunk.created_at.isoformat(),
    }


def build_document_chunks_response(document):
    return {
        "document_id": document.id,
        "chunks": [serialize_chunk(chunk) for chunk in document.chunks.order_by("chunk_index")],
    }
```

```python
@require_GET
@permission_required("auth.view_document")
def document_chunks_view(request, document_id):
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)

    return JsonResponse(build_document_chunks_response(document))
```

Register the route in `backend/knowledgebase/urls.py`:

```python
path(
    "documents/<int:document_id>/chunks",
    document_chunks_view,
    name="knowledgebase-document-chunks",
),
```

Update `document_list_create_view()` to pass query params into `build_document_list_response()`:

```python
return JsonResponse(
    build_document_list_response(
        request.user,
        q=request.GET.get("q", ""),
        status=request.GET.get("status", "all"),
        time_range=request.GET.get("time_range", "all"),
        page=request.GET.get("page", 1),
        page_size=request.GET.get("page_size", 10),
    )
)
```

- [ ] **Step 5: Run the targeted backend tests to verify they pass**

Run:

```bash
cd /root/finmodpro/backend
python manage.py test \
  knowledgebase.tests.KnowledgebaseApiTests.test_document_list_filters_and_paginates_results \
  knowledgebase.tests.KnowledgebaseApiTests.test_document_chunks_endpoint_returns_chunk_rows
```

Expected: PASS.

- [ ] **Step 6: Commit the backend list and chunk work**

Run:

```bash
git add backend/knowledgebase/controllers/__init__.py \
  backend/knowledgebase/controllers/chunk_controller.py \
  backend/knowledgebase/controllers/document_controller.py \
  backend/knowledgebase/services/document_service.py \
  backend/knowledgebase/tests.py \
  backend/knowledgebase/urls.py
git commit -m "feat(knowledgebase): add filtered list and chunk endpoint"
```

## Task 2: Add batch ingest, batch delete, delete RBAC, and vector cleanup

**Files:**
- Modify: `backend/rbac/services/rbac_service.py`
- Modify: `backend/rbac/tests.py`
- Create: `backend/knowledgebase/controllers/batch_controller.py`
- Modify: `backend/knowledgebase/controllers/__init__.py`
- Modify: `backend/knowledgebase/urls.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/services/vector_service.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write failing tests for delete permission, batch ingest, and batch delete cleanup**

Add tests like:

```python
class RbacPermissionSeedTests(TestCase):
    def test_seed_roles_and_permissions_adds_delete_document_permission(self):
        groups = seed_roles_and_permissions()
        admin_permissions = set(groups[ROLE_ADMIN].permissions.values_list("codename", flat=True))
        member_permissions = set(groups[ROLE_MEMBER].permissions.values_list("codename", flat=True))

        self.assertIn("delete_document", admin_permissions)
        self.assertNotIn("delete_document", member_permissions)

    def test_batch_ingest_returns_accepted_and_skipped_counts(self):
        first = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("first.txt", b"first", content_type="text/plain"),
            title="First",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        second = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("second.txt", b"second", content_type="text/plain"),
            title="Second",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        running_task = IngestionTask.objects.create(
            document=second,
            status=IngestionTask.STATUS_RUNNING,
            current_step=IngestionTask.STEP_INDEXING,
        )

        response = self.client.post(
            "/api/knowledgebase/documents/batch/ingest",
            data=json.dumps({"document_ids": [first.id, second.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accepted_count"], 1)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["results"][1]["document_id"], second.id)
        self.assertEqual(payload["results"][1]["reason"], "已有进行中的摄取任务。")

    def test_batch_delete_removes_file_chunks_and_vectors(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("delete.txt", b"delete me", content_type="text/plain"),
            title="Delete me",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        enqueue_document_ingestion(document)
        original_path = document.file.path

        with patch.object(VectorService, "delete_document", return_value=None) as delete_vector_mock:
            response = self.client.post(
                "/api/knowledgebase/documents/batch/delete",
                data=json.dumps({"document_ids": [document.id]}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_count"], 1)
        self.assertFalse(Document.objects.filter(id=document.id).exists())
        self.assertFalse(os.path.exists(original_path))
        delete_vector_mock.assert_called_once_with(document.id)
```

- [ ] **Step 2: Run the targeted backend and RBAC tests to verify they fail**

Run:

```bash
cd /root/finmodpro/backend
python manage.py test \
  rbac.tests.RbacPermissionSeedTests.test_seed_roles_and_permissions_adds_delete_document_permission \
  knowledgebase.tests.KnowledgebaseApiTests.test_batch_ingest_returns_accepted_and_skipped_counts \
  knowledgebase.tests.KnowledgebaseApiTests.test_batch_delete_removes_file_chunks_and_vectors
```

Expected: FAIL because the permission and batch endpoints do not exist.

- [ ] **Step 3: Add delete RBAC and vector deletion primitives**

Update `backend/rbac/services/rbac_service.py`:

```python
CUSTOM_PERMISSION_DEFINITIONS = (
    ("view_dashboard", "Can view dashboard"),
    ("view_role", "Can view role"),
    ("assign_role", "Can assign role"),
    ("upload_document", "Can upload document"),
    ("view_document", "Can view document"),
    ("trigger_ingest", "Can trigger ingest"),
    ("delete_document", "Can delete document"),
    ("ask_financial_qa", "Can ask financial qa"),
    ("view_chat_session", "Can view chat session"),
    ("review_risk_event", "Can review risk event"),
    ("manage_model_config", "Can manage model config"),
    ("view_evaluation", "Can view evaluation"),
    ("run_evaluation", "Can run evaluation"),
    ("view_audit_log", "Can view audit log"),
)

ROLE_PERMISSION_MAP = {
    ROLE_SUPER_ADMIN: {
        "auth.view_dashboard",
        "auth.view_user",
        "auth.add_user",
        "auth.change_user",
        "auth.delete_user",
        "auth.view_role",
        "auth.assign_role",
        "auth.upload_document",
        "auth.view_document",
        "auth.trigger_ingest",
        "auth.delete_document",
        "auth.ask_financial_qa",
        "auth.view_chat_session",
        "auth.review_risk_event",
        "auth.manage_model_config",
        "auth.view_evaluation",
        "auth.run_evaluation",
        "auth.view_audit_log",
    },
    ROLE_ADMIN: {
        "auth.view_dashboard",
        "auth.view_user",
        "auth.add_user",
        "auth.change_user",
        "auth.view_role",
        "auth.upload_document",
        "auth.view_document",
        "auth.trigger_ingest",
        "auth.delete_document",
        "auth.ask_financial_qa",
        "auth.view_chat_session",
        "auth.review_risk_event",
        "auth.manage_model_config",
        "auth.view_evaluation",
        "auth.view_audit_log",
    },
    ROLE_MEMBER: {
        "auth.view_dashboard",
        "auth.view_document",
        "auth.ask_financial_qa",
    },
}
```

Update `backend/knowledgebase/services/vector_service.py`:

```python
    def delete_document(self, document_id):
        client = self.ensure_collection()
        client.delete(
            settings.MILVUS_COLLECTION_NAME,
            filter=f"document_id == {int(document_id)}",
        )
```

- [ ] **Step 4: Implement batch ingest, batch delete, and service cleanup**

Add service helpers shaped like:

```python
def _parse_document_ids(raw_ids):
    return [int(value) for value in raw_ids if str(value).strip()]


def batch_enqueue_document_ingestion(user, document_ids):
    results = []
    accepted_count = 0
    skipped_count = 0
    for document_id in _parse_document_ids(document_ids):
        try:
            document = get_document_for_user(user, document_id)
        except Document.DoesNotExist:
            skipped_count += 1
            results.append({"document_id": document_id, "status": "missing", "reason": "文档不存在。"})
            continue

        task, created = enqueue_document_ingestion(document)
        if created:
            accepted_count += 1
            results.append({"document_id": document_id, "status": "accepted", "task_id": task.id})
        else:
            skipped_count += 1
            results.append({"document_id": document_id, "status": "skipped", "reason": "已有进行中的摄取任务。"})

    return {"accepted_count": accepted_count, "skipped_count": skipped_count, "results": results}


def delete_document_with_vectors(document):
    VectorService().delete_document(document.id)
    file_field = document.file
    storage = file_field.storage
    file_name = file_field.name
    document.delete()
    if file_name and storage.exists(file_name):
        storage.delete(file_name)


def batch_delete_documents(user, document_ids):
    deleted_count = 0
    failed = []
    for document_id in _parse_document_ids(document_ids):
        try:
            document = get_document_for_user(user, document_id)
        except Document.DoesNotExist:
            failed.append({"document_id": document_id, "status": 404, "message": "文档不存在。"})
            continue

        try:
            delete_document_with_vectors(document)
            deleted_count += 1
        except Exception as exc:
            failed.append({"document_id": document_id, "status": 500, "message": str(exc) or "删除失败。"})

    return {
        "deleted_count": deleted_count,
        "failed_count": len(failed),
        "failures": failed,
    }
```

Add `batch_controller.py`:

```python
@csrf_exempt
@require_POST
@permission_required("auth.trigger_ingest")
def document_batch_ingest_view(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    return JsonResponse(batch_enqueue_document_ingestion(request.user, payload.get("document_ids") or []))


@csrf_exempt
@require_POST
@permission_required("auth.delete_document")
def document_batch_delete_view(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    return JsonResponse(batch_delete_documents(request.user, payload.get("document_ids") or []))
```

Register routes:

```python
path("documents/batch/ingest", document_batch_ingest_view, name="knowledgebase-document-batch-ingest"),
path("documents/batch/delete", document_batch_delete_view, name="knowledgebase-document-batch-delete"),
```

- [ ] **Step 5: Run the targeted backend and RBAC tests to verify they pass**

Run:

```bash
cd /root/finmodpro/backend
python manage.py test \
  rbac.tests.RbacPermissionSeedTests.test_seed_roles_and_permissions_adds_delete_document_permission \
  knowledgebase.tests.KnowledgebaseApiTests.test_batch_ingest_returns_accepted_and_skipped_counts \
  knowledgebase.tests.KnowledgebaseApiTests.test_batch_delete_removes_file_chunks_and_vectors
```

Expected: PASS.

- [ ] **Step 6: Commit the batch operations and cleanup work**

Run:

```bash
git add backend/knowledgebase/controllers/__init__.py \
  backend/knowledgebase/controllers/batch_controller.py \
  backend/knowledgebase/services/document_service.py \
  backend/knowledgebase/services/vector_service.py \
  backend/knowledgebase/tests.py \
  backend/knowledgebase/urls.py \
  backend/rbac/services/rbac_service.py \
  backend/rbac/tests.py
git commit -m "feat(knowledgebase): add batch ingest and delete workflows"
```

## Task 3: Add frontend knowledgebase helpers, API normalization, and unit coverage

**Files:**
- Create: `frontend/src/lib/knowledgebase-workspace.js`
- Create: `frontend/src/lib/__tests__/knowledgebase-workspace.test.js`
- Modify: `frontend/src/api/knowledgebase.js`
- Modify: `frontend/src/lib/knowledgebase-actions.js`
- Modify: `frontend/src/lib/__tests__/knowledgebase-actions.test.js`

- [ ] **Step 1: Write failing frontend helper tests for query state, preview state, and row actions**

Add tests to `frontend/src/lib/__tests__/knowledgebase-workspace.test.js`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildKnowledgebaseQuery,
  buildPreviewState,
  summarizeBatchResult,
} from '../knowledgebase-workspace.js';

test('buildKnowledgebaseQuery removes empty filters and keeps pagination', () => {
  assert.deepEqual(
    buildKnowledgebaseQuery({
      searchKeyword: 'liquidity',
      statusFilter: 'indexed',
      timeRange: '7d',
      page: 2,
      pageSize: 10,
    }),
    { q: 'liquidity', status: 'indexed', time_range: '7d', page: 2, page_size: 10 },
  );
});

test('buildPreviewState prefers extracted text and falls back to preview text', () => {
  assert.deepEqual(
    buildPreviewState({ extractedText: '', parsedTextPreview: 'short preview' }),
    { hasContent: true, body: 'short preview' },
  );
});

test('summarizeBatchResult reports partial failure details', () => {
  assert.match(
    summarizeBatchResult(
      { accepted_count: 2, skipped_count: 1, results: [{ document_id: 3, reason: '已有进行中的摄取任务。' }] },
      '重新入库',
    ),
    /成功 2 项，跳过 1 项/,
  );
});
```

Expand `frontend/src/lib/__tests__/knowledgebase-actions.test.js` with:

```js
import { getDocumentRowActions } from '../knowledgebase-actions.js';

test('failed document exposes retry and error row actions', () => {
  const actions = getDocumentRowActions({
    status: 'failed',
    processStep: { code: 'failed' },
    latestTask: { status: 'failed' },
    isSearchReady: false,
    processError: '解析失败',
  });

  assert.deepEqual(
    actions.map((item) => item.id),
    ['retry', 'view-error'],
  );
});
```

- [ ] **Step 2: Run the targeted frontend helper tests to verify they fail**

Run:

```bash
cd /root/finmodpro/frontend
node --test src/lib/__tests__/knowledgebase-workspace.test.js src/lib/__tests__/knowledgebase-actions.test.js
```

Expected: FAIL because the new helper file and row action API do not exist.

- [ ] **Step 3: Implement helper and API normalization logic**

Create `frontend/src/lib/knowledgebase-workspace.js` with pure helpers:

```js
export const buildKnowledgebaseQuery = ({
  searchKeyword = '',
  statusFilter = 'all',
  timeRange = 'all',
  page = 1,
  pageSize = 10,
}) => {
  const query = { page, page_size: pageSize };
  if (searchKeyword.trim()) query.q = searchKeyword.trim();
  if (statusFilter && statusFilter !== 'all') query.status = statusFilter;
  if (timeRange && timeRange !== 'all') query.time_range = timeRange;
  return query;
};

export const buildPreviewState = (document) => {
  const body = document?.extractedText || document?.parsedTextPreview || '';
  return {
    hasContent: body.trim().length > 0,
    body,
  };
};

export const summarizeBatchResult = (payload, label) => {
  const success = payload?.accepted_count ?? payload?.deleted_count ?? 0;
  const skipped = payload?.skipped_count ?? payload?.failed_count ?? 0;
  return `${label}完成：成功 ${success} 项，跳过/失败 ${skipped} 项。`;
};
```

Update `frontend/src/api/knowledgebase.js`:

```js
export const kbApi = {
  async listDocuments(params = {}) {
    const query = new URLSearchParams(buildKnowledgebaseQuery(params));
    const response = await apiConfig.fetchImpl(
      joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents?${query.toString()}`),
      { method: 'GET', headers: getHeaders(), auth: true },
    );
    const data = await parseResponse(response);
    const docs = Array.isArray(data.documents) ? data.documents : [];
    return {
      documents: docs.map((doc) => normalizeDocument(doc)),
      total: Number(data.total || 0),
      page: Number(data.page || 1),
      pageSize: Number(data.page_size || 10),
      totalPages: Number(data.total_pages || 0),
    };
  },

  async getDocumentChunks(documentId) {
    const response = await apiConfig.fetchImpl(
      joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents/${documentId}/chunks`),
      { method: 'GET', headers: getHeaders(), auth: true },
    );
    const data = await parseResponse(response);
    return (data.chunks || []).map((chunk) => ({
      id: chunk.id,
      chunkIndex: Number(chunk.chunk_index || 0),
      pageLabel: chunk.page_label || `chunk-${Number(chunk.chunk_index || 0) + 1}`,
      content: chunk.content || '',
      vectorId: chunk.vector_id || '',
      metadata: chunk.metadata || {},
    }));
  },

  async batchIngestDocuments(documentIds) {
    const response = await apiConfig.fetchImpl(
      joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents/batch/ingest'),
      {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ document_ids: documentIds }),
        auth: true,
      },
    );
    return parseResponse(response);
  },

  async batchDeleteDocuments(documentIds) {
    const response = await apiConfig.fetchImpl(
      joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents/batch/delete'),
      {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ document_ids: documentIds }),
        auth: true,
      },
    );
    return parseResponse(response);
  },
};
```

Update `frontend/src/lib/knowledgebase-actions.js`:

```js
export const getDocumentRowActions = (document) => {
  const actions = [];
  const ingestAction = getIngestionAction(document);
  if (ingestAction) {
    actions.push({ id: 'retry', label: ingestAction.label, emphasis: ingestAction.emphasis });
  }
  if (String(document?.processStep?.code || '').toLowerCase() === 'failed' && document?.processError) {
    actions.push({ id: 'view-error', label: '查看错误', emphasis: 'secondary' });
  }
  return actions;
};
```

- [ ] **Step 4: Run the targeted frontend helper tests to verify they pass**

Run:

```bash
cd /root/finmodpro/frontend
node --test src/lib/__tests__/knowledgebase-workspace.test.js src/lib/__tests__/knowledgebase-actions.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit the frontend helper groundwork**

Run:

```bash
git add frontend/src/api/knowledgebase.js \
  frontend/src/lib/knowledgebase-actions.js \
  frontend/src/lib/knowledgebase-workspace.js \
  frontend/src/lib/__tests__/knowledgebase-actions.test.js \
  frontend/src/lib/__tests__/knowledgebase-workspace.test.js
git commit -m "refactor(frontend): add knowledgebase workspace state helpers"
```

## Task 4: Split the knowledgebase page and rebuild the dense list workflow

**Files:**
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseToolbar.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseTable.vue`

- [ ] **Step 1: Write the failing orchestration tests for query and selection behavior**

Add tests to `frontend/src/lib/__tests__/knowledgebase-workspace.test.js`:

```js
import { buildNextSelection, buildSelectionAfterBatchDelete } from '../knowledgebase-workspace.js';

test('buildNextSelection keeps row selection separate from checkbox selection', () => {
  assert.deepEqual(
    buildNextSelection({
      selectedIds: [2],
      toggledId: 3,
    }),
    [2, 3],
  );
});

test('buildSelectionAfterBatchDelete removes deleted ids and preserves survivors', () => {
  assert.deepEqual(
    buildSelectionAfterBatchDelete([1, 2, 3], [2, 4]),
    [1, 3],
  );
});
```

- [ ] **Step 2: Run the targeted helper test to verify it fails**

Run:

```bash
cd /root/finmodpro/frontend
node --test src/lib/__tests__/knowledgebase-workspace.test.js
```

Expected: FAIL because the selection helpers do not exist yet.

- [ ] **Step 3: Expand the helper layer and rebuild the page container**

Add selection helpers:

```js
export const buildNextSelection = ({ selectedIds, toggledId }) => (
  selectedIds.includes(toggledId)
    ? selectedIds.filter((id) => id !== toggledId)
    : [...selectedIds, toggledId]
);

export const buildSelectionAfterBatchDelete = (selectedIds, deletedIds) => (
  selectedIds.filter((id) => !deletedIds.includes(id))
);
```

Refactor `frontend/src/components/KnowledgeBase.vue` into orchestration state only:

```vue
<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import KnowledgeBaseToolbar from './knowledgebase/KnowledgeBaseToolbar.vue';
import KnowledgeBaseTable from './knowledgebase/KnowledgeBaseTable.vue';
import KnowledgeBaseDetailPanel from './knowledgebase/KnowledgeBaseDetailPanel.vue';
import KnowledgeBasePreviewModal from './knowledgebase/KnowledgeBasePreviewModal.vue';
import {
  buildKnowledgebaseQuery,
  buildNextSelection,
  buildPreviewState,
  buildSelectionAfterBatchDelete,
  summarizeBatchResult,
} from '../lib/knowledgebase-workspace.js';

const items = ref([]);
const pagination = ref({ total: 0, page: 1, pageSize: 10, totalPages: 0 });
const searchKeyword = ref('');
const statusFilter = ref('all');
const timeRange = ref('all');
const selectedDocumentId = ref('');
const checkedDocumentIds = ref([]);
const isPreviewOpen = ref(false);

const fetchDocuments = async () => {
  const payload = await kbApi.listDocuments({
    searchKeyword: searchKeyword.value,
    statusFilter: statusFilter.value,
    timeRange: timeRange.value,
    page: pagination.value.page,
    pageSize: pagination.value.pageSize,
  });
  items.value = payload.documents;
  pagination.value = {
    total: payload.total,
    page: payload.page,
    pageSize: payload.pageSize,
    totalPages: payload.totalPages,
  };
};
</script>
```

Create `KnowledgeBaseToolbar.vue` with props/events for search, status, time range, and upload.

Create `KnowledgeBaseTable.vue` with:

```vue
<template>
  <div class="kb-table ui-card">
    <div class="kb-table__header">
      <label class="kb-checkbox">
        <input type="checkbox" :checked="allChecked" @change="$emit('toggle-all')" />
      </label>
      <span>文档</span>
      <span>上传者</span>
      <span>当前状态</span>
      <span>上传时间</span>
      <span>操作</span>
    </div>

    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="kb-table__row"
      :class="{ active: item.id === selectedDocumentId }"
      @click="$emit('select', item)"
    >
      <label class="kb-checkbox" @click.stop>
        <input
          type="checkbox"
          :checked="checkedIds.includes(item.id)"
          @change="$emit('toggle-row', item.id)"
        />
      </label>
      <div class="kb-table__title">
        <strong>{{ item.title }}</strong>
        <span :title="item.filename">{{ item.filename }}</span>
      </div>
      <div>{{ item.uploaderName }}</div>
      <div><span class="status-chip">{{ item.processStep.label }}</span></div>
      <div>{{ item.uploadTime }}</div>
      <div class="kb-table__actions">
        <button
          v-for="action in item.rowActions"
          :key="action.id"
          type="button"
          class="kb-link-btn"
          @click.stop="$emit('row-action', { item, action })"
        >
          {{ action.label }}
        </button>
      </div>
    </button>
  </div>
</template>
```

- [ ] **Step 4: Run the helper tests to verify selection and orchestration logic**

Run:

```bash
cd /root/finmodpro/frontend
node --test src/lib/__tests__/knowledgebase-workspace.test.js src/lib/__tests__/knowledgebase-actions.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit the list-density and orchestration split**

Run:

```bash
git add frontend/src/components/KnowledgeBase.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseToolbar.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseTable.vue \
  frontend/src/lib/knowledgebase-workspace.js \
  frontend/src/lib/__tests__/knowledgebase-workspace.test.js
git commit -m "refactor(frontend): rebuild knowledgebase table workflow"
```

## Task 5: Rebuild the detail panel, preview modal, chunks tab, and batch action bar

**Files:**
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseDetailPanel.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBasePreviewModal.vue`
- Create: `frontend/src/components/knowledgebase/KnowledgeBaseChunksPanel.vue`

- [ ] **Step 1: Add failing helper tests for preview empty states and chunk expansion state**

Extend `frontend/src/lib/__tests__/knowledgebase-workspace.test.js`:

```js
import {
  buildChunkExpansionState,
  buildEmptyDetailState,
} from '../knowledgebase-workspace.js';

test('buildEmptyDetailState returns the expected workspace prompt', () => {
  assert.deepEqual(buildEmptyDetailState(), {
    title: '请选择一个文档查看详情',
    detail: '左侧选择文档后，可查看处理进度、切块和错误信息。',
  });
});

test('buildChunkExpansionState toggles a chunk key idempotently', () => {
  assert.deepEqual(buildChunkExpansionState(['chunk-1'], 'chunk-2'), ['chunk-1', 'chunk-2']);
  assert.deepEqual(buildChunkExpansionState(['chunk-1'], 'chunk-1'), []);
});
```

- [ ] **Step 2: Run the helper test to verify it fails**

Run:

```bash
cd /root/finmodpro/frontend
node --test src/lib/__tests__/knowledgebase-workspace.test.js
```

Expected: FAIL because the new helpers do not exist yet.

- [ ] **Step 3: Implement detail, preview, and chunks presentation**

Add helper functions:

```js
export const buildEmptyDetailState = () => ({
  title: '请选择一个文档查看详情',
  detail: '左侧选择文档后，可查看处理进度、切块和错误信息。',
});

export const buildChunkExpansionState = (expandedIds, chunkId) => (
  expandedIds.includes(chunkId)
    ? expandedIds.filter((id) => id !== chunkId)
    : [...expandedIds, chunkId]
);
```

Create `KnowledgeBaseDetailPanel.vue` with tabs for `processing`, `chunks`, and `errors`:

```vue
<template>
  <div class="kb-detail ui-card">
    <template v-if="document">
      <header class="kb-detail__header">
        <div>
          <p class="eyebrow">文档详情</p>
          <h3>{{ document.title }}</h3>
          <p class="kb-detail__summary">{{ document.processResult }}</p>
        </div>
        <div class="kb-detail__actions">
          <button
            v-if="primaryAction"
            :class="primaryAction.emphasis === 'primary' ? 'kb-primary-btn' : 'kb-secondary-btn'"
            @click="$emit('ingest')"
          >
            {{ primaryAction.label }}
          </button>
          <button class="kb-secondary-btn" @click="$emit('preview')">查看预览</button>
          <button class="kb-secondary-btn" @click="$emit('open-original')">查看原文</button>
        </div>
      </header>

      <nav class="kb-detail__tabs">
        <button v-for="tab in tabs" :key="tab.id" @click="$emit('change-tab', tab.id)">{{ tab.label }}</button>
      </nav>
    </template>

    <div v-else class="kb-empty-state">
      <h4>{{ emptyState.title }}</h4>
      <p>{{ emptyState.detail }}</p>
    </div>
  </div>
</template>
```

Create `KnowledgeBasePreviewModal.vue`:

```vue
<template>
  <el-dialog :model-value="modelValue" title="文档预览" width="720px" @close="$emit('close')">
    <div v-if="previewState.hasContent" class="kb-preview-modal__body">
      <pre>{{ previewState.body }}</pre>
    </div>
    <div v-else class="kb-empty-state">
      <h4>当前暂无可预览文本</h4>
      <p>请先完成解析，或直接打开原文查看。</p>
    </div>
  </el-dialog>
</template>
```

Create `KnowledgeBaseChunksPanel.vue`:

```vue
<template>
  <div v-if="chunks.length" class="kb-chunks">
    <article v-for="chunk in chunks" :key="chunk.id" class="kb-chunk">
      <div class="kb-chunk__meta">
        <strong>{{ chunk.pageLabel }}</strong>
        <span>向量 {{ chunk.vectorId || '未写入' }}</span>
      </div>
      <p>{{ expandedIds.includes(chunk.id) ? chunk.content : `${chunk.content.slice(0, 180)}...` }}</p>
      <button type="button" class="kb-link-btn" @click="$emit('toggle-chunk', chunk.id)">
        {{ expandedIds.includes(chunk.id) ? '收起' : '展开' }}
      </button>
    </article>
  </div>
  <div v-else class="kb-empty-state">
    <h4>当前文档暂无切块数据</h4>
    <p>请等待入库完成，或重新发起处理任务。</p>
  </div>
</template>
```

Update `KnowledgeBase.vue` to:

- keep `selectedDocumentId` empty on first load
- fetch detail and chunks only after row selection
- open preview modal from `查看预览`
- show batch action bar only when `checkedDocumentIds.length > 0`
- call `kbApi.batchIngestDocuments()` and `kbApi.batchDeleteDocuments()` then refresh list

- [ ] **Step 4: Run the helper tests again, then build the frontend**

Run:

```bash
cd /root/finmodpro/frontend
node --test src/lib/__tests__/knowledgebase-workspace.test.js src/lib/__tests__/knowledgebase-actions.test.js
npm run build
```

Expected:
- helper tests PASS
- Vite build succeeds

- [ ] **Step 5: Commit the detail and batch UI work**

Run:

```bash
git add frontend/src/components/KnowledgeBase.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseChunksPanel.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseDetailPanel.vue \
  frontend/src/components/knowledgebase/KnowledgeBasePreviewModal.vue \
  frontend/src/lib/knowledgebase-workspace.js \
  frontend/src/lib/__tests__/knowledgebase-workspace.test.js
git commit -m "feat(frontend): upgrade knowledgebase detail and batch operations"
```

## Task 6: Run full verification and close the branch cleanly

**Files:**
- Verify: `backend/knowledgebase/tests.py`
- Verify: `backend/rbac/tests.py`
- Verify: `frontend/src/lib/__tests__/knowledgebase-actions.test.js`
- Verify: `frontend/src/lib/__tests__/knowledgebase-workspace.test.js`

- [ ] **Step 1: Run the full backend verification set**

Run:

```bash
cd /root/finmodpro/backend
python manage.py check
python manage.py test knowledgebase.tests rbac.tests
```

Expected:
- `System check identified no issues`
- knowledgebase and RBAC tests PASS

- [ ] **Step 2: Run the full frontend verification set**

Run:

```bash
cd /root/finmodpro/frontend
npm test
npm run build
```

Expected:
- all Node tests PASS
- production build succeeds

- [ ] **Step 3: Sanity-check the implemented workspace manually**

Verify in the browser:

```text
1. 知识库列表默认不选中首条，右侧显示空状态。
2. 文档列表每行只保留单行标题和简短次级信息。
3. 状态列不再显示长描述。
4. 搜索、状态筛选、时间筛选和分页联动正常。
5. 批量勾选后出现批量操作栏。
6. 查看预览打开弹层，不再默认铺开全文。
7. Chunks tab 能看到切块、vector_id 和展开/收起。
8. 失败文档可查看错误并重新入库。
```

- [ ] **Step 4: Create the final implementation commit**

Run:

```bash
git status --short
git add backend/rbac/services/rbac_service.py \
  backend/rbac/tests.py \
  backend/knowledgebase/controllers/__init__.py \
  backend/knowledgebase/controllers/batch_controller.py \
  backend/knowledgebase/controllers/chunk_controller.py \
  backend/knowledgebase/controllers/document_controller.py \
  backend/knowledgebase/services/document_service.py \
  backend/knowledgebase/services/vector_service.py \
  backend/knowledgebase/tests.py \
  backend/knowledgebase/urls.py \
  frontend/src/api/knowledgebase.js \
  frontend/src/components/KnowledgeBase.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseChunksPanel.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseDetailPanel.vue \
  frontend/src/components/knowledgebase/KnowledgeBasePreviewModal.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseTable.vue \
  frontend/src/components/knowledgebase/KnowledgeBaseToolbar.vue \
  frontend/src/lib/knowledgebase-actions.js \
  frontend/src/lib/knowledgebase-workspace.js \
  frontend/src/lib/__tests__/knowledgebase-actions.test.js \
  frontend/src/lib/__tests__/knowledgebase-workspace.test.js \
  docs/superpowers/specs/2026-04-12-knowledgebase-workspace-density-and-rag-ops-design.md \
  docs/superpowers/plans/2026-04-12-knowledgebase-workspace-density-and-rag-ops.md
git commit -m "feat(frontend): redesign knowledgebase workspace operations"
```

Expected: one clean feature commit after all verifications pass.
