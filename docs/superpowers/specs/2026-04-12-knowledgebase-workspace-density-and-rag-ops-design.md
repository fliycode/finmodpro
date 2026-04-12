# Knowledgebase Workspace Density And RAG Ops Design

## Goal

Rework the workspace knowledgebase page so it behaves like an operational document console instead of a loose document viewer: increase list density, remove wasted repeated copy, add explicit filtering and pagination, expose chunk inspection for RAG debugging, support batch actions, and surface failure handling without forcing users to read full extracted text inline.

## Problem Statement

The current knowledgebase page is functionally connected to the upload and ingest flow, but it still wastes attention and vertical space in ways that make routine operations harder than they should be:

1. The list repeats file information in the document column and shows long status helper text inside each row, making row height too large.
2. The overview title reads like an internal implementation note rather than a user-facing workspace heading.
3. The right-side detail panel spends too much space on sparse metadata cards and a full extracted-text block.
4. `查看预览` and `查看原文` exist, but the page still dumps extracted text inline, so the action model is unclear.
5. Search is overloaded to do status lookup that should be handled by explicit filters.
6. The page has no chunk inspection workflow, even though chunk quality is central to Milvus-backed RAG operations.
7. Batch actions, failure diagnostics, and pagination are missing, which will make the page degrade quickly as document volume grows.

The result is a page that technically exposes the pipeline but does not yet support efficient document governance or RAG debugging.

## Design Summary

The page will remain a single workspace screen with a left list and right detail panel, but it will shift to a denser operations-first layout. The left side becomes a selectable, paginated document table with checkbox-based batch actions, explicit status and time filters, and single-row document presentation. The right side becomes a compact detail console with tabs for processing details, chunk inspection, and error logs. Inline full extracted text is removed from the default layout; preview moves into an explicit modal launched from `查看预览`.

The backend will grow only where needed: chunk listing, paginated and filtered document listing, batch ingest, batch delete, and document deletion cleanup that also clears vector rows.

## Approach Options

### Option A: Pure Frontend Compression

Keep current APIs and only tighten the layout and copy.

Pros:
- Fastest delivery
- Low backend risk

Cons:
- No chunk inspection
- No real batch workflow
- No server-backed pagination or filter semantics
- Does not solve the page's operational gaps

### Option B: Workspace Console Upgrade

Keep the current route and overall split layout, but add the missing operational capabilities with small targeted backend changes.

Pros:
- Solves the reported UI density issues
- Adds the minimum RAG-debugging and operations features users actually need
- Preserves the current workspace mental model

Cons:
- Requires coordinated frontend and backend changes
- Broader test surface than a layout-only pass

### Option C: Split Detail Into Separate Routes

Break the page into list, document detail, and chunk detail sub-pages.

Pros:
- Highest long-term extensibility
- Cleaner deep-linking for future workflows

Cons:
- Too much churn for the current repo structure
- Adds navigation overhead before the current page earns it

### Recommendation

Use Option B. It addresses the concrete usability problems without over-expanding the workspace IA.

## Information Architecture

### 1. Workspace Hero And Overview

The workspace view already provides the outer page hero (`知识检索与文档管理`). Inside the knowledgebase module, replace the current internal headline `上传、处理、入库三段状态分离展示` with a business-facing title such as `文档处理状态监控`.

Keep one short supporting sentence that explains the ingest lifecycle in user language:

- uploaded: file saved
- processing: parsing, chunking, indexing in progress
- indexed: searchable in Milvus-backed retrieval

The four summary stats remain:

- 文档总数
- 处理中
- 已入库
- 失败

These are still useful as quick workload markers and do not need a larger redesign in this iteration.

### 2. Toolbar

The toolbar will become:

- search input
- status filter
- time-range filter
- upload button

The search field remains free text and should target:

- title
- filename
- uploader

Status filtering should no longer rely on users typing status words into search.

Initial status options:

- 全部
- 处理中
- 已入库
- 失败

Initial time options:

- 全部时间
- 近 7 天
- 近 30 天

### 3. Left Document Table

The list becomes a denser data table with these columns:

- checkbox
- 文档
- 上传者
- 当前状态
- 上传时间
- 操作

Document column rules:

- Title is the main line.
- Secondary text is reduced to one compact line only.
- Prefer showing the original filename in muted text.
- If a path or ID is needed later, use tooltip treatment rather than reserving another row by default.

Status column rules:

- Show only the status chip in-row.
- Remove the long status helper sentence from each row.
- Detailed process messaging moves to the right detail panel.

Action column rules:

- Show row-level `重新入库` when appropriate.
- If failed, also show `查看错误`.

Selection rules:

- Row click selects the document.
- Checkbox click only affects selection for batch actions and does not replace the active detail selection.

### 4. Right Detail Panel

The right panel keeps its current role but becomes more compact and more operational:

- default empty state when no document is selected
- title, status chip, and primary action in the header
- compact metadata grid or list instead of tall single-purpose cards
- tabs for `处理详情`, `Chunks`, `错误日志`

Metadata should include:

- 上传者
- 归属人
- 上传时间
- 更新时间
- 切块数量
- 向量数量

The current full-height extracted-text block is removed from the main panel.

### 5. Preview Model

`查看预览` becomes the explicit place to inspect text content. The first iteration uses a modal rather than a new route.

Preview behavior:

- If parsed preview text exists, show it in the modal.
- If full parsed text is available from the detail payload, the modal may show it with truncation controls.
- If no previewable text exists, render a clear empty state in the modal instead of showing an error toast.

`查看原文` keeps opening the original file URL in a new tab.

## Interaction Design

### Selection And Empty State

Do not auto-select the first document on initial page load. The right panel should explicitly show:

`请选择一个文档查看详情。`

This avoids stale or accidental detail state and matches the user's expectation for a master-detail workspace.

### Polling

Keep polling only while there are active processing documents on the current page.

Polling behavior:

- refresh current list page
- preserve active document selection if still visible
- refresh the selected document detail if one is active
- stop polling when no documents are in queued/parsing/chunking/indexing states

### Error Visibility

Failed documents should expose failure reasons in two places:

- quick access from the table action column via `查看错误`
- dedicated `错误日志` tab in the detail panel

The detail panel should favor the latest ingestion task error when present, then fall back to the document-level error.

## RAG Operations Features

### 1. Chunks Inspection

Add a `Chunks` tab in the right detail panel backed by a dedicated endpoint.

For each chunk, show:

- chunk id
- chunk index
- page label
- truncated content with expand/collapse
- vector id
- metadata summary when useful

Do not show raw embedding arrays. They are noisy, expensive to render, and not helpful for routine debugging.

The UX goal is to answer:

- Was the document split correctly?
- How many chunks were produced?
- Was each chunk written to the vector store?

### 2. Failure Retry

Keep using the existing ingest endpoint for retry. The UI should simply surface it more clearly:

- row-level retry in the table
- primary retry in the detail header
- retry remains available for already indexed documents as `重新入库`

### 3. Batch Actions

Add checkbox-driven batch operations with a compact action bar shown only when one or more rows are selected.

Initial actions:

- 批量重新入库
- 批量删除

Deletion is worth including in the first iteration because batch selection without a removal workflow would feel incomplete for a document operations page.

### 4. Pagination

Use server-backed pagination rather than virtual scrolling in this iteration.

Reason:

- The page already behaves like a business table.
- Pagination is easier to reason about with filters and batch actions.
- It keeps the backend query surface honest and predictable.

Initial page size may be 10 or 20; use the existing visual density to decide, but the first screen should show materially more rows than today.

## Backend API Design

### 1. Filtered And Paginated Document List

Extend `GET /api/knowledgebase/documents` with query params:

- `q`
- `status`
- `time_range`
- `page`
- `page_size`

Status semantics:

- `all`: no filter
- `processing`: queued, parsing, chunking, indexing, or running equivalents
- `indexed`
- `failed`

Time-range semantics:

- `all`
- `7d`
- `30d`

Response shape becomes:

```json
{
  "documents": [],
  "total": 0,
  "page": 1,
  "page_size": 10,
  "total_pages": 0
}
```

### 2. Document Chunks Endpoint

Add:

`GET /api/knowledgebase/documents/<id>/chunks`

Response should be scoped to the same document-visibility rules as detail access and return only chunk-inspection data, not full document detail.

### 3. Batch Ingest Endpoint

Add:

`POST /api/knowledgebase/documents/batch/ingest`

Request body:

```json
{
  "document_ids": [1, 2, 3]
}
```

Response should report:

- accepted count
- skipped count
- per-document outcome summary when needed

### 4. Batch Delete Endpoint

Add:

`POST /api/knowledgebase/documents/batch/delete`

Request body:

```json
{
  "document_ids": [1, 2, 3]
}
```

The response should report success and failure counts plus per-document failures so the frontend can show partial-result feedback.

### 5. Delete Permission

Current RBAC includes `upload_document`, `view_document`, and `trigger_ingest`, but no delete permission. Add:

- `auth.delete_document`

Grant it to:

- super_admin
- admin

Do not grant it to `member`.

## Backend Data And Cleanup Rules

### Delete Behavior

Deleting a document must clean up:

- the `Document` row
- related `DocumentChunk` rows
- related `IngestionTask` rows through cascade
- uploaded file from storage
- vector rows for the document from the vector store

If vector cleanup fails, the API should return the deletion as failed for that document rather than silently leaving orphaned vector data.

### Serialization

List responses should stay lightweight.

Detail responses should continue returning:

- process summary
- preview text
- task metadata

But they should not expand to include all chunks inline; chunk retrieval belongs to the dedicated endpoint.

## Frontend Component Boundaries

To keep the page maintainable, split the current large `KnowledgeBase.vue` into focused units.

Recommended components:

- `KnowledgeBaseToolbar`
- `KnowledgeBaseTable`
- `KnowledgeBaseDetailPanel`
- `KnowledgeBasePreviewModal`
- `KnowledgeBaseChunksPanel`

Support logic can remain in:

- `frontend/src/api/knowledgebase.js`
- `frontend/src/lib/knowledgebase-actions.js`

This split should follow existing workspace patterns and keep styling local to the owning components where possible.

## Error Handling

### Frontend

- Missing preview content: show modal empty state, not an error toast
- Missing original URL: show current error toast
- Batch partial failure: show exact success and failure counts
- Empty chunk list: show `当前文档暂无切块数据。`

### Backend

- Unauthorized delete or ingest attempts return 403
- Invisible documents still return 404 at detail, chunks, and batch per-document resolution boundaries
- Invalid filter values should fall back to safe defaults or return 400 only if the contract becomes ambiguous

## Testing Strategy

### Backend Tests

Add or update tests for:

- document list filtering by text, status, and time range
- document list pagination metadata
- chunk endpoint visibility and response shape
- batch ingest success, skip, and partial-result paths
- batch delete success and partial-result paths
- delete cleanup for file and vector data
- RBAC coverage for the new delete permission

### Frontend Tests

Add or update tests for:

- search plus explicit filter interaction
- pagination state and page changes
- no-default-selection empty state
- row selection versus checkbox selection behavior
- batch action bar visibility and action dispatch
- preview modal behavior with and without preview text
- chunk tab rendering and expand/collapse
- failed-state error display and retry entry points

## Out Of Scope

This iteration does not include:

- separate routes for document detail or chunk detail
- raw embedding vector visualization
- virtual scrolling
- advanced time pickers
- multi-column sorting
- document version history

## Success Criteria

The redesign is successful when:

- the document list shows significantly more rows per screen than today
- row status is readable without large helper copy
- the right panel remains useful without dumping full extracted text inline
- users can inspect chunks directly from the knowledgebase page
- users can retry failed ingests and re-run indexed documents from both row and detail contexts
- users can batch re-ingest and batch delete
- large document sets remain navigable through filters and pagination

