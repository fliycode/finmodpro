# LangGraph Memory Migration Design

**Date:** 2026-04-27  
**Scope:** Backend only — `backend/chat/`  
**Goal:** Replace custom keyword-based memory system with LangGraph's `BaseStore` API and LLM-based extraction.

---

## Problem Statement

The current memory system has three compounding failures:

1. **Critical bug** — `_direct_answer_context` in `rag_graph_service.py` hard-codes `session=None`, causing all "direct route" questions (most conversational queries) to receive no session history and no memories.
2. **Extraction is keyword-only** — `_classify_memory_content()` only fires on messages containing literal phrases like "请记住" or "我希望". Normal facts said in conversation are never stored.
3. **Search is keyword-only** — `search_memories()` uses Django `icontains`, so it misses semantically related but lexically different queries.

The memory models (`MemoryItem`, `MemoryEvidence`, `MemoryActionLog`) and the Celery async dispatch pattern are both sound and will be retained.

---

## Proposed Architecture

### Two-layer migration

**Layer 1 — Storage interface: `DjangoMemoryStore`**  
Implement LangGraph's `BaseStore` backed by the existing `MemoryItem` Django/MySQL table. This gives us the standard LangGraph store API (`put`, `get`, `search`, `delete`) while persisting to MySQL with no new infrastructure.

**Layer 2 — Extraction: LLM-based**  
Replace the keyword classifier with an LLM call that extracts structured memory items from recent conversation turns. Called from the existing Celery task (async, no latency added to user responses).

### Why not full Checkpointer migration?

LangGraph's `Checkpointer` would also solve the short-term memory bug, but:
- No official MySQL checkpointer exists (only Postgres, SQLite)
- `ChatSession`/`ChatMessage` are the source of truth for the frontend API
- Migrating would create dual storage with no user-visible benefit

The short-term memory bug is fixed directly (`session=None` → `session=state.get("session")`).

---

## Component Design

### 1. `DjangoMemoryStore` — `chat/services/store.py` (new file)

Subclasses `langgraph.store.base.BaseStore`. Only `batch()` and `abatch()` need to be implemented — `put`, `get`, `search`, `delete` are inherited free wrappers.

**Namespace convention:**
| Namespace tuple | MemoryItem scope |
|---|---|
| `("memories", "<user_id>")` | `scope_type="user_global"`, `scope_key=""` |
| `("memories", "<user_id>", "dataset", "<dataset_id>")` | `scope_type="dataset"`, `scope_key="<dataset_id>"` |

**Key:** SHA-256 fingerprint of normalized content (same dedup logic as today).

**Value dict stored in `MemoryItem`:**
```python
{
    "title": str,
    "content": str,
    "memory_type": str,          # user_preference | work_rule | confirmed_fact | project_background
    "confidence_score": float,
    "pinned": bool,
    "source_kind": str,          # auto | manual
}
```

**Op mapping:**
- `PutOp(value=dict)` → upsert `MemoryItem` (match by fingerprint/namespace/key)
- `PutOp(value=None)` → soft-delete (`status=deleted`)
- `GetOp` → fetch active `MemoryItem` by namespace + key
- `SearchOp` → filter active `MemoryItem`s by namespace prefix + optional `icontains` on title/content
- `ListNamespacesOp` → distinct scope_type/scope_key combinations

A module-level singleton `django_memory_store = DjangoMemoryStore()` is exported.

**`abatch()`**: Django ORM is sync-only; `abatch` uses `asyncio.get_event_loop().run_in_executor(None, self.batch, ops)`.

---

### 2. RAG graph changes — `chat/services/rag_graph_service.py`

**Change 1 — Compile graph with store:**
```python
_RAG_GRAPH = _build_rag_graph().compile(store=django_memory_store)
```
Nodes can now call `get_store()` at runtime instead of importing the store directly.

**Change 2 — Fix `_direct_answer_context`:**
```python
# Before
"messages": build_chat_messages(session=None, ...)
# After
"messages": build_chat_messages(session=state.get("session"), ...)
```

No other graph structure changes.

---

### 3. Context service — `chat/services/context_service.py`

Replace `from chat.services.memory_service import search_memories` with the store:

```python
from langgraph.config import get_store
from chat.services.store import django_memory_store

def _load_memories(*, user_id, question, dataset_id=None, limit=5):
    namespace = ("memories", str(user_id))
    # Try store from graph context first; fall back to singleton for non-graph callers
    try:
        store = get_store()
    except Exception:
        store = django_memory_store
    items = store.search(namespace, query=question, limit=limit)
    if dataset_id:
        ds_namespace = ("memories", str(user_id), "dataset", str(dataset_id))
        items += store.search(ds_namespace, query=question, limit=limit)
    # Return value dicts so _format_memories() receives plain dicts (title, content keys)
    return [item.value for item in items]
```

---

### 4. Memory service rewrite — `chat/services/memory_service.py`

**Remove:**
- `_classify_memory_content()` — keyword matching
- `_build_memory_scope()`, `_build_memory_title()`, `_build_memory_fingerprint()` (moved into store)
- `extract_session_memories()` — replaced by LLM extraction below
- `search_memories()` — replaced by store

**Keep (unchanged):**
- `list_memory_items_for_user()` — used by memory controller API
- `get_memory_item_for_user()`, `list_memory_evidence_for_memory()`
- `record_memory_view()`, `set_memory_pin_state()`, `delete_memory_item()`

**New: `extract_memories_with_llm(*, session_id)`**

```
1. Load session + last N user/assistant messages (configurable, default 4)
2. Build LLM prompt asking it to extract memorable facts as JSON array:
   [{"title": "...", "content": "...", "memory_type": "...", "confidence_score": 0.0–1.0}]
3. Parse response; skip items with confidence < threshold (default 0.7)
4. For each item:
   - Build namespace from session.user + context_filters
   - Build fingerprint
   - store.put(namespace, fingerprint_key, value_dict)
5. Return count of stored items
```

**LLM extraction prompt design:**
- Instructs model to only extract content the user would expect the assistant to remember
- Categories: user preference, work rule, confirmed fact, project background
- Explicitly tells model to return empty array `[]` if nothing memorable is said
- Max 5 items per call to prevent over-extraction

---

### 5. Celery task — `chat/tasks.py`

Replace `extract_session_memories` import with `extract_memories_with_llm`:

```python
from chat.services.memory_service import extract_memories_with_llm

@shared_task(name="chat.extract_session_memories_task")
def extract_session_memories_task(session_id):
    return extract_memories_with_llm(session_id=session_id)
```

Task name unchanged — no redeployment of Celery beat config needed.

---

## Data Flow (after migration)

```
User message
    │
    ▼
LangGraph RAG graph (compiled with DjangoMemoryStore)
    │
    ├── route_question (direct or retrieve)
    │
    ├── [retrieve path] rewrite_query → retrieve → grade → build_retrieval_context
    │                                                           │
    │   build_chat_messages():                                  │
    │     - recent messages (Django)                           │
    │     - rolling summary (Django)                           │
    │     - store.search(namespace, query) ← NEW              │
    │     - citations                                          │
    │                                                          │
    └── [direct path] direct_answer_context  ← BUG FIXED     │
            build_chat_messages(session=session) ←─────────────┘
    │
    ▼
provider.chat() → answer
    │
    ▼
finalize_session_message (Django)
    │
    ▼
dispatch_session_maintenance_tasks
    ├── update_session_title_task
    ├── update_session_summary_task
    └── extract_session_memories_task  ← now uses LLM + DjangoMemoryStore
```

---

## Files Changed

| File | Change |
|---|---|
| `chat/services/store.py` | **NEW** — `DjangoMemoryStore` |
| `chat/services/memory_service.py` | **REWRITE** — remove keyword logic, add `extract_memories_with_llm` |
| `chat/services/context_service.py` | **EDIT** — use store.search() instead of search_memories() |
| `chat/services/rag_graph_service.py` | **EDIT** — compile with store, fix session=None bug |
| `chat/tasks.py` | **EDIT** — import new extraction function |
| `chat/models.py` | **NO CHANGE** |
| `chat/controllers/memory_controller.py` | **NO CHANGE** |
| `chat/urls.py` | **NO CHANGE** |

---

## Not in Scope

- Semantic/vector memory search (requires embedding model integration; left as future P2)
- LangGraph Checkpointer (requires PostgreSQL; not in current infra)
- Frontend changes
- `MemoryEvidence` / `MemoryActionLog` model changes
- Django DB migration

---

## Testing Plan

- Unit tests for `DjangoMemoryStore`: `put → search → get → delete` roundtrip using Django test DB
- Unit test for `extract_memories_with_llm` with a mocked LLM provider
- Existing `context_service` tests updated to use store search instead of `search_memories`
- Integration test: send a message with memorable content, assert it's stored; send follow-up, assert it's injected into context
- Regression: existing `memory_controller` API endpoints still work after rewrite
