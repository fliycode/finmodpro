# Knowledgebase Hierarchical Chunking Design

## Problem

The current knowledgebase ingest path uses a mostly flat chunking strategy with a default chunk size of 400 characters and 50 characters of overlap. This works for small and medium documents, but it breaks down for very large inputs.

The clearest example is document `34` (`apple-2025-10-31-annual-filing.txt`):

- Parsed text size: about 10.5 million characters
- Flat chunk count: 26,309
- Embedding batch size: 10
- Estimated embedding calls: about 2,631

In production, this creates a long all-or-nothing indexing phase. Even after batching fixes and transport retries, a few upstream timeouts can still fail the entire ingest task because the document is expanded into too many vectorized units.

## Goal

Stabilize ingest for very large documents without degrading the retrieval experience for normal documents.

The design should:

1. Reduce vectorized unit count for large documents
2. Keep final answer snippets fine-grained
3. Allow resumable indexing at a smaller unit than the whole document
4. Avoid forcing a disruptive migration for already indexed normal documents

## Non-Goals

This phase does not aim to:

- Reindex all existing documents automatically
- Add child-level vector search immediately
- Redesign the entire RAG ranking stack
- Change behavior for normal documents unless they exceed explicit thresholds

## Current State

### Chunking

`ChunkService.build_chunks()` performs flat character-window chunking. `build_chunks_from_elements()` respects some Unstructured boundaries, but for long plain-text inputs the result is still effectively many small chunks.

### Storage

`DocumentChunk` currently stores all chunks for a document in one table. Every chunk is treated as both a retrieval unit and a vectorization unit.

### Indexing

`VectorService._build_rows()` loads all `DocumentChunk`s for a document, batches embeddings, and then writes vectors. Although request batching has improved throughput, the indexing model is still document-wide and expensive for huge files.

### Retrieval

The current retrieval path expects chunk-level vector search results and returns chunk snippets directly.

## Proposed Design

### Overview

Introduce a hierarchical chunking model with two explicit storage layers:

1. `DocumentSectionChunk` for parent chunks
2. `DocumentChunk` for child chunks

The retrieval and indexing responsibilities are separated:

- Parent chunks are the primary vector search unit
- Child chunks are the fine-grained answer/snippet unit

### Data Model

#### New table: `DocumentSectionChunk`

Add a new parent chunk model with fields equivalent to the responsibilities below:

- `document`
- `section_index`
- `title` or `section_label`
- `section_path`
- `content`
- `vector_id`
- `metadata`
- `start_offset`
- `end_offset`
- timestamps

This model owns the section-level chunk that will be embedded and stored in Milvus.

#### Existing table: `DocumentChunk`

Retain `DocumentChunk`, but repurpose it as the child chunk table.

Add a required FK to `DocumentSectionChunk`:

- `section_chunk`

Add child-specific indexing fields:

- `chunk_index_in_section`
- `start_offset`
- `end_offset`

Keep:

- `document`
- `content`
- `metadata`

`vector_id` should no longer be required for every child chunk in the first phase because child chunks will not be embedded by default.

### Chunk Construction

#### Parent chunk generation

Generate `DocumentSectionChunk`s first.

Preferred splitting order:

1. Title / section / header boundaries from parser elements
2. Table isolation
3. Paragraph-group boundaries
4. Fallback soft windowing for structure-poor text

For long plain-text documents, do not fall back immediately to 400-character flat chunks. Instead, create larger section-level windows that aim to keep the section count in the hundreds or low thousands rather than tens of thousands.

#### Child chunk generation

Within each `DocumentSectionChunk`, generate finer `DocumentChunk`s using a chunk size close to the current 400/50 behavior. These child chunks preserve fine-grained answer snippets and page/position metadata, but they are not the primary vectorized unit.

## Retrieval Flow

### Phase 1 retrieval

Retrieval becomes a two-stage process:

1. Vector search over `DocumentSectionChunk`
2. Local child selection within matched parent chunks

Detailed flow:

1. Query Milvus using section embeddings only
2. Receive top-k section candidates
3. Load child chunks under those section candidates
4. Rank child chunks locally using keyword or local text matching
5. Return child chunk snippets, while retaining section context metadata

### Result shape

Externally, keep the response close to the current retrieval schema:

- `document_id`
- `chunk_id`
- `document_title`
- `snippet`
- `metadata`
- `score`

Internally, add:

- `section_chunk_id`
- `section_title` / `section_path`
- `section_context_summary` as a nullable field reserved for later use; phase 1 may leave it empty but the response contract should define it explicitly

This keeps downstream consumers stable while allowing hierarchical ranking.

### Why not child-level vectors in phase 1

The main objective is to reduce ingest pressure. If parent and child chunks are both embedded immediately, the vector count problem returns. Child-level vector search can be added later as an enhancement, not as part of the initial stabilization scope.

## Ingest Flow

### New pipeline

1. Parse document
2. Build `DocumentSectionChunk`s
3. Build `DocumentChunk`s inside each section
4. Embed and index only section chunks
5. Mark indexing progress at section-batch granularity
6. Mark document indexed once all section batches complete

### Batch persistence

Do not keep indexing as one document-wide all-or-nothing operation.

Instead:

- Process section chunks in batches
- After each successful batch:
  - write vectors to Milvus
  - mark those sections indexed in persistent state

This reduces rollback cost and makes restarts practical.

### Resume behavior

Extend ingest progress tracking so retries continue from unindexed section batches rather than restarting from zero.

Recommended progress fields:

- `total_section_count`
- `indexed_section_count`
- `failed_section_count`
- indexing strategy marker

The first implementation should support resume-from-next-unindexed-section. It should not silently skip permanently failing sections yet, because partial invisible holes would make debugging and trust worse.

## Activation Strategy

Do not globally switch all documents to hierarchical chunking.

### Normal documents

Keep the current flat strategy for ordinary documents.

### Large-document trigger

Enable hierarchical chunking when either condition is met:

- parsed text length exceeds a configured threshold
- estimated flat chunk count exceeds a configured threshold

Suggested initial trigger style:

- text length threshold: hundreds of thousands of characters
- chunk count threshold: roughly 3,000+

This preserves existing behavior for most documents while protecting the ingest path from extreme cases.

## Operational Visibility

Expose the active ingest strategy and hierarchical progress in the task/document detail surfaces.

Recommended fields to surface:

- `strategy = flat | hierarchical`
- `section_count`
- `child_chunk_count`
- `indexed_section_count`
- `retry_count`

This makes it obvious why a document behaves differently and where it is currently spending time.

## Migration Strategy

Do not attempt a forced migration of all existing documents in phase 1.

Recommended rollout:

1. New very large documents use the hierarchical strategy
2. Existing indexed documents remain as they are
3. Reindex is opt-in per document when needed

This keeps rollout risk low and avoids surprising retrieval shifts across the whole corpus.

## Risks and Mitigations

### Retrieval quality risk

Risk:
Section-level recall may be good while child-level local selection is weak.

Mitigation:
Run A/B comparisons between flat chunk retrieval and hierarchical retrieval on a representative QA set. Compare both snippet relevance and final answer quality.

### Section imbalance risk

Risk:
Bad section segmentation can still create oversized parent chunks.

Mitigation:
Apply a hard maximum parent size. If a section exceeds it, split again using paragraph groups or a larger soft window.

### Compatibility risk

Risk:
Current retrieval and admin views assume a single chunk layer.

Mitigation:
Keep outward-facing result shapes as stable as possible and add section metadata as an extension, not a replacement.

### Recovery complexity risk

Risk:
Section-level resumability adds more ingest state.

Mitigation:
Track only the minimum necessary persistent counters and statuses in phase 1. Avoid speculative skip-bad-section logic until the base resume model is proven.

## Verification Plan

### Unit tests

- section chunk construction
- child chunk construction within a parent section
- parent-child association integrity
- hierarchical strategy trigger conditions
- resume-from-unindexed-section behavior

### Integration tests

- very large document ingest uses hierarchical mode
- section-only embedding count is much lower than child count
- retries resume indexing instead of starting from zero
- retrieval returns child snippets sourced from matched parent sections

### Production verification

Compare one ordinary document and one large document:

- total embedded units
- total embedding requests
- ingest duration
- retry behavior
- retrieval snippet quality

## Recommended Rollout

### Phase 1

- Add `DocumentSectionChunk`
- Repurpose `DocumentChunk` as child chunk storage
- Enable hierarchical strategy only for very large documents
- Index only parent chunks
- Add section-batch persistence and resumable indexing

### Phase 2

- Improve local child selection
- Add better admin observability
- Decide whether selected child chunks need secondary vector indexing as a later enhancement

### Phase 3

- Consider broader rollout or migration tooling if hierarchical mode proves better across more document types

## Recommendation

Adopt hierarchical chunking only for large documents and use parent chunks as the sole vectorized unit in phase 1.

This gives the best balance for the current problem:

- it directly attacks request explosion
- it preserves fine answer snippets
- it reduces ingest restart cost
- it limits blast radius for existing normal documents

It is the most practical path to stabilizing knowledgebase ingest for oversized documents without overhauling the whole retrieval system in one step.
