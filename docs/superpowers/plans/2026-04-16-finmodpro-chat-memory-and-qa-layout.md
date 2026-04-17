# FinModPro Chat Memory And QA Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build durable chat memory foundations for FinModPro, including complete message persistence, AI-generated session titles, rolling summaries, user-governed long-term memory, and a larger B1-style QA canvas with button-driven history and memory drawers.

**Architecture:** Keep `chat` as the source-of-truth app for session data and derived memory. Persist final facts in MySQL, use Celery/Redis for title/summary/memory maintenance work, and keep the frontend on the current workspace route tree while shrinking the left workspace rail and moving history/memory into drawers.

**Tech Stack:** Django, existing `chat` app, Celery, Redis-backed cache/broker when enabled, Vue 3, Element Plus drawers, Node test runner, Django test runner

---

## Scope

### In Scope

- Full user and assistant transcript persistence
- Session metadata fields for AI titles, rolling summaries, and counters
- Long-term memory tables with user-global and generic scoped records
- Memory governance APIs: list, evidence, delete, pin
- Context assembly order: summary -> recent messages -> memories -> RAG
- QA page conversion to large-canvas B1 layout
- Workspace sidebar compaction to icon rail for workspace routes

### Out of Scope

- Adding a new external memory platform such as Mem0 or Zep
- Adding a new project-domain model just to satisfy memory scope
- Vectorized long-term memory retrieval in phase one
- Collaborative/shared chat sessions
- Manual free-form memory authoring UI

## Locked Decisions

- `ChatMessage` remains the source of truth; titles, summaries, and memories are derived layers.
- Long-term memory scope is stored as generic `scope_type + scope_key`; phase one uses `user_global` and `dataset`, while `project` is reserved at the API/model level.
- Celery tasks must be non-blocking for the ask/stream endpoints; failures never block chat responses.
- Frontend verification must stay inside the existing `node --test` + build workflow; do not introduce a component test library.

## File Structure

### Backend

- `backend/chat/models.py`
- `backend/chat/migrations/0003_chat_memory_foundation.py`
- `backend/chat/serializers.py`
- `backend/chat/services/session_service.py`
- `backend/chat/services/ask_service.py`
- `backend/chat/services/context_service.py`
- `backend/chat/services/title_service.py`
- `backend/chat/services/summary_service.py`
- `backend/chat/services/memory_service.py`
- `backend/chat/tasks.py`
- `backend/chat/controllers/memory_controller.py`
- `backend/chat/controllers/__init__.py`
- `backend/chat/urls.py`
- `backend/chat/tests.py`
- `backend/config/settings.py`
- `backend/.env.example`
- `backend/README.md`
- `backend/docs/dependency-services.md`

### Frontend

- `frontend/src/api/chat.js`
- `frontend/src/api/__tests__/chat.test.js`
- `frontend/src/components/FinancialQA.vue`
- `frontend/src/components/ChatHistory.vue`
- `frontend/src/components/ChatMemoryDrawer.vue`
- `frontend/src/components/ui/AppSidebar.vue`
- `frontend/src/layouts/WorkspaceLayout.vue`
- `frontend/src/style.css`
- `frontend/src/lib/workspace-qa.js`
- `frontend/src/lib/chat-memory.js`
- `frontend/src/lib/__tests__/workspace-qa.test.js`
- `frontend/src/lib/__tests__/chat-memory.test.js`
- `frontend/src/views/workspace/WorkspaceHistoryView.vue`

## API Contract

### Session list/detail additions

`GET /api/chat/sessions`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessions": [
      {
        "id": 18,
        "title": "流动性压力测试结论整理",
        "title_status": "ready",
        "rolling_summary": "用户正在围绕数据集 7 追问流动性与偿债能力。",
        "last_message_preview": "已整理出三项高优先级关注点。",
        "message_count": 6,
        "last_message_at": "2026-04-16T19:00:00+08:00",
        "context_filters": {"dataset_id": 7}
      }
    ]
  }
}
```

### Memory governance endpoints

- `GET /api/chat/memories?scope_type=user_global&q=偏好`
- `GET /api/chat/memories?scope_type=dataset&scope_key=7`
- `GET /api/chat/memories/<id>/evidence`
- `POST /api/chat/memories/<id>/pin`
- `DELETE /api/chat/memories/<id>`

Pin request:

```json
{
  "pinned": true
}
```

List response item:

```json
{
  "id": 9,
  "memory_type": "user_preference",
  "scope_type": "dataset",
  "scope_key": "7",
  "title": "用户偏好结果先给表格",
  "content": "在数据集问答里先给结构化结论，再展开依据。",
  "pinned": true,
  "confidence_score": 0.94,
  "source_kind": "auto",
  "status": "active",
  "updated_at": "2026-04-16T19:08:00+08:00"
}
```

## Task 1: Add failing backend tests for session truth and memory foundations

**Files:**
- Modify: `backend/chat/tests.py`

- [ ] **Step 1: Add model and API expectations for new session metadata**

```python
def test_chat_session_defaults_pending_title_and_summary_fields(self):
    session = ChatSession.objects.create(user=self.user)
    self.assertEqual(session.title, "新对话")
    self.assertEqual(session.title_status, ChatSession.TITLE_STATUS_PENDING)
    self.assertEqual(session.rolling_summary, "")
    self.assertEqual(session.message_count, 0)
    self.assertIsNone(session.last_message_at)
```

- [ ] **Step 2: Add ask-flow expectations for full transcript persistence**

```python
@patch("chat.services.ask_service.retrieve", return_value=[])
def test_chat_stream_finalizes_assistant_message_and_session_counters(self, mocked_retrieve):
    session = ChatSession.objects.create(user=self.user, context_filters={"dataset_id": 7})
    response = self.client.post(
        "/api/chat/ask/stream",
        data=json.dumps({"question": "cash flow outlook", "session_id": session.id}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
    )
    self.assertEqual(response.status_code, 200)
    session.refresh_from_db()
    self.assertEqual(session.message_count, 2)
    self.assertIsNotNone(session.last_message_at)
    assistant = session.messages.filter(role=ChatMessage.ROLE_ASSISTANT).get()
    self.assertEqual(assistant.status, ChatMessage.STATUS_COMPLETE)
    self.assertEqual(assistant.content, "cash flow outlook")
```

- [ ] **Step 3: Add memory model and governance endpoint tests**

```python
def test_memory_item_supports_user_global_and_dataset_scopes(self):
    global_item = MemoryItem.objects.create(
        user=self.user,
        scope_type=MemoryItem.SCOPE_USER_GLOBAL,
        scope_key="",
        memory_type=MemoryItem.TYPE_USER_PREFERENCE,
        title="偏好结构化回答",
        content="先给结论后给依据。",
    )
    dataset_item = MemoryItem.objects.create(
        user=self.user,
        scope_type=MemoryItem.SCOPE_DATASET,
        scope_key="7",
        memory_type=MemoryItem.TYPE_WORK_RULE,
        title="数据集 7 长期关注点",
        content="重点跟踪流动性恶化。",
    )
    self.assertFalse(global_item.pinned)
    self.assertEqual(dataset_item.scope_key, "7")
```

- [ ] **Step 4: Run targeted backend tests to confirm failure**

Run: `cd backend && .venv/bin/python manage.py test chat.tests -v 2`

Expected: FAIL on missing `title_status`, `rolling_summary`, `message_count`, `MemoryItem`, and missing memory endpoints.

- [ ] **Step 5: Commit the red test baseline**

```bash
git add backend/chat/tests.py
git commit -m "test(chat): lock memory and session truth expectations"
```

## Task 2: Implement backend models, migration, and session serialization

**Files:**
- Modify: `backend/chat/models.py`
- Create: `backend/chat/migrations/0003_chat_memory_foundation.py`
- Modify: `backend/chat/serializers.py`
- Modify: `backend/chat/services/session_service.py`
- Modify: `backend/chat/tests.py`

- [ ] **Step 1: Add session/message metadata fields and long-term memory tables**

```python
class ChatSession(models.Model):
    TITLE_STATUS_PENDING = "pending"
    TITLE_STATUS_READY = "ready"
    TITLE_STATUS_FAILED = "failed"
    TITLE_STATUS_CHOICES = (
        (TITLE_STATUS_PENDING, "Pending"),
        (TITLE_STATUS_READY, "Ready"),
        (TITLE_STATUS_FAILED, "Failed"),
    )

    title_status = models.CharField(
        max_length=16,
        choices=TITLE_STATUS_CHOICES,
        default=TITLE_STATUS_PENDING,
    )
    title_source = models.CharField(max_length=32, default="ai")
    rolling_summary = models.TextField(blank=True, default="")
    summary_updated_through_message_id = models.PositiveBigIntegerField(blank=True, null=True)
    message_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(blank=True, null=True)


class ChatMessage(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    status = models.CharField(max_length=16, default=STATUS_COMPLETE)
    citations_json = models.JSONField(default=list, blank=True)
    model_metadata_json = models.JSONField(default=dict, blank=True)
    client_message_id = models.CharField(max_length=64, blank=True, default="")


class MemoryItem(models.Model):
    SCOPE_USER_GLOBAL = "user_global"
    SCOPE_DATASET = "dataset"
    SCOPE_PROJECT = "project"
    TYPE_USER_PREFERENCE = "user_preference"
    TYPE_PROJECT_BACKGROUND = "project_background"
    TYPE_CONFIRMED_FACT = "confirmed_fact"
    TYPE_WORK_RULE = "work_rule"
```

- [ ] **Step 2: Extend serializers and session helpers**

```python
class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = [
            "id",
            "session_id",
            "user_id",
            "title",
            "title_status",
            "title_source",
            "rolling_summary",
            "message_count",
            "last_message_at",
            "context_filters",
            "created_at",
            "updated_at",
        ]
```

- [ ] **Step 3: Update session persistence helpers to track counters and previews**

```python
def create_session_message(*, session, role, content, status=ChatMessage.STATUS_COMPLETE, **extra_fields):
    message = ChatMessage.objects.create(
        session=session,
        role=role,
        content=content,
        status=status,
        **extra_fields,
    )
    ChatSession.objects.filter(id=session.id).update(
        message_count=F("message_count") + 1,
        last_message_at=timezone.now(),
        updated_at=timezone.now(),
    )
    return message


def finalize_session_message(*, message, content, citations=None, model_metadata=None):
    message.content = content
    message.status = ChatMessage.STATUS_COMPLETE
    message.citations_json = citations or []
    message.model_metadata_json = model_metadata or {}
    message.save(update_fields=["content", "status", "citations_json", "model_metadata_json", "updated_at"])
    ChatSession.objects.filter(id=message.session_id).update(
        last_message_at=timezone.now(),
        updated_at=timezone.now(),
    )
```

- [ ] **Step 4: Rerun backend tests and migrate schema**

Run: `cd backend && .venv/bin/python manage.py test chat.tests -v 2`

Expected: PASS for model defaults and serializer fields; remaining failures should now concentrate in ask-flow maintenance and missing memory endpoints.

- [ ] **Step 5: Commit the schema foundation**

```bash
git add backend/chat/models.py backend/chat/migrations/0003_chat_memory_foundation.py backend/chat/serializers.py backend/chat/services/session_service.py backend/chat/tests.py
git commit -m "feat(chat): add memory and session metadata foundations"
```

## Task 3: Rework ask/stream flow and add Celery-backed title, summary, and memory maintenance

**Files:**
- Modify: `backend/chat/services/ask_service.py`
- Modify: `backend/chat/services/session_service.py`
- Create: `backend/chat/services/context_service.py`
- Create: `backend/chat/services/title_service.py`
- Create: `backend/chat/services/summary_service.py`
- Create: `backend/chat/services/memory_service.py`
- Create: `backend/chat/tasks.py`
- Modify: `backend/chat/tests.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/.env.example`
- Modify: `backend/README.md`
- Modify: `backend/docs/dependency-services.md`

- [ ] **Step 1: Add failing tests for context assembly order and task dispatch**

```python
@patch("chat.tasks.update_session_title_task.delay")
@patch("chat.tasks.update_session_summary_task.delay")
@patch("chat.tasks.extract_session_memories_task.delay")
def test_chat_ask_dispatches_maintenance_tasks(self, mock_memory, mock_summary, mock_title):
    session = ChatSession.objects.create(user=self.user, context_filters={"dataset_id": 7})
    response = self.client.post(
        "/api/chat/ask",
        data=json.dumps({"question": "liquidity outlook", "session_id": session.id}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
    )
    self.assertEqual(response.status_code, 200)
    mock_title.assert_called_once_with(session.id)
    mock_summary.assert_called_once_with(session.id)
    mock_memory.assert_called_once_with(session.id)
```

- [ ] **Step 2: Build a dedicated context service with fixed ordering**

```python
def build_chat_context(*, session, question, retrieval_payload, filters):
    recent_messages = list(
        session.messages.filter(status=ChatMessage.STATUS_COMPLETE)
        .order_by("-sequence", "-id")[: settings.CHAT_CONTEXT_RECENT_MESSAGES]
    )
    memories = search_memories(
        user=session.user,
        query=question,
        dataset_id=filters.get("dataset_id"),
        limit=settings.CHAT_MEMORY_RESULT_LIMIT,
    )
    return render_chat_prompt(
        question=question,
        rolling_summary=session.rolling_summary,
        recent_messages=list(reversed(recent_messages)),
        memories=memories,
        citations=retrieval_payload["citations"],
    )
```

- [ ] **Step 3: Persist user messages immediately, finalize assistant messages after generation, and enqueue maintenance tasks**

```python
create_session_message(
    session=session,
    role=ChatMessage.ROLE_USER,
    content=question,
    status=ChatMessage.STATUS_COMPLETE,
)
assistant_message = create_session_message(
    session=session,
    role=ChatMessage.ROLE_ASSISTANT,
    content="",
    status=ChatMessage.STATUS_PENDING,
)
answer = get_chat_provider().chat(messages=payload["messages"])
finalize_session_message(
    message=assistant_message,
    content=answer,
    citations=payload["citations"],
    model_metadata={"answer_mode": payload["answer_mode"]},
)
dispatch_session_maintenance_tasks(session_id=session.id)
```

- [ ] **Step 4: Add Celery tasks and runtime settings/env docs**

```python
@shared_task(name="chat.update_session_title_task")
def update_session_title_task(session_id):
    generate_session_title(session_id=session_id)


@shared_task(name="chat.update_session_summary_task")
def update_session_summary_task(session_id):
    update_session_summary(session_id=session_id)


@shared_task(name="chat.extract_session_memories_task")
def extract_session_memories_task(session_id):
    extract_session_memories(session_id=session_id)
```

Add settings/env defaults:

```python
CHAT_CONTEXT_RECENT_MESSAGES = get_int_env("CHAT_CONTEXT_RECENT_MESSAGES", 8)
CHAT_MEMORY_RESULT_LIMIT = get_int_env("CHAT_MEMORY_RESULT_LIMIT", 5)
CHAT_SUMMARY_TRIGGER_MESSAGES = get_int_env("CHAT_SUMMARY_TRIGGER_MESSAGES", 6)
```

- [ ] **Step 5: Run backend verification and commit**

Run: `cd backend && .venv/bin/python manage.py test chat.tests -v 2`

Expected: PASS for chat ask/stream persistence, context ordering, and maintenance task dispatch.

```bash
git add backend/chat/services/ask_service.py backend/chat/services/session_service.py backend/chat/services/context_service.py backend/chat/services/title_service.py backend/chat/services/summary_service.py backend/chat/services/memory_service.py backend/chat/tasks.py backend/chat/tests.py backend/config/settings.py backend/.env.example backend/README.md backend/docs/dependency-services.md
git commit -m "feat(chat): derive titles summaries and memories from session truth"
```

## Task 4: Add memory governance APIs and evidence serialization

**Files:**
- Create: `backend/chat/controllers/memory_controller.py`
- Modify: `backend/chat/controllers/__init__.py`
- Modify: `backend/chat/serializers.py`
- Modify: `backend/chat/urls.py`
- Modify: `backend/chat/services/memory_service.py`
- Modify: `backend/chat/tests.py`

- [ ] **Step 1: Add failing tests for list, evidence, pin, and delete**

```python
def test_memory_list_filters_by_scope_and_query(self):
    MemoryItem.objects.create(
        user=self.user,
        scope_type=MemoryItem.SCOPE_USER_GLOBAL,
        scope_key="",
        memory_type=MemoryItem.TYPE_USER_PREFERENCE,
        title="偏好表格",
        content="先给表格再给解释。",
    )
    response = self.client.get(
        "/api/chat/memories?scope_type=user_global&q=表格",
        HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
    )
    self.assertEqual(response.status_code, 200)
    self.assertEqual(len(response.json()["data"]["memories"]), 1)
```

- [ ] **Step 2: Add serializers and service helpers for governance**

```python
class MemoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemoryItem
        fields = [
            "id",
            "memory_type",
            "scope_type",
            "scope_key",
            "title",
            "content",
            "confidence_score",
            "source_kind",
            "status",
            "pinned",
            "updated_at",
        ]
```

- [ ] **Step 3: Wire the new controller endpoints into `chat/urls.py`**

```python
urlpatterns = [
    path("ask", chat_ask_view, name="chat-ask"),
    path("ask/stream", chat_ask_stream_view, name="chat-ask-stream"),
    path("sessions", ChatSessionCreateView.as_view(), name="chat-session-create"),
    path("sessions/<int:session_id>", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("sessions/<int:session_id>/export", ChatSessionExportView.as_view(), name="chat-session-export"),
    path("memories", ChatMemoryListView.as_view(), name="chat-memory-list"),
    path("memories/<int:memory_id>/evidence", ChatMemoryEvidenceView.as_view(), name="chat-memory-evidence"),
    path("memories/<int:memory_id>/pin", ChatMemoryPinView.as_view(), name="chat-memory-pin"),
    path("memories/<int:memory_id>", ChatMemoryDeleteView.as_view(), name="chat-memory-delete"),
]
```

- [ ] **Step 4: Verify the new API surface**

Run: `cd backend && .venv/bin/python manage.py test chat.tests -v 2`

Expected: PASS for memory list, evidence, pin, delete, and owner scoping.

- [ ] **Step 5: Commit the governance API**

```bash
git add backend/chat/controllers/memory_controller.py backend/chat/controllers/__init__.py backend/chat/serializers.py backend/chat/urls.py backend/chat/services/memory_service.py backend/chat/tests.py
git commit -m "feat(chat): add governed memory APIs"
```

## Task 5: Add frontend adapters, memory helpers, and the B1 QA canvas

**Files:**
- Modify: `frontend/src/api/chat.js`
- Create: `frontend/src/api/__tests__/chat.test.js`
- Modify: `frontend/src/lib/workspace-qa.js`
- Modify: `frontend/src/lib/__tests__/workspace-qa.test.js`
- Create: `frontend/src/lib/chat-memory.js`
- Create: `frontend/src/lib/__tests__/chat-memory.test.js`
- Create: `frontend/src/components/ChatMemoryDrawer.vue`
- Modify: `frontend/src/components/FinancialQA.vue`
- Modify: `frontend/src/components/ChatHistory.vue`
- Modify: `frontend/src/components/ui/AppSidebar.vue`
- Modify: `frontend/src/layouts/WorkspaceLayout.vue`
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/views/workspace/WorkspaceHistoryView.vue`

- [ ] **Step 1: Add failing frontend tests for session normalization and memory helpers**

```javascript
test('normalizeSession keeps title status and rolling summary fields', () => {
  const session = normalizeSession({
    session: {
      id: 3,
      title: '流动性会话',
      title_status: 'ready',
      rolling_summary: '用户持续追问流动性。',
      message_count: 4,
    },
  });

  assert.equal(session.titleStatus, 'ready');
  assert.equal(session.rollingSummary, '用户持续追问流动性。');
  assert.equal(session.messageCount, 4);
});
```

- [ ] **Step 2: Extend `chatApi` and add memory normalization helpers**

```javascript
export function normalizeMemoryItems(items = []) {
  return items.map((item) => ({
    id: item.id,
    title: item.title || '未命名记忆',
    content: item.content || '',
    pinned: Boolean(item.pinned),
    scopeType: item.scope_type || 'user_global',
    scopeKey: item.scope_key || '',
    scopeLabel: buildMemoryScopeLabel(item.scope_type, item.scope_key),
    updatedAt: item.updated_at || '',
  }));
}
```

- [ ] **Step 3: Convert `FinancialQA.vue` into the B1 canvas with button-driven history and memory drawers**

```vue
<div class="qa-shell__actions">
  <button class="ghost-btn" type="button" @click="historyDrawerOpen = true">历史会话</button>
  <button class="ghost-btn" type="button" @click="memoryDrawerOpen = true">记忆</button>
  <button class="ghost-btn ghost-btn--primary" type="button" @click="startNewConversation">新对话</button>
</div>

<ChatMemoryDrawer
  v-model:open="memoryDrawerOpen"
  :items="memoryItems"
  :is-loading="isLoadingMemories"
  @refresh="refreshMemories"
  @pin="toggleMemoryPin"
  @remove="deleteMemory"
  @open-evidence="openMemoryEvidence"
/>
```

- [ ] **Step 4: Compact the workspace sidebar to an icon rail without changing routes**

```vue
<aside class="app-sidebar" :class="{ 'app-sidebar--workspace-compact': props.area === 'workspace' }">
  <RouterLink v-for="item in group.items" :key="item.id" :to="item.to" class="app-sidebar__item" :title="item.label">
    <span class="app-sidebar__item-icon"><AppIcon :name="item.icon" /></span>
    <span class="app-sidebar__item-label">{{ item.label }}</span>
  </RouterLink>
</aside>
```

- [ ] **Step 5: Run frontend verification and commit**

Run:

```bash
cd frontend && node --test src/api/__tests__/chat.test.js src/lib/__tests__/workspace-qa.test.js src/lib/__tests__/chat-memory.test.js
cd frontend && npm run build
```

Expected: PASS, with the workspace QA route still building under the compact rail and new drawers.

```bash
git add frontend/src/api/chat.js frontend/src/api/__tests__/chat.test.js frontend/src/lib/workspace-qa.js frontend/src/lib/__tests__/workspace-qa.test.js frontend/src/lib/chat-memory.js frontend/src/lib/__tests__/chat-memory.test.js frontend/src/components/ChatMemoryDrawer.vue frontend/src/components/FinancialQA.vue frontend/src/components/ChatHistory.vue frontend/src/components/ui/AppSidebar.vue frontend/src/layouts/WorkspaceLayout.vue frontend/src/style.css frontend/src/views/workspace/WorkspaceHistoryView.vue
git commit -m "feat(frontend): turn QA into a governed large-canvas chat workspace"
```

## Task 6: Run full verification and land the finished slice

- [ ] **Step 1: Run backend verification**

Run:

```bash
cd backend && .venv/bin/python manage.py check
cd backend && .venv/bin/python manage.py test chat.tests -v 2
```

Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run:

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Validate manual smoke checks**

Check:

- New chat opens with `新对话` and later updates to an AI title.
- A multi-turn session preserves every user and assistant message.
- History drawer shows AI titles and latest preview.
- Memory drawer can list, pin, delete, and open evidence for returned memories.
- Workspace left rail remains navigable while leaving more room for the chat canvas.

- [ ] **Step 4: Commit the verified feature**

```bash
git add backend/chat backend/config/settings.py backend/.env.example backend/README.md backend/docs/dependency-services.md frontend/src/api/chat.js frontend/src/api/__tests__/chat.test.js frontend/src/lib/workspace-qa.js frontend/src/lib/__tests__/workspace-qa.test.js frontend/src/lib/chat-memory.js frontend/src/lib/__tests__/chat-memory.test.js frontend/src/components/ChatMemoryDrawer.vue frontend/src/components/FinancialQA.vue frontend/src/components/ChatHistory.vue frontend/src/components/ui/AppSidebar.vue frontend/src/layouts/WorkspaceLayout.vue frontend/src/style.css frontend/src/views/workspace/WorkspaceHistoryView.vue docs/superpowers/plans/2026-04-16-finmodpro-chat-memory-and-qa-layout.md
git commit -m "feat(chat): add durable memory and large-canvas QA workflows"
```

## Acceptance Checklist

- [ ] Session titles are AI-generated and asynchronously backfilled
- [ ] Chat transcripts preserve complete user and assistant content
- [ ] Session metadata tracks summary, counters, and last-message timing
- [ ] Long-term memory supports user-global and scoped records without inventing a new project model
- [ ] Memory APIs support list, evidence, delete, and pin
- [ ] Context assembly uses summary -> recent messages -> memories -> RAG
- [ ] QA page uses B1 layout with compact workspace rail and button-driven drawers
- [ ] Backend and frontend verification pass with existing project toolchains
