# LangGraph Memory Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the keyword-based custom memory system with a LangGraph `BaseStore`-backed architecture that uses LLM extraction, fixing conversation memory so it actually persists and surfaces across turns.

**Architecture:** `DjangoMemoryStore(BaseStore)` wraps the existing `MemoryItem` model so LangGraph's native store API is used end-to-end. The RAG graph is compiled with `store=django_memory_store`, and `build_chat_messages()` retrieves memories via the store. A Celery task calls an LLM extraction function (not keyword matching) after each turn.

**Tech Stack:** LangGraph 1.1.9, Django ORM, Celery, `provider.chat()` for extraction

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `backend/chat/services/store.py` | `DjangoMemoryStore(BaseStore)` + module singleton |
| **Create** | `backend/prompts/chat/extract_memories.txt` | LLM prompt for structured memory extraction |
| **Modify** | `backend/chat/services/memory_service.py` | Add `extract_memories_with_llm`, keep CRUD helpers, remove keyword extraction |
| **Modify** | `backend/chat/services/context_service.py` | Replace `search_memories()` with store-based `_load_memories()` |
| **Modify** | `backend/chat/services/rag_graph_service.py` | Fix `session=None` bug; compile graph with `store=` |
| **Modify** | `backend/chat/tasks.py` | Import and call `extract_memories_with_llm` |
| **Modify** | `backend/chat/tests.py` | Remove stale `extract_session_memories` import; update memory extraction tests |

**Unchanged:** `chat/models.py`, `chat/controllers/memory_controller.py`, `chat/urls.py`, `chat/serializers.py`, `MemoryEvidence`, `MemoryActionLog`.

---

## Tests setup reference

```bash
cd backend
source .venv/bin/activate
set -a; source .env; set +a
python manage.py test chat --keepdb 2>&1 | tail -20
```

Run a single test class:
```bash
python manage.py test chat.tests.MemoryGovernanceApiTests --keepdb 2>&1 | tail -20
```

---

## Task 1: Create `DjangoMemoryStore`

**Files:**
- Create: `backend/chat/services/store.py`
- Test in: `backend/chat/tests.py` (add class `DjangoMemoryStoreTests` before the existing test classes)

### Step 1.1: Write the failing tests

Add this class at the top of the test class section in `backend/chat/tests.py` (after the helper classes `FakeChatProvider`, `ScriptedChatProvider`, and before the first test class):

```python
from chat.services.store import DjangoMemoryStore


class DjangoMemoryStoreTests(django.test.TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="store-test-user",
            password="pw",
            email="store@example.com",
        )
        self.store = DjangoMemoryStore()
        self.ns = ("memories", str(self.user.id))

    def test_put_then_get_returns_item(self):
        self.store.put(self.ns, "key1", {"title": "T", "content": "C", "memory_type": "confirmed_fact", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        item = self.store.get(self.ns, "key1")
        self.assertIsNotNone(item)
        self.assertEqual(item.value["content"], "C")
        self.assertEqual(item.key, "key1")
        self.assertEqual(item.namespace, self.ns)

    def test_put_none_soft_deletes(self):
        self.store.put(self.ns, "key2", {"title": "T", "content": "C", "memory_type": "confirmed_fact", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        self.store.put(self.ns, "key2", None)
        item = self.store.get(self.ns, "key2")
        self.assertIsNone(item)

    def test_search_returns_matching_items(self):
        self.store.put(self.ns, "k1", {"title": "偏好", "content": "用户喜欢深色模式", "memory_type": "user_preference", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        self.store.put(self.ns, "k2", {"title": "规则", "content": "每次输出中文", "memory_type": "work_rule", "confidence_score": 0.85, "pinned": False, "source_kind": "auto"})
        results = self.store.search(self.ns, query="深色")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value["title"], "偏好")

    def test_search_with_no_query_returns_all(self):
        self.store.put(self.ns, "ka", {"title": "A", "content": "alpha", "memory_type": "confirmed_fact", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        self.store.put(self.ns, "kb", {"title": "B", "content": "beta", "memory_type": "confirmed_fact", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        results = self.store.search(self.ns)
        self.assertGreaterEqual(len(results), 2)

    def test_dataset_namespace_isolated_from_user_global(self):
        ds_ns = ("memories", str(self.user.id), "dataset", "99")
        self.store.put(self.ns, "global-key", {"title": "全局", "content": "全局内容", "memory_type": "confirmed_fact", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        self.store.put(ds_ns, "ds-key", {"title": "数据集", "content": "数据集内容", "memory_type": "work_rule", "confidence_score": 0.9, "pinned": False, "source_kind": "auto"})
        global_results = self.store.search(self.ns)
        ds_results = self.store.search(ds_ns)
        global_keys = {r.key for r in global_results}
        ds_keys = {r.key for r in ds_results}
        self.assertIn("global-key", global_keys)
        self.assertNotIn("ds-key", global_keys)
        self.assertIn("ds-key", ds_keys)
        self.assertNotIn("global-key", ds_keys)

    def test_put_updates_existing_item(self):
        self.store.put(self.ns, "upd", {"title": "旧标题", "content": "旧内容", "memory_type": "confirmed_fact", "confidence_score": 0.7, "pinned": False, "source_kind": "auto"})
        self.store.put(self.ns, "upd", {"title": "新标题", "content": "新内容", "memory_type": "confirmed_fact", "confidence_score": 0.95, "pinned": False, "source_kind": "auto"})
        item = self.store.get(self.ns, "upd")
        self.assertEqual(item.value["title"], "新标题")
        self.assertEqual(item.value["content"], "新内容")
```

- [ ] **Step 1.1: Add the test imports and class**

At the top of `backend/chat/tests.py` (after the existing imports), add:
```python
import django.test
```
(Only if not already imported via TestCase — check first. `from django.test import TestCase` is already there, so add the class body only.)

Add the test class after line ~75 (after `fake_vector_search`). The full class is shown above.

- [ ] **Step 1.2: Run tests — verify they fail with ImportError**

```bash
cd backend && source .venv/bin/activate && set -a && source .env && set +a
python manage.py test chat.tests.DjangoMemoryStoreTests --keepdb 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'DjangoMemoryStore' from 'chat.services.store'`

- [ ] **Step 1.3: Create `backend/chat/services/store.py`**

```python
import asyncio
from typing import Iterable

from langgraph.store.base import BaseStore, GetOp, Item, ListNamespacesOp, Op, PutOp, SearchOp

from chat.models import MemoryItem


def _namespace_to_user_id(namespace: tuple) -> int:
    return int(namespace[1])


def _namespace_to_scope(namespace: tuple) -> tuple:
    """Map LangGraph namespace tuple → (scope_type, scope_key)."""
    if len(namespace) >= 4 and namespace[2] == "dataset":
        return MemoryItem.SCOPE_DATASET, str(namespace[3])
    return MemoryItem.SCOPE_USER_GLOBAL, ""


def _scope_to_namespace(memory: MemoryItem) -> tuple:
    base = ("memories", str(memory.user_id))
    if memory.scope_type == MemoryItem.SCOPE_DATASET:
        return base + ("dataset", memory.scope_key)
    return base


def _memory_to_item(memory: MemoryItem) -> Item:
    return Item(
        namespace=_scope_to_namespace(memory),
        key=memory.fingerprint,
        value={
            "title": memory.title,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "confidence_score": float(memory.confidence_score),
            "pinned": memory.pinned,
            "source_kind": memory.source_kind,
        },
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


class DjangoMemoryStore(BaseStore):
    """LangGraph BaseStore backed by the MemoryItem Django model."""

    def batch(self, ops: Iterable[Op]) -> list:
        results = []
        for op in ops:
            if isinstance(op, PutOp):
                results.append(self._handle_put(op))
            elif isinstance(op, GetOp):
                results.append(self._handle_get(op))
            elif isinstance(op, SearchOp):
                results.append(self._handle_search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(self._handle_list_namespaces(op))
            else:
                results.append(None)
        return results

    async def abatch(self, ops: Iterable[Op]) -> list:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.batch, list(ops))

    def _handle_put(self, op: PutOp):
        user_id = _namespace_to_user_id(op.namespace)
        scope_type, scope_key = _namespace_to_scope(op.namespace)

        if op.value is None:
            MemoryItem.objects.filter(
                user_id=user_id,
                fingerprint=op.key,
                scope_type=scope_type,
                scope_key=scope_key,
            ).update(status=MemoryItem.STATUS_DELETED)
            return None

        value = op.value
        MemoryItem.objects.update_or_create(
            user_id=user_id,
            fingerprint=op.key,
            scope_type=scope_type,
            scope_key=scope_key,
            defaults={
                "title": str(value.get("title", ""))[:255],
                "content": value.get("content", ""),
                "memory_type": value.get("memory_type", MemoryItem.TYPE_CONFIRMED_FACT),
                "confidence_score": value.get("confidence_score", 0.0),
                "pinned": value.get("pinned", False),
                "source_kind": value.get("source_kind", MemoryItem.SOURCE_AUTO),
                "status": MemoryItem.STATUS_ACTIVE,
            },
        )
        return None

    def _handle_get(self, op: GetOp):
        user_id = _namespace_to_user_id(op.namespace)
        scope_type, scope_key = _namespace_to_scope(op.namespace)
        try:
            memory = MemoryItem.objects.get(
                user_id=user_id,
                fingerprint=op.key,
                scope_type=scope_type,
                scope_key=scope_key,
                status=MemoryItem.STATUS_ACTIVE,
            )
            return _memory_to_item(memory)
        except MemoryItem.DoesNotExist:
            return None

    def _handle_search(self, op: SearchOp) -> list:
        prefix = op.namespace_prefix
        if len(prefix) < 2:
            return []

        user_id = int(prefix[1])
        queryset = MemoryItem.objects.filter(
            user_id=user_id,
            status=MemoryItem.STATUS_ACTIVE,
        )

        if len(prefix) >= 4 and prefix[2] == "dataset":
            queryset = queryset.filter(
                scope_type=MemoryItem.SCOPE_DATASET,
                scope_key=str(prefix[3]),
            )
        else:
            queryset = queryset.filter(scope_type=MemoryItem.SCOPE_USER_GLOBAL)

        if op.query:
            from django.db.models import Q
            for token in op.query.split():
                queryset = queryset.filter(
                    Q(title__icontains=token) | Q(content__icontains=token)
                )

        limit = op.limit or 10
        offset = op.offset or 0
        memories = list(queryset.order_by("-pinned", "-updated_at")[offset : offset + limit])
        return [_memory_to_item(m) for m in memories]

    def _handle_list_namespaces(self, op: ListNamespacesOp) -> list:
        combos = (
            MemoryItem.objects.filter(status=MemoryItem.STATUS_ACTIVE)
            .values_list("user_id", "scope_type", "scope_key")
            .distinct()
        )
        result = []
        for user_id, scope_type, scope_key in combos:
            if scope_type == MemoryItem.SCOPE_DATASET:
                result.append(("memories", str(user_id), "dataset", scope_key))
            else:
                result.append(("memories", str(user_id)))
        return result


django_memory_store = DjangoMemoryStore()
```

- [ ] **Step 1.4: Run tests — verify they pass**

```bash
python manage.py test chat.tests.DjangoMemoryStoreTests --keepdb 2>&1 | tail -10
```

Expected: `OK` with 6 tests passing.

- [ ] **Step 1.5: Commit**

```bash
git add backend/chat/services/store.py backend/chat/tests.py
git commit -m "feat(chat): add DjangoMemoryStore backed by MemoryItem model

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Fix the `session=None` bug + compile graph with store

**Files:**
- Modify: `backend/chat/services/rag_graph_service.py`

The `_direct_answer_context` node passes `session=None` to `build_chat_messages()`, which means all conversational (non-retrieval) questions get zero session history and zero memories. This is the primary reason memory appears broken.

- [ ] **Step 2.1: Write the failing test**

In `backend/chat/tests.py`, find the class `ChatAskApiTests` and add this test method:

```python
@patch("chat.services.ask_service.get_chat_provider")
@patch("chat.services.ask_service.retrieve", return_value=[])
def test_direct_route_answer_includes_session_context(self, mocked_retrieve, mocked_provider):
    """Session history must be injected even when the router picks 'direct' route."""
    from chat.services.context_service import build_chat_messages

    captured_calls = []

    class CapturingProvider:
        def chat(self, *, messages, options=None):
            captured_calls.append(messages)
            return "ok"

        def stream(self, *, messages, options=None):
            captured_calls.append(messages)
            yield "ok"

    mocked_provider.return_value = CapturingProvider()

    session = ChatSession.objects.create(
        user=self.user,
        title="记忆测试会话",
        context_filters={},
    )
    # Pre-populate a previous message so session history exists
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content="我叫张三",
        status=ChatMessage.STATUS_COMPLETE,
        sequence=1,
    )
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_ASSISTANT,
        content="您好，张三。",
        status=ChatMessage.STATUS_COMPLETE,
        sequence=2,
    )

    response = self.client.post(
        "/api/chat/ask",
        data=json.dumps({"question": "我叫什么名字？", "session_id": session.id}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
    )

    self.assertEqual(response.status_code, 200)
    self.assertTrue(len(captured_calls) > 0, "Provider must have been called")
    user_message = captured_calls[-1][-1]["content"]
    self.assertIn("张三", user_message, "Session history must appear in the prompt sent to the LLM")
```

- [ ] **Step 2.2: Run the test — verify it fails**

```bash
python manage.py test chat.tests.ChatAskApiTests.test_direct_route_answer_includes_session_context --keepdb 2>&1 | tail -15
```

Expected: FAIL — `AssertionError: Session history must appear in the prompt sent to the LLM`

- [ ] **Step 2.3: Fix the bug and compile graph with store**

In `backend/chat/services/rag_graph_service.py`:

**a) Add the store import** near the top (after existing imports):
```python
from chat.services.store import django_memory_store
```

**b) Fix `_direct_answer_context`** — change `session=None` to `session=state.get("session")`:
```python
def _direct_answer_context(state: ChatRagState):
    return {
        "retrieval_results": [],
        "citations": [],
        "answer_mode": "direct",
        "messages": build_chat_messages(
            session=state.get("session"),
            question=state["question"],
            citations=[],
            filters=state.get("resolved_filters", {}),
        ),
    }
```

**c) Compile the graph with the store** — change `_build_rag_graph`:
```python
def _build_rag_graph():
    graph = StateGraph(ChatRagState)
    graph.add_node("route_question", _route_question)
    graph.add_node("rewrite_query", _rewrite_query)
    graph.add_node("retrieve_context", _retrieve_context)
    graph.add_node("grade_retrieval", _grade_retrieval)
    graph.add_node("build_retrieval_context", _build_retrieval_context)
    graph.add_node("direct_answer_context", _direct_answer_context)
    graph.add_edge(START, "route_question")
    graph.add_conditional_edges(
        "route_question",
        _route_after_router,
        {
            "rewrite_query": "rewrite_query",
            "direct_answer_context": "direct_answer_context",
        },
    )
    graph.add_edge("rewrite_query", "retrieve_context")
    graph.add_edge("retrieve_context", "grade_retrieval")
    graph.add_edge("grade_retrieval", "build_retrieval_context")
    graph.add_edge("build_retrieval_context", END)
    graph.add_edge("direct_answer_context", END)
    return graph.compile(store=django_memory_store)
```

- [ ] **Step 2.4: Run the test — verify it passes**

```bash
python manage.py test chat.tests.ChatAskApiTests.test_direct_route_answer_includes_session_context --keepdb 2>&1 | tail -10
```

Expected: `OK`

- [ ] **Step 2.5: Run full chat test suite to check for regressions**

```bash
python manage.py test chat --keepdb 2>&1 | tail -20
```

Expected: All previously-passing tests still pass.

- [ ] **Step 2.6: Commit**

```bash
git add backend/chat/services/rag_graph_service.py backend/chat/tests.py
git commit -m "fix(chat): pass session to direct_answer_context and compile graph with store

Previously _direct_answer_context passed session=None to build_chat_messages(),
stripping all session history and memories from conversational (non-retrieval)
responses. Also compile the RAG graph with DjangoMemoryStore so get_store()
works inside graph nodes.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Update `context_service.py` to use `DjangoMemoryStore`

**Files:**
- Modify: `backend/chat/services/context_service.py`

Replace the `search_memories()` call with a store-based `_load_memories()` that tries `get_store()` inside graph context and falls back to the module singleton.

- [ ] **Step 3.1: Write the failing test**

Add this test class to `backend/chat/tests.py` (after `DjangoMemoryStoreTests`):

```python
from chat.services.context_service import build_chat_messages as _build_chat_messages
from chat.services.store import DjangoMemoryStore as _DjangoMemoryStore


class ContextServiceMemoryInjectionTests(django.test.TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ctx-mem-user",
            password="pw",
            email="ctx@example.com",
        )
        store = _DjangoMemoryStore()
        ns = ("memories", str(self.user.id))
        store.put(ns, "pref-key", {
            "title": "语言偏好",
            "content": "用户希望所有回答用英文输出",
            "memory_type": "user_preference",
            "confidence_score": 0.95,
            "pinned": False,
            "source_kind": "auto",
        })

    def _make_session(self):
        from chat.models import ChatSession
        return ChatSession.objects.create(
            user=self.user,
            title="ctx测试",
            context_filters={},
        )

    def test_build_chat_messages_injects_memory_into_prompt(self):
        session = self._make_session()
        messages = _build_chat_messages(
            session=session,
            question="请问有什么偏好设置？",
            citations=[],
            filters={},
        )
        full_text = " ".join(m["content"] for m in messages)
        self.assertIn("英文", full_text, "Memory content must appear in the assembled prompt")
```

- [ ] **Step 3.2: Run the test — verify it fails**

```bash
python manage.py test chat.tests.ContextServiceMemoryInjectionTests --keepdb 2>&1 | tail -10
```

Expected: FAIL — memory not found in prompt (because `search_memories()` doesn't return store-backed items without a query match).

Actually: The existing `search_memories` uses icontains keyword matching on the query "请问有什么偏好设置？". The stored content is "用户希望所有回答用英文输出". There's no token overlap, so search returns 0 results. Test fails with the assertion.

- [ ] **Step 3.3: Update `context_service.py`**

Replace the file content of `backend/chat/services/context_service.py`:

```python
from django.conf import settings

from chat.models import ChatMessage
from chat.services.store import django_memory_store
from llm.services.prompt_service import render_prompt

FINMODPRO_SYSTEM_PROMPT = (
    "你是 FinModPro 平台内置的专业金融分析助手，服务于企业财务、风险、知识库和投研分析场景。"
    "当用户询问你是谁、能做什么或平台能力时，明确说明你是 FinModPro 的平台助手。"
    "回答应专业、审慎、结构清晰；不要编造数据或来源。"
    "只有在用户问题与提供的参考资料直接相关时才使用并引用资料。"
)


def _get_positive_int_setting(name, default):
    raw_value = getattr(settings, name, default)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return default


def _collapse_text(value):
    return " ".join(str(value or "").split()).strip()


def _format_recent_messages(messages):
    role_labels = {
        ChatMessage.ROLE_USER: "用户",
        ChatMessage.ROLE_ASSISTANT: "助手",
        ChatMessage.ROLE_SYSTEM: "系统",
    }
    lines = []
    for message in messages:
        content = _collapse_text(message.content)
        if not content:
            continue
        lines.append(f"- {role_labels.get(message.role, message.role)}: {content}")
    return "\n".join(lines)


def _format_memories(memories):
    lines = []
    for memory in memories:
        if isinstance(memory, dict):
            title = _collapse_text(memory.get("title"))
            content = _collapse_text(memory.get("content"))
        else:
            title = _collapse_text(getattr(memory, "title", ""))
            content = _collapse_text(getattr(memory, "content", ""))
        if not (title or content):
            continue
        if title and content:
            lines.append(f"- {title}: {content}")
        else:
            lines.append(f"- {title or content}")
    return "\n".join(lines)


def _format_citations(citations):
    lines = []
    for index, citation in enumerate(citations or [], start=1):
        document_title = citation.get("document_title", "未命名资料")
        page_label = citation.get("page_label") or "未标注位置"
        snippet = _collapse_text(citation.get("snippet"))
        lines.append(f"[{index}] {document_title} {page_label}: {snippet}")
    return "\n".join(lines)


def _build_context_sections(*, rolling_summary="", recent_messages=None, memories=None, citations=None):
    sections = []
    normalized_summary = _collapse_text(rolling_summary)
    if normalized_summary:
        sections.append(f"会话摘要:\n{normalized_summary}")

    recent_block = _format_recent_messages(recent_messages or [])
    if recent_block:
        sections.append(f"最近对话:\n{recent_block}")

    memory_block = _format_memories(memories or [])
    if memory_block:
        sections.append(f"长期记忆:\n{memory_block}")

    citation_block = _format_citations(citations or [])
    if citation_block:
        sections.append(f"参考资料:\n{citation_block}")

    return "\n\n".join(sections)


def _get_store():
    """Return the active store: graph-injected store when inside a graph node, module singleton otherwise."""
    try:
        from langgraph.config import get_store
        return get_store()
    except Exception:
        return django_memory_store


def _load_memories(*, user, question, dataset_id=None, limit=5):
    """Retrieve memories for a user via LangGraph store."""
    store = _get_store()
    user_ns = ("memories", str(user.id))
    items = store.search(user_ns, query=question, limit=limit)

    if dataset_id not in (None, ""):
        ds_ns = ("memories", str(user.id), "dataset", str(dataset_id))
        items = items + store.search(ds_ns, query=question, limit=limit)

    return [item.value for item in items]


def build_chat_messages(*, question, session=None, citations=None, filters=None):
    citations = citations or []

    recent_messages = []
    memories = []
    if session is not None:
        recent_message_limit = _get_positive_int_setting("CHAT_CONTEXT_RECENT_MESSAGES", 8)
        recent_messages = list(
            reversed(
                list(
                    session.messages.filter(status=ChatMessage.STATUS_COMPLETE).order_by(
                        "-sequence", "-id"
                    )[:recent_message_limit]
                )
            )
        )
        dataset_id = (filters or {}).get("dataset_id")
        memory_limit = _get_positive_int_setting("CHAT_MEMORY_RESULT_LIMIT", 5)
        memories = _load_memories(
            user=session.user,
            question=question,
            dataset_id=dataset_id,
            limit=memory_limit,
        )

    context = _build_context_sections(
        rolling_summary=getattr(session, "rolling_summary", ""),
        recent_messages=recent_messages,
        memories=memories,
        citations=citations,
    )
    if not context:
        return [
            {"role": "system", "content": FINMODPRO_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

    prompt = render_prompt(
        "chat/answer.txt",
        question=question,
        context=context,
    )
    return [
        {"role": "system", "content": FINMODPRO_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
```

- [ ] **Step 3.4: Run the test — verify it passes**

```bash
python manage.py test chat.tests.ContextServiceMemoryInjectionTests --keepdb 2>&1 | tail -10
```

Expected: `OK`

- [ ] **Step 3.5: Run full chat test suite**

```bash
python manage.py test chat --keepdb 2>&1 | tail -20
```

Expected: All previously-passing tests still pass.

- [ ] **Step 3.6: Commit**

```bash
git add backend/chat/services/context_service.py backend/chat/tests.py
git commit -m "feat(chat): use DjangoMemoryStore in context_service for memory retrieval

Replace icontains keyword search_memories() with store.search() via
_load_memories(). Falls back to module singleton when outside graph context.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Create the memory extraction LLM prompt

**Files:**
- Create: `backend/prompts/chat/extract_memories.txt`

- [ ] **Step 4.1: Create the prompt file**

```
以下是用户与助手的最近对话记录。

---
{conversation}
---

请仔细阅读对话，提取其中用户明确表达的、值得长期记住的信息。
仅提取以下四类内容：
- user_preference（用户偏好）：用户对输出格式、语言、风格的持久偏好
- work_rule（工作规则）：用户对助手行为的持久规则或要求
- confirmed_fact（已确认事实）：用户明确陈述的关于自身、所属机构或项目的客观事实
- project_background（项目背景）：用户工作涉及的特定背景信息

如果对话中没有值得记忆的内容，输出空数组。
最多提取 5 条，每条 confidence_score 在 0.0 到 1.0 之间（低于 0.7 的信息请省略）。

输出严格 JSON，不要输出额外文本：
[
  {{
    "title": "简短标题（10 字以内）",
    "content": "完整内容描述",
    "memory_type": "user_preference|work_rule|confirmed_fact|project_background",
    "confidence_score": 0.0
  }}
]
```

- [ ] **Step 4.2: Verify the prompt renders correctly**

```bash
cd backend && python -c "
from llm.services.prompt_service import render_prompt
out = render_prompt('chat/extract_memories.txt', conversation='用户: 请记住我喜欢英文输出\n助手: 好的')
print(out[:200])
"
```

Expected: The prompt text with `{conversation}` replaced.

- [ ] **Step 4.3: Commit**

```bash
git add backend/prompts/chat/extract_memories.txt
git commit -m "feat(chat): add LLM memory extraction prompt template

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Add `extract_memories_with_llm` to `memory_service.py`

**Files:**
- Modify: `backend/chat/services/memory_service.py`

Replace the keyword-based `extract_session_memories` with an LLM-based version. Keep all CRUD helpers (`list_memory_items_for_user`, `get_memory_item_for_user`, `set_memory_pin_state`, `delete_memory_item`, `record_memory_view`, `list_memory_evidence_for_memory`, `search_memories`). Remove the private keyword-extraction helpers.

- [ ] **Step 5.1: Write the failing test**

Add this class to `backend/chat/tests.py` (after `ContextServiceMemoryInjectionTests`):

```python
from unittest.mock import patch as _patch


class LlmMemoryExtractionTests(django.test.TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="llm-mem-user",
            password="pw",
            email="llmem@example.com",
        )
        self.session = ChatSession.objects.create(
            user=self.user,
            title="抽取测试",
            context_filters={},
        )
        ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="我是一名基金经理，请记住我偏好英文输出。",
            status=ChatMessage.STATUS_COMPLETE,
            sequence=1,
        )
        ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="好的，我记住了。",
            status=ChatMessage.STATUS_COMPLETE,
            sequence=2,
        )

    @_patch("chat.services.memory_service.get_chat_provider")
    def test_extract_saves_memories_to_store(self, mocked_provider):
        from chat.services.memory_service import extract_memories_with_llm
        from chat.services.store import DjangoMemoryStore
        import json as _json

        llm_response = _json.dumps([
            {
                "title": "用户身份",
                "content": "用户是基金经理",
                "memory_type": "confirmed_fact",
                "confidence_score": 0.9,
            },
            {
                "title": "输出语言偏好",
                "content": "用户偏好英文输出",
                "memory_type": "user_preference",
                "confidence_score": 0.95,
            },
        ])

        class FixedProvider:
            def chat(self, *, messages, options=None):
                return llm_response

        mocked_provider.return_value = FixedProvider()

        count = extract_memories_with_llm(session_id=self.session.id)

        self.assertEqual(count, 2)
        store = DjangoMemoryStore()
        ns = ("memories", str(self.user.id))
        items = store.search(ns)
        contents = [i.value["content"] for i in items]
        self.assertTrue(
            any("基金经理" in c for c in contents),
            f"Expected '基金经理' in memory contents, got: {contents}",
        )

    @_patch("chat.services.memory_service.get_chat_provider")
    def test_extract_skips_low_confidence(self, mocked_provider):
        from chat.services.memory_service import extract_memories_with_llm
        from chat.services.store import DjangoMemoryStore
        import json as _json

        llm_response = _json.dumps([
            {
                "title": "低置信度",
                "content": "这条信息不确定",
                "memory_type": "confirmed_fact",
                "confidence_score": 0.5,
            },
        ])

        class FixedProvider:
            def chat(self, *, messages, options=None):
                return llm_response

        mocked_provider.return_value = FixedProvider()

        count = extract_memories_with_llm(session_id=self.session.id)

        self.assertEqual(count, 0)
        store = DjangoMemoryStore()
        ns = ("memories", str(self.user.id))
        items = store.search(ns)
        self.assertEqual(len(items), 0)

    @_patch("chat.services.memory_service.get_chat_provider")
    def test_extract_returns_zero_on_empty_session(self, mocked_provider):
        from chat.services.memory_service import extract_memories_with_llm

        count = extract_memories_with_llm(session_id=999999)
        self.assertEqual(count, 0)
        mocked_provider.assert_not_called()

    @_patch("chat.services.memory_service.get_chat_provider")
    def test_extract_handles_malformed_llm_output_gracefully(self, mocked_provider):
        from chat.services.memory_service import extract_memories_with_llm

        class BrokenProvider:
            def chat(self, *, messages, options=None):
                return "这不是JSON格式的输出"

        mocked_provider.return_value = BrokenProvider()

        count = extract_memories_with_llm(session_id=self.session.id)
        self.assertEqual(count, 0)
```

- [ ] **Step 5.2: Run tests — verify they fail with ImportError**

```bash
python manage.py test chat.tests.LlmMemoryExtractionTests --keepdb 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'extract_memories_with_llm'`

- [ ] **Step 5.3: Rewrite `memory_service.py`**

Replace the entire file with:

```python
import hashlib
import json
import logging
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from chat.models import ChatMessage, ChatSession, MemoryActionLog, MemoryEvidence, MemoryItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers shared by CRUD and extraction
# ---------------------------------------------------------------------------

def _get_memory_limit(limit):
    raw_value = limit
    if raw_value in (None, ""):
        raw_value = getattr(settings, "CHAT_MEMORY_RESULT_LIMIT", 5)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return 5


def _normalize_text(value):
    return " ".join(str(value or "").split()).strip()


def _get_dataset_scope_key(session):
    context_filters = getattr(session, "context_filters", None)
    if not isinstance(context_filters, dict):
        return ""
    dataset_id = context_filters.get("dataset_id")
    if dataset_id in (None, ""):
        return ""
    return str(dataset_id)


def _build_memory_fingerprint(*, user_id, namespace, memory_type, content):
    fingerprint_source = f"{user_id}|{namespace}|{memory_type}|{content}"
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CRUD helpers (unchanged public API)
# ---------------------------------------------------------------------------

def list_memory_items_for_user(*, user, scope_type="", scope_key="", query=""):
    queryset = MemoryItem.objects.filter(
        user=user,
        status=MemoryItem.STATUS_ACTIVE,
    )

    normalized_scope_type = str(scope_type or "").strip()
    if normalized_scope_type:
        queryset = queryset.filter(scope_type=normalized_scope_type)

    normalized_scope_key = str(scope_key or "").strip()
    if normalized_scope_key:
        queryset = queryset.filter(scope_key=normalized_scope_key)

    normalized_query = _normalize_text(query)
    if normalized_query:
        for token in normalized_query.split():
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content__icontains=token)
            )

    return list(queryset.order_by("-pinned", "-updated_at", "-id"))


def get_memory_item_for_user(*, user, memory_id):
    return MemoryItem.objects.get(id=memory_id, user=user)


def list_memory_evidence_for_memory(*, memory_item):
    return list(memory_item.evidence_items.order_by("-created_at", "-id"))


def record_memory_view(*, memory_item, actor_user):
    return MemoryActionLog.objects.create(
        memory_item=memory_item,
        actor_user=actor_user,
        action=MemoryActionLog.ACTION_VIEW,
        details_json={},
    )


def set_memory_pin_state(*, memory_item, actor_user, pinned):
    with transaction.atomic():
        memory_item.pinned = pinned
        memory_item.save(update_fields=["pinned", "updated_at"])
        MemoryActionLog.objects.create(
            memory_item=memory_item,
            actor_user=actor_user,
            action=MemoryActionLog.ACTION_PIN if pinned else MemoryActionLog.ACTION_UNPIN,
            details_json={"pinned": pinned},
        )
    return memory_item


def delete_memory_item(*, memory_item, actor_user):
    with transaction.atomic():
        memory_item.status = MemoryItem.STATUS_DELETED
        memory_item.save(update_fields=["status", "updated_at"])
        MemoryActionLog.objects.create(
            memory_item=memory_item,
            actor_user=actor_user,
            action=MemoryActionLog.ACTION_DELETE,
            details_json={},
        )
    return memory_item


def search_memories(*, user, query="", dataset_id=None, limit=None):
    """Thin keyword search kept for backward compatibility. Prefer store.search() for new code."""
    queryset = MemoryItem.objects.filter(
        user=user,
        status=MemoryItem.STATUS_ACTIVE,
    )

    scope_filter = Q(scope_type=MemoryItem.SCOPE_USER_GLOBAL)
    if dataset_id not in (None, ""):
        scope_filter |= Q(
            scope_type=MemoryItem.SCOPE_DATASET,
            scope_key=str(dataset_id),
        )
    queryset = queryset.filter(scope_filter)

    normalized_query = _normalize_text(query)
    if normalized_query:
        for token in normalized_query.split():
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content__icontains=token)
            )

    return list(queryset[: _get_memory_limit(limit)])


# ---------------------------------------------------------------------------
# LLM-based extraction (replaces keyword-based extract_session_memories)
# ---------------------------------------------------------------------------

def _parse_memory_extraction_output(raw_text: str) -> list:
    text = str(raw_text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        text = array_match.group(0)
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        return []
    return parsed


def extract_memories_with_llm(*, session_id: int) -> int:
    """Extract memorable facts from the session's recent messages using an LLM.

    Returns the number of memories written to the store.
    """
    from llm.services.runtime_service import get_chat_provider
    from llm.services.prompt_service import render_prompt
    from chat.services.store import DjangoMemoryStore

    session = ChatSession.objects.select_related("user").filter(id=session_id).first()
    if session is None:
        return 0

    message_limit = getattr(settings, "CHAT_MEMORY_EXTRACTION_MESSAGES", 6)
    messages = list(
        session.messages.filter(
            status=ChatMessage.STATUS_COMPLETE,
        ).order_by("-sequence", "-id")[:message_limit]
    )
    if not messages:
        return 0
    messages = list(reversed(messages))

    role_labels = {
        ChatMessage.ROLE_USER: "用户",
        ChatMessage.ROLE_ASSISTANT: "助手",
    }
    conversation_lines = []
    for msg in messages:
        label = role_labels.get(msg.role, msg.role)
        content = _normalize_text(msg.content)
        if content:
            conversation_lines.append(f"{label}: {content}")
    if not conversation_lines:
        return 0

    conversation = "\n".join(conversation_lines)
    prompt = render_prompt("chat/extract_memories.txt", conversation=conversation)

    try:
        provider = get_chat_provider()
        raw_output = provider.chat(
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "max_tokens": 512},
        )
    except Exception:
        logger.exception("Memory extraction LLM call failed", extra={"session_id": session_id})
        return 0

    try:
        extracted = _parse_memory_extraction_output(raw_output)
    except Exception:
        logger.warning(
            "Memory extraction output parse failed",
            extra={"session_id": session_id, "raw": str(raw_output)[:200]},
        )
        return 0

    confidence_threshold = getattr(settings, "CHAT_MEMORY_CONFIDENCE_THRESHOLD", 0.7)
    store = DjangoMemoryStore()
    dataset_scope_key = _get_dataset_scope_key(session)
    saved_count = 0

    for item in extracted[:5]:
        confidence = float(item.get("confidence_score", 0))
        if confidence < confidence_threshold:
            continue

        content = _normalize_text(item.get("content", ""))
        if not content:
            continue

        memory_type = item.get("memory_type", MemoryItem.TYPE_CONFIRMED_FACT)
        if memory_type == MemoryItem.TYPE_WORK_RULE and dataset_scope_key:
            namespace = ("memories", str(session.user_id), "dataset", dataset_scope_key)
        else:
            namespace = ("memories", str(session.user_id))

        fingerprint = _build_memory_fingerprint(
            user_id=session.user_id,
            namespace=str(namespace),
            memory_type=memory_type,
            content=content,
        )

        store.put(
            namespace,
            fingerprint,
            {
                "title": str(item.get("title", ""))[:255],
                "content": content,
                "memory_type": memory_type,
                "confidence_score": confidence,
                "pinned": False,
                "source_kind": MemoryItem.SOURCE_AUTO,
            },
        )
        saved_count += 1

    return saved_count
```

- [ ] **Step 5.4: Run the extraction tests**

```bash
python manage.py test chat.tests.LlmMemoryExtractionTests --keepdb 2>&1 | tail -10
```

Expected: `OK` with 4 tests passing.

- [ ] **Step 5.5: Run the full chat test suite**

```bash
python manage.py test chat --keepdb 2>&1 | tail -20
```

Expected: All tests pass (the only thing that might break is the import of `extract_session_memories` in `tests.py` line 19 and `tasks.py` line 3 — those are fixed in Tasks 6 and 7 below).

- [ ] **Step 5.6: Commit**

```bash
git add backend/chat/services/memory_service.py backend/chat/tests.py
git commit -m "feat(chat): replace keyword extraction with LLM-based extract_memories_with_llm

Add extract_memories_with_llm() which calls the active chat provider with
a structured extraction prompt and writes results to DjangoMemoryStore.
Keep search_memories() as a thin backward-compat wrapper.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Update `tasks.py` and fix stale imports in `tests.py`

**Files:**
- Modify: `backend/chat/tasks.py`
- Modify: `backend/chat/tests.py` (line 19)

- [ ] **Step 6.1: Update `tasks.py`**

Replace the file:

```python
from celery import shared_task

from chat.services.memory_service import extract_memories_with_llm
from chat.services.summary_service import update_session_summary
from chat.services.title_service import generate_session_title


@shared_task(name="chat.update_session_title_task")
def update_session_title_task(session_id):
    return generate_session_title(session_id=session_id)


@shared_task(name="chat.update_session_summary_task")
def update_session_summary_task(session_id):
    return update_session_summary(session_id=session_id)


@shared_task(name="chat.extract_session_memories_task")
def extract_session_memories_task(session_id):
    return extract_memories_with_llm(session_id=session_id)
```

- [ ] **Step 6.2: Fix the stale import in `tests.py`**

In `backend/chat/tests.py`, change line 19 from:

```python
from chat.services.memory_service import delete_memory_item, extract_session_memories, set_memory_pin_state
```

to:

```python
from chat.services.memory_service import delete_memory_item, set_memory_pin_state
```

- [ ] **Step 6.3: Run full test suite**

```bash
python manage.py test chat --keepdb 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 6.4: Commit**

```bash
git add backend/chat/tasks.py backend/chat/tests.py
git commit -m "fix(chat): update tasks.py and tests.py to use extract_memories_with_llm

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Integration verification

This task confirms the end-to-end flow: a user says something memorable, the Celery task extracts it, and a follow-up question receives the memory in context.

- [ ] **Step 7.1: Add integration test**

Add this test class to `backend/chat/tests.py`:

```python
from unittest.mock import patch as _patch2


class MemoryIntegrationTests(django.test.TestCase):
    """End-to-end: extraction → storage → retrieval in context."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mem-integration-user",
            password="pw",
            email="memint@example.com",
        )
        self.session = ChatSession.objects.create(
            user=self.user,
            title="集成测试",
            context_filters={},
        )

    @_patch2("chat.services.memory_service.get_chat_provider")
    def test_extracted_memory_appears_in_next_turn_context(self, mocked_llm):
        import json as _json
        from chat.services.memory_service import extract_memories_with_llm
        from chat.services.context_service import build_chat_messages

        # User says something memorable
        ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="我在华夏基金担任首席风控官。",
            status=ChatMessage.STATUS_COMPLETE,
            sequence=1,
        )
        ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="明白了，您是风控官。",
            status=ChatMessage.STATUS_COMPLETE,
            sequence=2,
        )

        llm_resp = _json.dumps([{
            "title": "用户职位",
            "content": "用户在华夏基金担任首席风控官",
            "memory_type": "confirmed_fact",
            "confidence_score": 0.95,
        }])

        class OneShot:
            def chat(self, *, messages, options=None):
                return llm_resp

        mocked_llm.return_value = OneShot()

        # Simulate Celery task
        saved = extract_memories_with_llm(session_id=self.session.id)
        self.assertEqual(saved, 1)

        # Next turn: build the prompt for the follow-up question
        messages = build_chat_messages(
            session=self.session,
            question="帮我分析一下流动性风险",
            citations=[],
            filters={},
        )

        full_prompt = " ".join(m["content"] for m in messages)
        self.assertIn("华夏基金", full_prompt, "Extracted memory must appear in follow-up prompt")
```

- [ ] **Step 7.2: Run the integration test**

```bash
python manage.py test chat.tests.MemoryIntegrationTests --keepdb 2>&1 | tail -10
```

Expected: `OK`

- [ ] **Step 7.3: Run the complete test suite one final time**

```bash
python manage.py test chat --keepdb 2>&1 | tail -20
```

Expected: All tests pass, no regressions.

- [ ] **Step 7.4: Commit**

```bash
git add backend/chat/tests.py
git commit -m "test(chat): add LangGraph memory migration integration test

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `DjangoMemoryStore(BaseStore)` wrapping `MemoryItem` — Task 1
- [x] Fix `session=None` bug — Task 2
- [x] Compile graph with `store=` — Task 2
- [x] Replace `search_memories()` with `store.search()` — Task 3
- [x] LLM extraction prompt — Task 4
- [x] LLM extraction function — Task 5
- [x] Celery task updated — Task 6
- [x] Stale imports fixed — Task 6
- [x] End-to-end integration test — Task 7

**Spec items NOT in scope (deferred to P2 per design doc):**
- Semantic/vector memory search (keep text search for now)
- `MemoryCheckpointer` for `ChatSession`/`ChatMessage` (no MySQL checkpointer upstream)

**Type consistency check:**
- `DjangoMemoryStore.put(namespace, key, value_dict)` — called by `extract_memories_with_llm` ✓
- `DjangoMemoryStore.search(namespace_prefix, query=, limit=)` — called by `_load_memories()` ✓
- `Item.value` is a dict with keys `title/content/memory_type/confidence_score/pinned/source_kind` — consistent across all tasks ✓
- `extract_memories_with_llm(session_id=int)` → `int` — called by `tasks.py` ✓
- `build_chat_messages(session=, question=, citations=, filters=)` — signature unchanged ✓
