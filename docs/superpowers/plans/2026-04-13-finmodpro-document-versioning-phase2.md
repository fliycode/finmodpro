# FinModPro Document Versioning And Provenance Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add document version history and provenance metadata so each knowledge asset can be traced to its source, replacement history, and current active version without disrupting the existing ingestion workflow.

**Architecture:** Extend the existing `knowledgebase` app rather than creating a new lineage system. Keep `Document` as the main operational entity, add lightweight lineage/version fields or a closely coupled `DocumentVersion` record, and expose version/provenance information through current document APIs and the knowledgebase UI.

**Tech Stack:** Django, Django ORM, existing knowledgebase services/controllers, Vue 3, current knowledgebase UI, Django test runner, Vite/Node test runner

---

## Scope

### In Scope

- Document version lineage
- Current version indicator
- Replace-version upload flow
- Source metadata and provenance fields
- Version history API
- Version/provenance display in the knowledgebase UI

### Out of Scope

- Graph-style data lineage visualization
- Bulk version migration tools
- Dataset permissions redesign
- Rich audit dashboard for version actions
- Automatic diffing between document versions

## Locked Decisions

- Keep versioning inside `knowledgebase`.
- A document lineage may have multiple versions, but only one current version.
- Existing document upload remains supported for new lineages.
- “Upload new version” is a distinct API path, not overloaded into the base upload endpoint.
- Provenance is metadata-first, not a separate workflow engine.

## File Structure

- `backend/knowledgebase/models.py`
- `backend/knowledgebase/services/document_service.py`
- `backend/knowledgebase/services/version_service.py`
- `backend/knowledgebase/controllers/version_controller.py`
- `backend/knowledgebase/urls.py`
- `backend/knowledgebase/tests.py`
- `frontend/src/api/knowledgebase.js`
- `frontend/src/components/KnowledgeBase.vue`

## Data Model Decision

Prefer the smallest explicit lineage model that keeps current document logic readable:

```python
class DocumentVersion(models.Model):
    root_document = models.ForeignKey(Document, related_name="versions", on_delete=models.CASCADE)
    document = models.OneToOneField(Document, related_name="version_record", on_delete=models.CASCADE)
    version_number = models.PositiveIntegerField()
    is_current = models.BooleanField(default=True)
    source_type = models.CharField(max_length=64, blank=True, default="")
    source_label = models.CharField(max_length=255, blank=True, default="")
    source_metadata = models.JSONField(default=dict, blank=True)
    processing_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

If this proves too awkward, use equivalent fields directly on `Document`, but keep one current-version invariant.

## API Contract

- `GET /api/knowledgebase/documents/<id>/versions`
- `POST /api/knowledgebase/documents/<id>/versions`

Version list response:

```json
{
  "document_id": 11,
  "current_version": 3,
  "versions": [
    {
      "document_id": 11,
      "version_number": 3,
      "is_current": true,
      "source_type": "upload",
      "source_label": "Q1 风险纪要修订版",
      "created_at": "2026-04-13T10:00:00+08:00"
    }
  ]
}
```

## Task 1: Add failing backend tests for version lineage

**Files:**
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Add tests for version upload and listing**

Cover:

- creating an initial document
- uploading a replacement version
- listing versions
- ensuring only the newest version is marked current

- [ ] **Step 2: Add tests for provenance fields**

Cover `source_type`, `source_label`, `source_metadata`, and `processing_notes`.

- [ ] **Step 3: Run failing tests**

```bash
cd backend && python manage.py test knowledgebase -v 2
```

Expected: FAIL on missing version model/routes/services

## Task 2: Implement versioning and provenance in backend

**Files:**
- Modify: `backend/knowledgebase/models.py`
- Create: `backend/knowledgebase/services/version_service.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Create: `backend/knowledgebase/controllers/version_controller.py`
- Modify: `backend/knowledgebase/urls.py`

- [ ] **Step 1: Add model and migration**
- [ ] **Step 2: Add `create_new_document_version`, `list_document_versions`, `serialize_document_version` helpers**
- [ ] **Step 3: Expose version list/upload APIs**
- [ ] **Step 4: Extend base document serialization with current version and provenance summary**

- [ ] **Step 5: Verify backend**

```bash
cd backend && python manage.py test knowledgebase -v 2
```

Expected: PASS

## Task 3: Add UI support for version history and provenance

**Files:**
- Modify: `frontend/src/api/knowledgebase.js`
- Modify: `frontend/src/components/KnowledgeBase.vue`

- [ ] **Step 1: Add dataset-compatible version API methods**

Add:

- `listDocumentVersions(documentId)`
- `uploadNewVersion(documentId, file, metadata)`

- [ ] **Step 2: Render provenance and version panels**

Show:

- current version
- source label/type
- version history
- upload new version action

- [ ] **Step 3: Verify frontend**

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS

## Task 4: Final verification and commit

- [ ] **Step 1: Run combined verification**

```bash
cd backend && python manage.py test knowledgebase -v 2
cd frontend && npm test
cd frontend && npm run build
```

- [ ] **Step 2: Commit**

```bash
git add backend/knowledgebase frontend/src/api/knowledgebase.js frontend/src/components/KnowledgeBase.vue docs/superpowers/plans/2026-04-13-finmodpro-document-versioning-phase2.md
git commit -m "feat(platform): add document versioning and provenance"
```

## Acceptance Checklist

- [ ] Version history exists per document lineage
- [ ] Exactly one current version is enforced
- [ ] Provenance metadata is stored and exposed
- [ ] UI can view versions and upload a replacement version
- [ ] Existing ingestion flow remains intact
