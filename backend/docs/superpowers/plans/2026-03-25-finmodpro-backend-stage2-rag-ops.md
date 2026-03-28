# FinModPro Backend Stage 2 (Knowledgebase / RAG / LLM / Ops) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Django 认证 + RBAC 骨架上，完成金融文档知识库、向量检索、问答会话、风险/摘要任务、模型配置、评测与审计日志的最小可演示闭环。

**Architecture:** 后端继续按 MVC 思路推进，controller 只负责请求解析与响应，service 承担文档解析、切片、embedding、检索、prompt 组装、LLM 调用、评测与审计等主要逻辑。RAG 链路按“Document -> Chunk -> Embedding -> VectorIndex -> Retrieval -> Prompt -> Answer -> Evidence”落地，优先按 Milvus 真链路设计，同时保留可替换接口以适应本地/受限环境。

**Tech Stack:** Django 5, SQLite/MySQL, optional Redis, JWT, pymilvus or Milvus-compatible adapter, optional langchain/langchain-milvus, document parsers (PDF/DOCX/TXT), HTTP client

---

## 0. 调研结论（写入计划前先对齐）

### 0.1 当前仓库现状
- 已有 app：`authentication`、`rbac`、`systemcheck`
- 已有 Django 注册：`config/settings.py`
- 已有路由入口：`config/urls.py`
- 当前依赖极简：`requirements.txt` 只有 `Django>=5,<6`
- 说明：Stage 2 不能直接把 LangChain / Milvus 深度耦合进 controller，必须先定义 service 接口与 fallback 实现。

### 0.2 技术选型建议
1. **Milvus 作为目标向量库协议**
   - collection 维度、主键、metadata filter、top-k 检索都按 Milvus 思维建模。
   - 如果环境没装 Milvus，先做 `VectorStoreService` 抽象，并提供 `InMemoryVectorStoreService` 测试/本地 fallback。
2. **LangChain 不是必须依赖，但可以作为集成层**
   - 不建议一上来把业务逻辑写死在 LangChain chain 里。
   - 推荐：业务 service 自己定义 DTO；LangChain 只作为 embedding / vectorstore / prompt 工具的可选适配层。
3. **rerank 先留标准接口，再决定是否真接模型**
   - 先实现 `RerankService.rank(query, candidates)`，默认可返回原排序；如果后续接 rerank 模型，只替换 service。
4. **任务闭环优先级**
   - 优先做“可上传 -> 可解析 -> 可切片 -> 可入向量 -> 可检索 -> 可问答 -> 可留证据”。
   - 评测和审计在此基础上再补齐。

### 0.3 推荐依赖（分层引入）
- 第一批必须：
  - `requests` 或 `httpx`
  - PDF/DOCX 解析库（如 `pypdf`、`python-docx`）
- 第二批按需：
  - `pymilvus`
  - `langchain`
  - `langchain-milvus`
- 当前阶段不强制：
  - `celery`（若 ingest 先同步做即可）

---

## 1. 文件结构与责任划分

### 1.1 修改的项目级文件
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Modify: `requirements.txt`
- Modify: `README.md`

### 1.2 knowledgebase app
- Create: `knowledgebase/apps.py`
- Create: `knowledgebase/models.py`
- Create: `knowledgebase/urls.py`
- Create: `knowledgebase/controllers/document_controller.py`
- Create: `knowledgebase/controllers/ingest_controller.py`
- Create: `knowledgebase/services/document_service.py`
- Create: `knowledgebase/services/parser_service.py`
- Create: `knowledgebase/services/chunk_service.py`
- Create: `knowledgebase/tests.py`
- Create: `knowledgebase/migrations/0001_initial.py`

### 1.3 rag app
- Create: `rag/apps.py`
- Create: `rag/models.py`
- Create: `rag/urls.py`
- Create: `rag/controllers/retrieval_controller.py`
- Create: `rag/services/embedding_service.py`
- Create: `rag/services/vector_store_service.py`
- Create: `rag/services/retrieval_service.py`
- Create: `rag/services/rerank_service.py`
- Create: `rag/tests.py`
- Create: `rag/migrations/0001_initial.py`

### 1.4 llm app
- Create: `llm/apps.py`
- Create: `llm/models.py`
- Create: `llm/urls.py`
- Create: `llm/controllers/chat_controller.py`
- Create: `llm/controllers/task_controller.py`
- Create: `llm/services/gateway_service.py`
- Create: `llm/services/prompt_service.py`
- Create: `llm/services/chat_service.py`
- Create: `llm/services/task_service.py`
- Create: `llm/tests.py`
- Create: `llm/migrations/0001_initial.py`

### 1.5 ops app
- Create: `ops/apps.py`
- Create: `ops/models.py`
- Create: `ops/urls.py`
- Create: `ops/controllers/model_config_controller.py`
- Create: `ops/controllers/evaluation_controller.py`
- Create: `ops/controllers/audit_log_controller.py`
- Create: `ops/services/model_config_service.py`
- Create: `ops/services/evaluation_service.py`
- Create: `ops/services/audit_log_service.py`
- Create: `ops/tests.py`
- Create: `ops/migrations/0001_initial.py`

### 1.6 可选公共模块（推荐，避免重复）
- Create: `common/http.py`
- Create: `common/json.py`
- Create: `common/files.py`
- Create: `common/exceptions.py`
- Create: `common/testing.py`

---

## 2. 领域模型建议

### 2.1 knowledgebase.models
- `KnowledgeDocument`
  - `title`
  - `doc_type`
  - `source_date`
  - `status` (`uploaded` / `parsed` / `chunked` / `indexed` / `failed`)
  - `storage_path`
  - `uploaded_by` -> `User`
  - `metadata_json`
  - timestamps
- `DocumentChunk`
  - `document` -> `KnowledgeDocument`
  - `chunk_index`
  - `content`
  - `page_label`
  - `token_count`
  - `metadata_json`
  - timestamps

### 2.2 rag.models
- `ChunkEmbedding`
  - `chunk` -> `DocumentChunk`
  - `embedding_model`
  - `vector_dim`
  - `vector_ref`
  - `metadata_json`
  - timestamps
- `RetrievalLog`
  - `query`
  - `top_k`
  - `filters_json`
  - `result_count`
  - `metadata_json`
  - timestamps

### 2.3 llm.models
- `ChatSession`
  - `user` -> `User`
  - `title`
  - `last_question`
  - timestamps
- `ChatMessage`
  - `session` -> `ChatSession`
  - `role` (`user` / `assistant` / `system`)
  - `content`
  - `model_name`
  - `metadata_json`
  - timestamps
- `ChatEvidence`
  - `message` -> `ChatMessage`
  - `document_title`
  - `doc_type`
  - `source_date`
  - `page_label`
  - `snippet`
  - `score`
  - `metadata_json`
- `LlmTaskCall`
  - `task_type` (`risk_extract` / `summary`)
  - `input_text`
  - `result_json`
  - `model_name`
  - `created_by` -> `User`
  - timestamps

### 2.4 ops.models
- `ModelConfig`
  - `name`
  - `provider`
  - `model_type` (`chat` / `embedding` / `rerank`)
  - `base_url`
  - `endpoint`
  - `api_key_ref`（只存引用，不存明文）
  - `enabled`
  - `is_default`
  - `config_json`
  - timestamps
- `EvaluationRun`
  - `strategy` (`base` / `base_rag` / `lora_rag`)
  - `dataset_name`
  - `status`
  - `metric_summary`
  - `sample_count`
  - timestamps
- `EvaluationSampleResult`
  - `run` -> `EvaluationRun`
  - `question`
  - `answer`
  - `reference_answer`
  - `score_json`
- `AuditLog`
  - `actor`
  - `action`
  - `target_type`
  - `target_id`
  - `detail_json`
  - `created_at`

---

## 3. 任务拆分（严格 TDD）

### Task 1: 扩展 RBAC 权限，为新模块打底

**Files:**
- Modify: `rbac/services/rbac_service.py`
- Modify: `rbac/tests.py`
- Modify: `authentication/tests.py`（如 `/api/auth/me` 权限摘要需扩展）

- [ ] Step 1: 写失败测试，定义知识库/问答/运维相关权限码
- [ ] Step 2: 跑 `python manage.py test rbac -v 2`，确认失败
- [ ] Step 3: 最小实现权限种子与角色映射
- [ ] Step 4: 再跑测试确认通过
- [ ] Step 5: 提交

**新增权限建议：**
- `upload_document`
- `view_document`
- `trigger_ingest`
- `ask_financial_qa`
- `view_chat_session`
- `manage_model_config`
- `view_evaluation`
- `run_evaluation`
- `view_audit_log`

**Commit:**
```bash
git add rbac authentication
git commit -m "feat: extend rbac permissions for financial platform"
```

### Task 2: 搭 knowledgebase 文档上传与列表最小闭环

**Files:**
- Create: `knowledgebase/*`
- Modify: `config/settings.py`
- Modify: `config/urls.py`

- [ ] Step 1: 写失败测试，覆盖文档上传、列表、详情、权限边界
- [ ] Step 2: 跑 `python manage.py test knowledgebase -v 2`，确认失败
- [ ] Step 3: 建 `KnowledgeDocument` 模型与 migration
- [ ] Step 4: 实现 `document_service.py` 与上传 controller
- [ ] Step 5: 接入 URL 和 Django app 注册
- [ ] Step 6: 重新跑 `python manage.py test knowledgebase -v 2`
- [ ] Step 7: 提交

**接口至少：**
- `POST /api/knowledgebase/documents`
- `GET /api/knowledgebase/documents`
- `GET /api/knowledgebase/documents/:id`

**Commit:**
```bash
git add knowledgebase config
git commit -m "feat: add knowledgebase upload workflow"
```

### Task 3: 实现解析与切片 ingest 主链路

**Files:**
- Modify: `knowledgebase/tests.py`
- Modify/Create: `knowledgebase/services/parser_service.py`
- Modify/Create: `knowledgebase/services/chunk_service.py`
- Create/Modify: `knowledgebase/controllers/ingest_controller.py`
- Modify: `knowledgebase/models.py`

- [ ] Step 1: 写失败测试，覆盖 ingest 触发后文档状态变化与 chunk 落库
- [ ] Step 2: 跑单测确认失败
- [ ] Step 3: 先支持 TXT/PDF 最小解析，DOCX 可按依赖情况跟进
- [ ] Step 4: 实现固定大小 + overlap 的切片 service
- [ ] Step 5: 文档状态从 `uploaded -> parsed -> chunked`
- [ ] Step 6: 再跑测试确认通过
- [ ] Step 7: 提交

**接口至少：**
- `POST /api/knowledgebase/documents/:id/ingest`

**Commit:**
```bash
git add knowledgebase
git commit -m "feat: add knowledgebase parsing and chunk ingestion"
```

### Task 4: 实现 embedding / vector store / retrieval 接口抽象

**Files:**
- Create: `rag/*`
- Modify: `config/settings.py`
- Modify: `config/urls.py`

- [ ] Step 1: 写失败测试，覆盖 chunk -> embedding -> vector upsert -> query recall
- [ ] Step 2: 跑 `python manage.py test rag -v 2`，确认失败
- [ ] Step 3: 定义 `EmbeddingService` 接口（输入 chunks，输出 embedding DTO）
- [ ] Step 4: 定义 `VectorStoreService` 接口（upsert/search/delete）
- [ ] Step 5: 先实现 `InMemoryVectorStoreService` 供测试使用
- [ ] Step 6: 预留 `MilvusVectorStoreService`，字段与 metadata filter 按 Milvus 设计
- [ ] Step 7: 实现 `RetrievalService`，支持 query、top_k、基础 metadata 过滤
- [ ] Step 8: 再跑测试确认通过
- [ ] Step 9: 提交

**接口至少：**
- `POST /api/rag/retrieval/query`

**过滤字段至少支持：**
- `doc_type`
- `document_id`
- `source_date_from`
- `source_date_to`

**Commit:**
```bash
git add rag config
 git commit -m "feat: add rag retrieval workflow"
```

### Task 5: 预留/实现 rerank 能力

**Files:**
- Modify: `rag/services/rerank_service.py`
- Modify: `rag/services/retrieval_service.py`
- Modify: `rag/tests.py`

- [ ] Step 1: 写失败测试，定义 rerank 接口输入输出结构
- [ ] Step 2: 跑测试确认失败
- [ ] Step 3: 实现 no-op rerank 或基于简单分数重排的最小实现
- [ ] Step 4: 在 retrieval service 中接入可选 rerank
- [ ] Step 5: 再跑测试确认通过
- [ ] Step 6: 提交

**返回 DTO 至少：**
- `chunk_id`
- `score`
- `rerank_score`
- `document_title`
- `snippet`

**Commit:**
```bash
git add rag
git commit -m "feat: reserve rerank service for retrieval pipeline"
```

### Task 6: 创建 llm app 与统一 gateway / prompt 层

**Files:**
- Create: `llm/*`
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Modify: `requirements.txt`

- [ ] Step 1: 写失败测试，定义 gateway 调用、prompt 组装与错误返回
- [ ] Step 2: 跑 `python manage.py test llm -v 2`，确认失败
- [ ] Step 3: 建 `GatewayService`，统一 chat/embedding/rerank 可配置入口
- [ ] Step 4: 建 `PromptService`，封装 chat/risk_extract/summary prompt 模板
- [ ] Step 5: 再跑测试确认通过
- [ ] Step 6: 提交

**Commit:**
```bash
git add llm config requirements.txt
git commit -m "feat: add llm gateway and prompt services"
```

### Task 7: 实现问答会话与 RAG 主链路

**Files:**
- Modify: `llm/tests.py`
- Modify/Create: `llm/services/chat_service.py`
- Modify/Create: `llm/controllers/chat_controller.py`
- Modify: `llm/models.py`
- Modify: `rag/services/retrieval_service.py`
- Modify: `ops/services/audit_log_service.py`（如已就绪）

- [ ] Step 1: 写失败测试，覆盖创建会话、会话列表、会话详情、发消息问答
- [ ] Step 2: 跑单测确认失败
- [ ] Step 3: 建 `ChatSession / ChatMessage / ChatEvidence` 模型与 migration
- [ ] Step 4: 实现 chat service：保存用户问题 -> 检索 chunks -> 组 prompt -> 调 gateway -> 保存 assistant 回复 -> 保存 evidence
- [ ] Step 5: 加普通用户仅可访问自己会话的测试与实现
- [ ] Step 6: 再跑测试确认通过
- [ ] Step 7: 提交

**接口必须：**
- `POST /api/chat/sessions`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/:id`
- `POST /api/chat/sessions/:id/messages`

**消息返回结构必须包含：**
- `answer`
- `model_name`
- `citations[]`

**citation 字段至少：**
- `document_title`
- `doc_type`
- `source_date`
- `page_label`
- `snippet`

**Commit:**
```bash
git add llm rag
git commit -m "feat: add llm chat endpoints with rag citations"
```

### Task 8: 实现风险抽取与摘要任务接口

**Files:**
- Modify: `llm/controllers/task_controller.py`
- Modify: `llm/services/task_service.py`
- Modify: `llm/models.py`
- Modify: `llm/tests.py`

- [ ] Step 1: 写失败测试，覆盖风险抽取与摘要的结构化返回
- [ ] Step 2: 跑测试确认失败
- [ ] Step 3: 实现 task service，走统一 gateway / prompt service
- [ ] Step 4: 落 `LlmTaskCall` 历史记录
- [ ] Step 5: 再跑测试确认通过
- [ ] Step 6: 提交

**接口：**
- `POST /api/llm/tasks/risk-extract`
- `POST /api/llm/tasks/summary`

**Commit:**
```bash
git add llm
git commit -m "feat: add llm task endpoints for risk extraction and summary"
```

### Task 9: 创建 ops app 与模型配置管理

**Files:**
- Create: `ops/*`
- Modify: `config/settings.py`
- Modify: `config/urls.py`

- [ ] Step 1: 写失败测试，覆盖模型配置列表、新增、编辑、默认项切换
- [ ] Step 2: 跑 `python manage.py test ops -v 2`，确认失败
- [ ] Step 3: 建 `ModelConfig` 模型与 service
- [ ] Step 4: 实现 controller 与权限校验
- [ ] Step 5: 加“同类型仅一个 default”约束
- [ ] Step 6: 再跑测试确认通过
- [ ] Step 7: 提交

**接口至少：**
- `GET /api/ops/model-configs`
- `POST /api/ops/model-configs`
- `PUT /api/ops/model-configs/:id`

**Commit:**
```bash
git add ops config
git commit -m "feat: add ops model configuration management"
```

### Task 10: 实现评测最小闭环

**Files:**
- Modify: `ops/models.py`
- Modify: `ops/services/evaluation_service.py`
- Modify: `ops/controllers/evaluation_controller.py`
- Modify: `ops/tests.py`

- [ ] Step 1: 写失败测试，覆盖发起评测、记录样本结果、查看摘要
- [ ] Step 2: 跑测试确认失败
- [ ] Step 3: 实现 `EvaluationRun / EvaluationSampleResult`
- [ ] Step 4: 支持 `base / base_rag / lora_rag` 三种 strategy
- [ ] Step 5: 先用同步执行 + 简单打分结构，保证闭环真实可跑
- [ ] Step 6: 再跑测试确认通过
- [ ] Step 7: 提交

**接口建议至少：**
- `POST /api/ops/evaluations`
- `GET /api/ops/evaluations`
- `GET /api/ops/evaluations/:id`

**Commit:**
```bash
git add ops
git commit -m "feat: add ops evaluation workflow"
```

### Task 11: 实现审计日志

**Files:**
- Modify: `ops/models.py`
- Modify: `ops/services/audit_log_service.py`
- Modify: `ops/controllers/audit_log_controller.py`
- Modify: `ops/tests.py`
- Modify: `knowledgebase/services/document_service.py`
- Modify: `llm/services/chat_service.py`
- Modify: `ops/services/model_config_service.py`
- Modify: `ops/services/evaluation_service.py`

- [ ] Step 1: 写失败测试，覆盖审计日志查询与关键业务动作落日志
- [ ] Step 2: 跑测试确认失败
- [ ] Step 3: 实现 `AuditLog` 模型与 service
- [ ] Step 4: 在文档上传、ingest 触发、问答调用、模型配置变更、评测发起处埋点
- [ ] Step 5: 再跑测试确认通过
- [ ] Step 6: 提交

**接口：**
- `GET /api/ops/audit-logs`

**Commit:**
```bash
git add ops knowledgebase llm
git commit -m "feat: add ops audit logging"
```

### Task 12: 最终联调验证与文档更新

**Files:**
- Modify: `README.md`
- Modify: `requirements.txt`
- Modify: `.env.example`（如存在）

- [ ] Step 1: 更新 README，补 app 说明、依赖安装、Milvus/LLM 配置、接口概览
- [ ] Step 2: 跑完整测试：
  ```bash
  python manage.py test authentication rbac knowledgebase llm rag ops -v 2
  ```
- [ ] Step 3: 跑配置检查：
  ```bash
  python manage.py check
  ```
- [ ] Step 4: 如新增 migration，执行并确认：
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  ```
- [ ] Step 5: 提交

**Commit:**
```bash
git add README.md requirements.txt .env.example config knowledgebase rag llm ops
git commit -m "feat: complete backend stage2 rag and ops modules"
```

---

## 4. LangChain / RAG 使用原则（给 Codex 的明确约束）

1. **不要把 LangChain 直接当业务边界**
   - service 层自己的 DTO / 方法签名优先。
   - LangChain 只作为 adapter，不要让 controller 依赖 `chain.invoke()` 风格实现细节。
2. **Milvus 先按真链路设计，运行环境不满足时再 fallback**
   - 测试用 in-memory stub。
   - 生产/真实部署留 `MilvusVectorStoreService`。
3. **RAG 主链路不要做成黑箱**
   - 明确拆出：query normalize、retrieval、optional rerank、context compose、prompt build、llm call、evidence persist。
4. **所有关键链路都可单测**
   - parser、chunker、retriever、chat service、task service、evaluation service 都必须可 mock 测。

---

## 5. 给 Codex 的实施顺序（建议保持）

1. RBAC 扩权
2. knowledgebase 上传/解析/切片
3. rag embedding/retrieval/rerank
4. llm chat/task
5. ops model config/evaluation/audit
6. README / tests / final verification

---

## 6. 验收映射

完成后应满足：
1. admin 可上传金融文档
2. 文档可解析并切片入库
3. chunk 可被问答检索到
4. 用户提问后返回答案和来源引用
5. 历史会话可查看
6. 风险抽取/摘要可调用
7. admin 可查看模型配置、评测结果、审计日志

---

## 7. 实施备注

- 由于当前仓库还没有 `knowledgebase` / `rag` / `llm` / `ops` app，建议由 Codex 一次性接完整后端 Stage 2，但必须按上面任务顺序与提交粒度推进。
- 如果主人希望进一步降低风险，我建议拆成两条 ACP 消息：
  - 第一条：RBAC + knowledgebase + rag
  - 第二条：llm + ops + final verification
- 这样可以先把“文档到检索”的底座跑通，再接问答与运维面板，返工会更少。
