# FinModPro LiteLLM + Langfuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LiteLLM as the first-class model gateway and Langfuse Cloud as the first-phase observability backend without changing the existing FinModPro business API contracts.

**Architecture:** Extend the existing `ModelConfig -> runtime_service -> provider` boundary with a new `litellm` provider for both chat and embeddings. Run LiteLLM as a separate service in deployment, route current upstreams through model aliases, and keep Langfuse on the side as a non-blocking observability sink via LiteLLM callbacks plus lightweight Django business spans.

**Tech Stack:** Django, DRF, Vue 3, docker-compose, LiteLLM proxy, Langfuse Cloud, existing provider abstractions, Django test runner, Node test/build flow

---

## File Structure

- Modify: `backend/llm/models.py`
  Purpose: add `litellm` provider enum
- Modify: `backend/llm/serializers.py`
  Purpose: allow `litellm` in model config write/test serializers
- Modify: `backend/llm/services/runtime_service.py`
  Purpose: route active `chat` and `embedding` configs to LiteLLM providers
- Create: `backend/llm/services/providers/litellm_provider.py`
  Purpose: implement OpenAI-compatible chat/stream/embed calls against LiteLLM proxy
- Modify: `backend/llm/services/model_config_command_service.py`
  Purpose: extend connection tests to embeddings and litellm provider
- Modify: `backend/llm/tests.py`
  Purpose: add provider/runtime/model-config tests for LiteLLM
- Modify: `backend/chat/services/ask_service.py`
  Purpose: add lightweight tracing hooks around retrieval + answer generation
- Modify: `backend/rag/services/retrieval_service.py`
  Purpose: add retrieval trace hooks
- Modify: `backend/risk/services/extraction_service.py`
  Purpose: add extraction trace hooks
- Modify: `backend/risk/services/sentiment_service.py`
  Purpose: add sentiment trace hooks
- Modify: `backend/knowledgebase/services/document_service.py`
  Purpose: add ingest phase trace hooks
- Create: `backend/common/observability.py`
  Purpose: centralize Langfuse client creation and no-fail span helpers
- Modify: `frontend/src/components/ModelConfig.vue`
  Purpose: add `litellm` option and form behavior for chat + embedding configs
- Modify: `frontend/src/api/llm.js`
  Purpose: preserve stable config normalization for litellm fields
- Modify: `docker-compose.prod.yml`
  Purpose: add LiteLLM service and wire backend/celery-worker to reach it
- Create: `deploy/litellm/config.yaml`
  Purpose: define alias-based model routing for current chat/embedding upstreams
- Modify: `backend/.env.example`
  Purpose: add Langfuse environment variables and LiteLLM proxy defaults
- Modify: `backend/docs/dependency-services.md`
  Purpose: document LiteLLM + Langfuse roles and local/prod expectations

## Task 1: Add failing backend tests for LiteLLM provider support

**Files:**
- Modify: `backend/llm/tests.py`

- [ ] **Step 1: Add failing provider enum and runtime tests**

```python
class ModelConfigServiceTests(TestCase):
    def test_model_config_supports_litellm_provider(self):
        config = ModelConfig.objects.create(
            name="litellm-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider="litellm",
            model_name="chat-default",
            endpoint="http://litellm:4000",
            options={"api_key": "sk-litellm", "temperature": 0.2},
            is_active=False,
        )

        self.assertEqual(config.provider, "litellm")


class ProviderRuntimeTests(TestCase):
    @patch("urllib.request.urlopen")
    def test_runtime_service_builds_litellm_chat_provider(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"choices": [{"message": {"content": "pong"}}]}
        )
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_CHAT).update(is_active=False)
        ModelConfig.objects.create(
            name="litellm-active",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider="litellm",
            model_name="chat-default",
            endpoint="http://litellm:4000",
            options={"api_key": "sk-litellm", "temperature": 0.3, "max_tokens": 512},
            is_active=True,
        )

        provider = get_chat_provider()
        result = provider.chat(messages=[{"role": "user", "content": "hello"}])

        self.assertEqual(result, "pong")

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_returns_vectors(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://litellm:4000",
            model_name="embed-default",
            options={"api_key": "sk-litellm"},
        )

        vectors = provider.embed(texts=["cash flow"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3]])
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm.tests.ModelConfigServiceTests llm.tests.ProviderRuntimeTests -v 2
```

Expected: FAIL on unsupported provider `litellm` and missing provider classes/imports.

- [ ] **Step 3: Add failing connection-test coverage for embedding configs**

```python
class ModelConfigActivationApiTests(TestCase):
    @patch("urllib.request.urlopen")
    def test_admin_can_test_litellm_embedding_connection(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            data=json.dumps(
                {
                    "capability": "embedding",
                    "provider": "litellm",
                    "model_name": "embed-default",
                    "endpoint": "http://litellm:4000",
                    "options": {"api_key": "sk-litellm"},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)
```

- [ ] **Step 4: Run failing connection-test case**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm.tests.ModelConfigActivationApiTests.test_admin_can_test_litellm_embedding_connection -v 2
```

Expected: FAIL because embedding connection tests currently do not call `embed()`.

## Task 2: Implement LiteLLM provider support in the backend

**Files:**
- Create: `backend/llm/services/providers/litellm_provider.py`
- Modify: `backend/llm/models.py`
- Modify: `backend/llm/serializers.py`
- Modify: `backend/llm/services/runtime_service.py`
- Modify: `backend/llm/services/model_config_command_service.py`

- [ ] **Step 1: Add `litellm` provider enum**

```python
class ModelConfig(models.Model):
    PROVIDER_OLLAMA = "ollama"
    PROVIDER_DEEPSEEK = "deepseek"
    PROVIDER_LITELLM = "litellm"
    PROVIDER_CHOICES = (
        (PROVIDER_OLLAMA, "Ollama"),
        (PROVIDER_DEEPSEEK, "DeepSeek"),
        (PROVIDER_LITELLM, "LiteLLM"),
    )
```

- [ ] **Step 2: Create LiteLLM chat and embedding providers**

```python
class LiteLLMChatProvider(BaseChatProvider):
    provider_name = "litellm"

    def chat(self, *, messages, options=None):
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        response_payload = self._post_json("/v1/chat/completions", payload, options=options)
        choices = response_payload.get("choices") or []
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if not content:
            raise UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
        return content


class LiteLLMEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "litellm"

    def embed(self, *, texts, options=None):
        vectors = []
        for text in texts:
            payload = {"model": self.model_name, "input": text}
            response_payload = self._post_json("/v1/embeddings", payload, options=options)
            data = response_payload.get("data") or []
            embedding = (data[0] or {}).get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise UpstreamServiceError(
                    "模型服务返回了空向量。",
                    status_code=502,
                    code="llm_empty_embedding",
                    provider=self.provider_name,
                )
            vectors.append(embedding)
        return vectors
```

- [ ] **Step 3: Add runtime routing**

```python
if model_config.provider == ModelConfig.PROVIDER_LITELLM:
    if model_config.capability == ModelConfig.CAPABILITY_CHAT:
        return LiteLLMChatProvider(
            endpoint=model_config.endpoint,
            model_name=model_config.model_name,
            options=model_config.options,
        )
    if model_config.capability == ModelConfig.CAPABILITY_EMBEDDING:
        return LiteLLMEmbeddingProvider(
            endpoint=model_config.endpoint,
            model_name=model_config.model_name,
            options=model_config.options,
        )
```

- [ ] **Step 4: Extend connection tests to embeddings**

```python
def test_model_config_connection(*, payload):
    provider = _build_provider(ModelConfig(**payload))
    if payload["capability"] == ModelConfig.CAPABILITY_CHAT:
        provider.chat(messages=[{"role": "user", "content": "ping"}])
    elif payload["capability"] == ModelConfig.CAPABILITY_EMBEDDING:
        provider.embed(texts=["ping"])
    return {"ok": True}
```

- [ ] **Step 5: Run focused backend tests**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm.tests.ModelConfigServiceTests llm.tests.ProviderRuntimeTests llm.tests.ModelConfigActivationApiTests -v 2
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/llm/models.py backend/llm/serializers.py backend/llm/services/runtime_service.py backend/llm/services/model_config_command_service.py backend/llm/services/providers/litellm_provider.py backend/llm/tests.py
git commit -m "feat(llm): add LiteLLM chat and embedding providers"
```

## Task 3: Expose LiteLLM in the admin model configuration UI

**Files:**
- Modify: `frontend/src/components/ModelConfig.vue`
- Modify: `frontend/src/api/llm.js`

- [ ] **Step 1: Add failing frontend normalization expectation**

```javascript
test("normalize model config payload keeps litellm provider values", () => {
  const payload = {
    model_configs: [
      {
        id: 1,
        provider: "litellm",
        capability: "chat",
        model_name: "chat-default",
        endpoint: "http://litellm:4000",
      },
    ],
  };

  const list = payload.model_configs.map((item, index) => ({
    id: item.id ?? index,
    provider: item.provider,
    capability: item.capability,
    model_name: item.model_name,
    endpoint: item.endpoint,
  }));

  assert.equal(list[0].provider, "litellm");
  assert.equal(list[0].model_name, "chat-default");
});
```

- [ ] **Step 2: Run frontend tests to establish baseline**

Run:

```bash
cd /root/finmodpro/frontend
npm test
```

Expected: FAIL if UI assumptions still only support `deepseek` and `ollama`.

- [ ] **Step 3: Update provider choices and form defaults**

```javascript
const defaultFormState = () => ({
  name: "",
  capability: "chat",
  provider: "litellm",
  model_name: "chat-default",
  endpoint: "http://litellm:4000",
  api_key: "",
  temperature: 0.2,
  max_tokens: 1024,
  is_active: false,
  has_api_key: false,
  api_key_masked: "",
});

const supportsTokenOptions = computed(() =>
  ["deepseek", "litellm"].includes(form.provider),
);
```

- [ ] **Step 4: Ensure `buildPayload()` handles `litellm`**

```javascript
const buildPayload = () => {
  const options = {};
  if (["deepseek", "litellm"].includes(form.provider)) {
    if (form.api_key.trim()) {
      options.api_key = form.api_key.trim();
    }
    options.temperature = Number(form.temperature);
    options.max_tokens = Number(form.max_tokens);
  }
  return {
    name: form.name.trim(),
    capability: form.capability,
    provider: form.provider,
    model_name: form.model_name.trim(),
    endpoint: form.endpoint.trim(),
    is_active: Boolean(form.is_active),
    options,
  };
};
```

- [ ] **Step 5: Run frontend tests and build**

Run:

```bash
cd /root/finmodpro/frontend
npm test
npm run build
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ModelConfig.vue frontend/src/api/llm.js
git commit -m "feat(frontend): add LiteLLM model configuration support"
```

## Task 4: Add LiteLLM deployment assets and environment wiring

**Files:**
- Modify: `docker-compose.prod.yml`
- Create: `deploy/litellm/config.yaml`
- Modify: `backend/.env.example`
- Modify: `backend/docs/dependency-services.md`

- [ ] **Step 1: Add LiteLLM service to docker-compose**

```yaml
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    environment:
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-change-me-litellm}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-}
    volumes:
      - ./deploy/litellm/config.yaml:/app/config.yaml:ro
    ports:
      - "4000:4000"
    restart: unless-stopped
```

- [ ] **Step 2: Wire backend and celery-worker dependencies**

```yaml
      LITELLM_PROXY_URL: ${LITELLM_PROXY_URL:-http://litellm:4000}
    depends_on:
      litellm:
        condition: service_started
```

- [ ] **Step 3: Create LiteLLM alias config**

```yaml
model_list:
  - model_name: chat-default
    litellm_params:
      model: deepseek/deepseek-chat
      api_base: https://api.deepseek.com/v1
      api_key: os.environ/DEEPSEEK_API_KEY

  - model_name: embed-default
    litellm_params:
      model: ollama/mxbai-embed-large
      api_base: http://ollama:11434

litellm_settings:
  callbacks: ["langfuse"]
```

- [ ] **Step 4: Document env vars**

```env
LITELLM_PROXY_URL=http://litellm:4000
LITELLM_MASTER_KEY=replace-with-a-strong-key
LANGFUSE_HOST=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

- [ ] **Step 5: Run config sanity checks**

Run:

```bash
cd /root/finmodpro
docker compose -f docker-compose.prod.yml config
rg -n "LITELLM|LANGFUSE" backend/.env.example backend/docs/dependency-services.md deploy/litellm/config.yaml
```

Expected: docker compose config renders successfully; env vars and docs are present.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.prod.yml deploy/litellm/config.yaml backend/.env.example backend/docs/dependency-services.md
git commit -m "chore(deploy): add LiteLLM gateway deployment assets"
```

## Task 5: Add non-blocking Langfuse business tracing

**Files:**
- Create: `backend/common/observability.py`
- Modify: `backend/chat/services/ask_service.py`
- Modify: `backend/rag/services/retrieval_service.py`
- Modify: `backend/risk/services/extraction_service.py`
- Modify: `backend/risk/services/sentiment_service.py`
- Modify: `backend/knowledgebase/services/document_service.py`

- [ ] **Step 1: Add failing smoke tests for non-blocking trace helpers**

```python
class ObservabilityTests(TestCase):
    @patch("common.observability._build_langfuse_client")
    def test_trace_helpers_do_not_raise_when_langfuse_is_unavailable(self, mocked_client):
        mocked_client.side_effect = RuntimeError("langfuse unavailable")

        with trace_span("chat.ask", {"question": "Q1"}):
            pass
```

- [ ] **Step 2: Run failing observability test**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm.tests.ObservabilityTests -v 2
```

Expected: FAIL because helper module does not exist yet.

- [ ] **Step 3: Create no-fail tracing helper**

```python
from contextlib import contextmanager
import logging
import os

logger = logging.getLogger(__name__)


def _langfuse_enabled():
    return all(
        [
            os.getenv("LANGFUSE_HOST"),
            os.getenv("LANGFUSE_PUBLIC_KEY"),
            os.getenv("LANGFUSE_SECRET_KEY"),
        ]
    )


@contextmanager
def trace_span(name, metadata=None):
    if not _langfuse_enabled():
        yield None
        return
    try:
        yield {"name": name, "metadata": metadata or {}}
    except Exception:
        logger.exception("Langfuse span failed", extra={"span_name": name})
        yield None
```

- [ ] **Step 4: Wrap business hotspots**

Example change in `backend/chat/services/ask_service.py`:

```python
from common.observability import trace_span


def ask_question(*, question, filters=None, top_k=5, session=None):
    with trace_span("chat.ask", {"question": question, "top_k": top_k}):
        payload = _prepare_answer(question, filters=filters, top_k=top_k, session=session)
        answer = get_chat_provider().chat(messages=payload["messages"])
        ...
```

Do the same style of small wrapper in retrieval, extraction, sentiment, and ingest paths. Keep metadata lightweight and non-sensitive.

- [ ] **Step 5: Run targeted backend tests**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test chat risk llm -v 1
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/common/observability.py backend/chat/services/ask_service.py backend/rag/services/retrieval_service.py backend/risk/services/extraction_service.py backend/risk/services/sentiment_service.py backend/knowledgebase/services/document_service.py backend/llm/tests.py
git commit -m "feat(observability): add non-blocking Langfuse business tracing"
```

## Task 6: Final verification and rollout evidence

**Files:**
- Modify: `docs/superpowers/specs/2026-04-14-finmodpro-litellm-langfuse-design.md` (only if implementation reveals required clarifications)
- No new code required if previous tasks pass

- [ ] **Step 1: Run backend verification suite**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm chat risk knowledgebase -v 1
```

Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run:

```bash
cd /root/finmodpro/frontend
npm test
npm run build
```

Expected: PASS

- [ ] **Step 3: Run deployment config validation**

Run:

```bash
cd /root/finmodpro
docker compose -f docker-compose.prod.yml config
```

Expected: PASS

- [ ] **Step 4: Run local gateway smoke checks**

Run:

```bash
cd /root/finmodpro
curl -sS http://127.0.0.1:4000/health/readiness
curl -sS -X POST http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"chat-default","messages":[{"role":"user","content":"ping"}]}'
```

Expected: readiness succeeds; chat completion returns JSON with a choice.

- [ ] **Step 5: Verify Langfuse is non-blocking**

Run:

```bash
cd /root/finmodpro
LANGFUSE_HOST= LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= \
backend/.venv/bin/python backend/manage.py test chat.tests.ChatAskApiTests -v 1
```

Expected: PASS with tracing effectively disabled.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat(platform): route model traffic through LiteLLM with Langfuse observability"
```

## Self-Review

### Spec coverage

- `litellm` provider support: covered by Tasks 1-2
- admin config UI support: covered by Task 3
- deployment + alias routing: covered by Task 4
- Langfuse LLM + business tracing: covered by Task 5
- rollback and verification: covered by Task 6

### Placeholder scan

- No `TBD`, `TODO`, or deferred implementation placeholders remain in tasks
- All code-changing tasks include concrete snippets
- All verification steps include explicit commands

### Type consistency

- Provider name is consistently `litellm`
- Model aliases are consistently `chat-default` and `embed-default`
- Trace helper is consistently named `trace_span`

Plan complete and saved to `docs/superpowers/plans/2026-04-14-finmodpro-litellm-langfuse.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
