# Knowledgebase Hierarchical Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize ingest for oversized documents by introducing parent/child chunking, section-only vector indexing, and resumable section-batch progress while preserving fine-grained retrieval snippets.

**Architecture:** Add a new `DocumentSectionChunk` parent model, keep `DocumentChunk` as child snippets, and switch large documents to a hierarchical ingest path. Vector search will target parent sections only, then rank child chunks locally inside matched sections; indexing progress will persist at the section-batch level so retries resume instead of restarting the whole document.

**Tech Stack:** Django models/migrations/tests, existing knowledgebase chunk services, Milvus vector store, DRF-backed knowledgebase APIs, Node test + Django test runner.

---

## File Structure

- Create: `backend/knowledgebase/migrations/0006_documentsectionchunk_and_ingest_progress.py`
- Create: `backend/knowledgebase/services/hierarchical_chunk_service.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/knowledgebase/models.py`
- Modify: `backend/knowledgebase/services/chunk_service.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/services/vector_service.py`
- Modify: `backend/rag/services/vector_store_service.py`
- Modify: `backend/knowledgebase/tests.py`
- Modify: `backend/systemcheck/services/dashboard_service.py`
- Modify: `frontend/src/api/knowledgebase.js`
- Modify: `frontend/src/api/__tests__/knowledgebase.test.js`

## Task 1: Add hierarchical storage models and ingest progress fields

**Files:**
- Create: `backend/knowledgebase/migrations/0006_documentsectionchunk_and_ingest_progress.py`
- Modify: `backend/knowledgebase/models.py`
- Test: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write the failing model/inventory test**

```python
def test_large_document_can_store_section_and_child_chunks(self):
    document = Document.objects.create(
        title="Annual filing",
        file=SimpleUploadedFile("filing.txt", b"filing", content_type="text/plain"),
        filename="filing.txt",
        doc_type="txt",
        visibility=Document.VISIBILITY_INTERNAL,
    )
    section = DocumentSectionChunk.objects.create(
        document=document,
        section_index=0,
        title="Management Discussion",
        section_path="Management Discussion",
        content="Parent section content",
        metadata={"document_title": document.title},
        start_offset=0,
        end_offset=100,
    )
    child = DocumentChunk.objects.create(
        document=document,
        section_chunk=section,
        chunk_index=0,
        chunk_index_in_section=0,
        content="Child chunk content",
        metadata={"document_title": document.title},
        start_offset=0,
        end_offset=50,
    )
    task = IngestionTask.objects.create(
        document=document,
        strategy=IngestionTask.STRATEGY_HIERARCHICAL,
        total_section_count=1,
        indexed_section_count=0,
        failed_section_count=0,
    )

    self.assertEqual(child.section_chunk_id, section.id)
    self.assertEqual(task.strategy, IngestionTask.STRATEGY_HIERARCHICAL)
    self.assertEqual(task.total_section_count, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_large_document_can_store_section_and_child_chunks --verbosity 2
```

Expected: FAIL because `DocumentSectionChunk`, `section_chunk`, and ingest progress fields do not exist yet.

- [ ] **Step 3: Write minimal model and migration changes**

```python
class IngestionTask(models.Model):
    STRATEGY_FLAT = "flat"
    STRATEGY_HIERARCHICAL = "hierarchical"
    STRATEGY_CHOICES = (
        (STRATEGY_FLAT, "Flat"),
        (STRATEGY_HIERARCHICAL, "Hierarchical"),
    )
    strategy = models.CharField(max_length=32, choices=STRATEGY_CHOICES, default=STRATEGY_FLAT)
    total_section_count = models.PositiveIntegerField(default=0)
    indexed_section_count = models.PositiveIntegerField(default=0)
    failed_section_count = models.PositiveIntegerField(default=0)


class DocumentSectionChunk(models.Model):
    document = models.ForeignKey(Document, related_name="section_chunks", on_delete=models.CASCADE)
    section_index = models.PositiveIntegerField()
    title = models.CharField(max_length=255, blank=True, default="")
    section_path = models.CharField(max_length=512, blank=True, default="")
    content = models.TextField()
    vector_id = models.CharField(max_length=64, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    start_offset = models.PositiveIntegerField(default=0)
    end_offset = models.PositiveIntegerField(default=0)
    is_indexed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section_index"]
        unique_together = ("document", "section_index")


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, related_name="chunks", on_delete=models.CASCADE)
    section_chunk = models.ForeignKey(
        DocumentSectionChunk,
        related_name="child_chunks",
        on_delete=models.CASCADE,
    )
    chunk_index = models.PositiveIntegerField()
    chunk_index_in_section = models.PositiveIntegerField(default=0)
    content = models.TextField()
    vector_id = models.CharField(max_length=64, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    start_offset = models.PositiveIntegerField(default=0)
    end_offset = models.PositiveIntegerField(default=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_large_document_can_store_section_and_child_chunks --verbosity 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/knowledgebase/models.py backend/knowledgebase/migrations/0006_documentsectionchunk_and_ingest_progress.py backend/knowledgebase/tests.py
git commit -m "feat(knowledgebase): add hierarchical chunk models"
```

## Task 2: Add hierarchical chunk builders and large-document trigger

**Files:**
- Create: `backend/knowledgebase/services/hierarchical_chunk_service.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/knowledgebase/services/chunk_service.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write the failing hierarchy builder tests**

```python
def test_build_hierarchical_chunks_from_plain_text_uses_large_sections(self):
    text = "Section A\n\n" + ("A" * 3000) + "\n\nSection B\n\n" + ("B" * 3000)
    result = build_hierarchical_document_chunks(
        text=text,
        elements=None,
        section_metadata_builder=lambda index: {"section_index": index},
        child_metadata_builder=lambda section, index: {"section_index": section["section_index"], "chunk_index": index},
    )

    self.assertGreaterEqual(len(result["sections"]), 2)
    self.assertGreater(len(result["child_chunks"]), len(result["sections"]))
    self.assertLess(len(result["sections"]), len(result["child_chunks"]))


def test_large_document_trigger_switches_to_hierarchical_strategy(self):
    strategy = choose_chunking_strategy(parsed_text_length=600_000, estimated_flat_chunk_count=3200)
    self.assertEqual(strategy, "hierarchical")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python manage.py test \
  knowledgebase.tests.KnowledgebaseChunkServiceTests.test_build_hierarchical_chunks_from_plain_text_uses_large_sections \
  knowledgebase.tests.KnowledgebaseChunkServiceTests.test_large_document_trigger_switches_to_hierarchical_strategy \
  --verbosity 2
```

Expected: FAIL because the hierarchical builder and strategy selector do not exist.

- [ ] **Step 3: Implement minimal hierarchical chunk builder and thresholds**

```python
KB_HIERARCHICAL_TEXT_THRESHOLD = get_int_env("KB_HIERARCHICAL_TEXT_THRESHOLD", 500000)
KB_HIERARCHICAL_CHUNK_THRESHOLD = get_int_env("KB_HIERARCHICAL_CHUNK_THRESHOLD", 3000)
KB_SECTION_CHUNK_SIZE = get_int_env("KB_SECTION_CHUNK_SIZE", 2000)
KB_SECTION_CHUNK_OVERLAP = get_int_env("KB_SECTION_CHUNK_OVERLAP", 200)


def choose_chunking_strategy(*, parsed_text_length, estimated_flat_chunk_count):
    if parsed_text_length >= settings.KB_HIERARCHICAL_TEXT_THRESHOLD:
        return "hierarchical"
    if estimated_flat_chunk_count >= settings.KB_HIERARCHICAL_CHUNK_THRESHOLD:
        return "hierarchical"
    return "flat"


def build_hierarchical_document_chunks(...):
    sections = build_document_chunks(
        text,
        metadata_builder=section_metadata_builder,
        chunk_size=settings.KB_SECTION_CHUNK_SIZE,
        overlap=settings.KB_SECTION_CHUNK_OVERLAP,
    )
    child_chunks = []
    for section in sections:
        for child in build_document_chunks(
            section["content"],
            metadata_builder=lambda index, section=section: child_metadata_builder(section, index),
            chunk_size=settings.KB_CHUNK_SIZE,
            overlap=settings.KB_CHUNK_OVERLAP,
        ):
            child_chunks.append(child)
    return {"sections": sections, "child_chunks": child_chunks}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && .venv/bin/python manage.py test \
  knowledgebase.tests.KnowledgebaseChunkServiceTests.test_build_hierarchical_chunks_from_plain_text_uses_large_sections \
  knowledgebase.tests.KnowledgebaseChunkServiceTests.test_large_document_trigger_switches_to_hierarchical_strategy \
  --verbosity 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/config/settings.py backend/knowledgebase/services/chunk_service.py backend/knowledgebase/services/hierarchical_chunk_service.py backend/knowledgebase/tests.py
git commit -m "feat(knowledgebase): add hierarchical chunk builder"
```

## Task 3: Switch ingest to parent/child persistence for large documents

**Files:**
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write the failing ingest persistence tests**

```python
@patch("knowledgebase.services.document_service.parse_document_file")
def test_chunk_document_persists_sections_and_children_for_large_document(self, mock_parse):
    document = self.create_document(filename="large.txt")
    mock_parse.return_value = {
        "parsed_text": "X" * 600000,
        "elements": None,
        "chunk_metadata_defaults": {},
    }

    parser_result = parse_document(document)
    chunk_document(document, parser_result)

    self.assertEqual(DocumentSectionChunk.objects.filter(document=document).count() > 0, True)
    self.assertEqual(DocumentChunk.objects.filter(document=document).count() > 0, True)
    latest_task = IngestionTask.objects.create(document=document)
    self.assertIn(document.status, {Document.STATUS_CHUNKED, Document.STATUS_INDEXED})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_chunk_document_persists_sections_and_children_for_large_document --verbosity 2
```

Expected: FAIL because `chunk_document()` still writes only flat `DocumentChunk`s.

- [ ] **Step 3: Implement minimal large-document ingest branching**

```python
def chunk_document(document, parser_result):
    parser_result = parser_result or {}
    parser_defaults = parser_result.get("chunk_metadata_defaults") or {}
    elements = parser_result.get("elements")
    parsed_text = parser_result.get("parsed_text", "")

    DocumentSectionChunk.objects.filter(document=document).delete()
    DocumentChunk.objects.filter(document=document).delete()

    estimated_flat_chunk_count = estimate_flat_chunk_count(parsed_text)
    strategy = choose_chunking_strategy(
        parsed_text_length=len(parsed_text),
        estimated_flat_chunk_count=estimated_flat_chunk_count,
    )

    if strategy == IngestionTask.STRATEGY_HIERARCHICAL:
        hierarchical = build_hierarchical_document_chunks(
            text=parsed_text,
            elements=elements,
            section_metadata_builder=lambda index: _build_section_chunk_metadata(document, index, parser_defaults),
            child_metadata_builder=lambda section, index: _build_chunk_metadata(document, index, parser_defaults),
        )
        sections = DocumentSectionChunk.objects.bulk_create([...])
        DocumentChunk.objects.bulk_create([...])
        _update_document_status(document, status=Document.STATUS_CHUNKED)
        return hierarchical

    ...
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_chunk_document_persists_sections_and_children_for_large_document --verbosity 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/knowledgebase/services/document_service.py backend/knowledgebase/tests.py
git commit -m "feat(knowledgebase): persist hierarchical chunk trees"
```

## Task 4: Index only section chunks and persist section-batch progress

**Files:**
- Modify: `backend/knowledgebase/services/vector_service.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write the failing section-indexing tests**

```python
@override_settings(KB_EMBEDDING_BATCH_SIZE=10)
def test_large_document_indexes_only_unindexed_sections(self):
    document = self.create_document(filename="large.txt")
    section_one = DocumentSectionChunk.objects.create(document=document, section_index=0, content="section one", metadata={}, is_indexed=False)
    section_two = DocumentSectionChunk.objects.create(document=document, section_index=1, content="section two", metadata={}, is_indexed=True)
    IngestionTask.objects.create(
        document=document,
        strategy=IngestionTask.STRATEGY_HIERARCHICAL,
        total_section_count=2,
        indexed_section_count=1,
    )

    with patch("knowledgebase.services.embedding_service.get_embedding_provider", return_value=RecordingEmbeddingProvider()):
        VectorService().index(document)

    section_one.refresh_from_db()
    section_two.refresh_from_db()
    self.assertTrue(section_one.is_indexed)
    self.assertTrue(section_two.is_indexed)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.VectorServiceBatchingTests.test_large_document_indexes_only_unindexed_sections --verbosity 2
```

Expected: FAIL because `VectorService.index()` still reads all `DocumentChunk`s and has no section progress state.

- [ ] **Step 3: Implement minimal resumable section indexing**

```python
def _build_section_rows(self, document):
    sections = list(
        DocumentSectionChunk.objects.filter(document=document, is_indexed=False).order_by("section_index")
    )
    ...

def index(self, document, *, ingestion_task=None):
    if ingestion_task and ingestion_task.strategy == IngestionTask.STRATEGY_HIERARCHICAL:
        rows, sections_to_update = self._build_section_rows(document)
        if rows:
            client.insert(settings.MILVUS_COLLECTION_NAME, rows)
            for section in sections_to_update:
                section.is_indexed = True
            DocumentSectionChunk.objects.bulk_update(sections_to_update, ["vector_id", "is_indexed"])
            ingestion_task.indexed_section_count += len(sections_to_update)
            ingestion_task.save(update_fields=["indexed_section_count", "updated_at"])
        return
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.VectorServiceBatchingTests.test_large_document_indexes_only_unindexed_sections --verbosity 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/knowledgebase/services/vector_service.py backend/knowledgebase/services/document_service.py backend/knowledgebase/tests.py
git commit -m "feat(knowledgebase): resume section indexing"
```

## Task 5: Switch retrieval to section-first + child-local ranking

**Files:**
- Modify: `backend/knowledgebase/services/vector_service.py`
- Modify: `backend/rag/services/vector_store_service.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write the failing hierarchical retrieval test**

```python
def test_query_store_returns_child_snippet_from_matched_section(self):
    document = self.create_document(filename="report.txt")
    section = DocumentSectionChunk.objects.create(
        document=document,
        section_index=0,
        title="Risk Factors",
        section_path="Risk Factors",
        content="Market risk and liquidity risk.",
        metadata={"document_title": document.title},
        vector_id="1",
        is_indexed=True,
    )
    child = DocumentChunk.objects.create(
        document=document,
        section_chunk=section,
        chunk_index=0,
        chunk_index_in_section=0,
        content="Liquidity risk increased during the quarter.",
        metadata={"document_title": document.title},
    )

    with patch.object(VectorService, "search", return_value=[{"document_id": document.id, "section_chunk_id": section.id, "score": 0.9}]):
        results = query_store("liquidity risk", top_k=3)

    self.assertEqual(results[0]["chunk_id"], child.id)
    self.assertEqual(results[0]["section_chunk_id"], section.id)
    self.assertIn("Liquidity risk", results[0]["snippet"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseRetrievalTests.test_query_store_returns_child_snippet_from_matched_section --verbosity 2
```

Expected: FAIL because retrieval still assumes vector results point directly to `DocumentChunk`.

- [ ] **Step 3: Implement minimal hierarchical retrieval merge**

```python
def _serialize_child_result(section, chunk, score, *, keyword_score=0.0, vector_score=0.0):
    metadata = chunk.metadata or {}
    return {
        "document_id": chunk.document_id,
        "chunk_id": chunk.id,
        "section_chunk_id": section.id,
        "document_title": metadata.get("document_title") or chunk.document.title,
        "snippet": chunk.content,
        "metadata": metadata,
        "score": score,
        "vector_score": vector_score,
        "keyword_score": keyword_score,
        "section_title": section.title,
        "section_path": section.section_path,
        "section_context_summary": "",
    }


def query_store(query, filters=None, top_k=5):
    section_candidates = VectorService().search(query=query, filters=filters, top_k=max(int(top_k), 1) * 2)
    child_results = _rank_children_within_sections(query, section_candidates, filters=filters)
    return child_results[: int(top_k)]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseRetrievalTests.test_query_store_returns_child_snippet_from_matched_section --verbosity 2
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/knowledgebase/services/vector_service.py backend/rag/services/vector_store_service.py backend/knowledgebase/tests.py
git commit -m "feat(rag): retrieve child snippets from section hits"
```

## Task 6: Expose strategy/progress metadata and run full verification

**Files:**
- Modify: `backend/systemcheck/services/dashboard_service.py`
- Modify: `frontend/src/api/knowledgebase.js`
- Modify: `frontend/src/api/__tests__/knowledgebase.test.js`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Write the failing progress serialization tests**

```python
def test_document_payload_includes_hierarchical_progress(self):
    ingestion_task = IngestionTask.objects.create(
        document=self.create_document(filename="large.txt"),
        strategy=IngestionTask.STRATEGY_HIERARCHICAL,
        total_section_count=12,
        indexed_section_count=5,
        failed_section_count=0,
    )

    payload = serialize_document(ingestion_task.document)

    self.assertEqual(payload["latest_ingestion_task"]["strategy"], "hierarchical")
    self.assertEqual(payload["latest_ingestion_task"]["indexed_section_count"], 5)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_document_payload_includes_hierarchical_progress --verbosity 2
```

Expected: FAIL because the serializer and frontend normalization do not expose hierarchical progress yet.

- [ ] **Step 3: Implement minimal payload and frontend support**

```python
latest_task_payload = {
    ...
    "strategy": ingestion_task.strategy,
    "total_section_count": ingestion_task.total_section_count,
    "indexed_section_count": ingestion_task.indexed_section_count,
    "failed_section_count": ingestion_task.failed_section_count,
}
```

```javascript
const progress = latestIngestionTask?.strategy === 'hierarchical'
  ? {
      totalSections: latestIngestionTask.total_section_count ?? 0,
      indexedSections: latestIngestionTask.indexed_section_count ?? 0,
      failedSections: latestIngestionTask.failed_section_count ?? 0,
      strategy: latestIngestionTask.strategy,
    }
  : null;
```

- [ ] **Step 4: Run the complete verification suite**

Run:

```bash
cd backend && .venv/bin/python manage.py check && .venv/bin/python manage.py test knowledgebase --verbosity 1
cd ../frontend && npm test
```

Expected: Django check clean, knowledgebase tests PASS, frontend tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/systemcheck/services/dashboard_service.py backend/knowledgebase/tests.py frontend/src/api/knowledgebase.js frontend/src/api/__tests__/knowledgebase.test.js
git commit -m "feat(knowledgebase): expose hierarchical ingest progress"
```
