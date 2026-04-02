# FinModPro LangChain / DeepSeek 接入与下一步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不打断现有 MVP 功能的前提下，为 FinModPro 补齐设计文档到实现之间的关键缺口：引入 LangChain 作为可替换的 RAG / Prompt / Structured Output 适配层，新增 DeepSeek API 占位接入，并按“模型抽象 → 问答闭环 → 多知识库 → 风险抽取 → 风险报告 → 评测/运维”顺序推进下一阶段开发。

**Architecture:** 现有业务边界继续保留在 Django service 层，不让 LangChain 直接侵入 controller、serializer 或数据库模型。LangChain 仅作为 adapter 层，用于 chat model、structured output、retriever 封装；模型提供方短期由 DeepSeek API 占位替代远程模型能力，待主人提供 API Key 后再完成真实联调。

**Tech Stack:** Django, DRF, Vue 3, MySQL, Redis, Celery, Milvus, Ollama, DeepSeek API (placeholder), LangChain Python

---

## 0. 当前判断（基于 2026-04-02 仓库状态）

### 0.1 LangChain 当前是否已接入

| 项 | 结论 |
|---|---|
| 仓库是否已把 LangChain 用进主实现 | **没有** |
| 是否只在历史计划文档中提到 | **是** |
| 当前生产代码的主链路 | 自研 provider / retrieval / prompt / vector service |
| 当前模型 provider | **仅 Ollama** |
| 当前检索实现 | 自研混合检索 + 内存 `_VECTOR_STORE` + Milvus 写入 |

### 0.2 Context7 查询到的 LangChain 官方最新用法要点

| 主题 | 官方要点 | 对 FinModPro 的落地建议 |
|---|---|---|
| Chat 模型调用 | `init_chat_model(...)` + `model.invoke(messages)` | 封装在 `langchain_chat_provider.py`，不要让 controller 直接调用 |
| Structured output | `with_structured_output(PydanticModel)` | 用于风险抽取 JSON 输出，替换当前手工 JSON 解析 |
| RAG / Retriever | vector store `similarity_search(...)` + 两阶段 RAG | 保持 2-step RAG，不上复杂 agent |
| 文档定位 | knowledge-base / rag 教程强调 retrieval 与 generation 解耦 | 保持现有 service 边界，LangChain 只做 adapter |

### 0.3 本轮范围控制（非目标）

| 非目标 | 说明 |
|---|---|
| 不做真实 DeepSeek 联调 | 当前没有 API Key，只完成占位接入与错误处理 |
| 不推翻现有 Ollama 默认链路 | 未显式切换前，默认行为保持现状 |
| 不引入复杂 Agent 编排 | 仍坚持设计文档中的 2-step RAG 主线 |
| 不做大规模前端重构 | 只补必要页面和接口闭环 |
| 不做多模型自动路由 | 第一版只做显式 provider / config 切换 |

---

## 1. 设计对齐策略

### 1.1 API 收口策略

| 领域 | 当前现状 | 目标收口 |
|---|---|---|
| 问答 | `POST /api/chat/ask` 为主 | 保留兼容，但逐步收口到 `session/message` 风格接口 |
| 会话 | 已有 `POST /api/chat/sessions` 和 `GET /api/chat/sessions/{id}` | 补齐 `POST /api/chat/sessions/{id}/messages` 语义 |
| 知识库 | 目前是隐式单知识库 + documents | 增加显式 `KnowledgeBase` 模型与归属关系 |
| 抽取/报告 | 当前多数同步触发 | 收口为“同步发起 + Celery 异步执行 + 任务状态查询” |

### 1.2 兼容策略

| 规则 | 说明 |
|---|---|
| 旧 `ask` 接口短期保留 | 作为兼容入口，内部可转发到新消息服务 |
| 新接口落地后前端逐步迁移 | 先保证页面可用，再切换调用主路径 |
| 未迁移完成前不删除旧路由 | 避免前端和历史联调脚本失效 |

---

## 2. 文件结构与改动边界

### 2.1 后端新增/修改文件

| 类型 | 文件 | 责任 |
|---|---|---|
| Modify | `backend/requirements.txt` | 增加 LangChain / DeepSeek 所需依赖 |
| Create | `backend/llm/services/providers/deepseek_provider.py` | DeepSeek **chat provider 占位实现** |
| Create | `backend/llm/services/providers/langchain_chat_provider.py` | LangChain chat adapter |
| Create | `backend/llm/services/providers/langchain_structured_output.py` | LangChain structured output adapter |
| Optional Create | `backend/llm/services/providers/langchain_embedding_provider.py` | 仅在第一版确定要接入时实现；否则延后 |
| Modify | `backend/llm/services/runtime_service.py` | provider 路由：Ollama / DeepSeek / LangChain adapter |
| Modify | `backend/llm/models.py` | provider 枚举扩展，支持 `deepseek` |
| Modify | `backend/llm/serializers.py` | 模型配置校验扩展 |
| Modify | `backend/chat/services/ask_service.py` | 问答写入 `ChatMessage`，并支持 session 贯通 |
| Modify/Create | `backend/chat/controllers/*.py` | 增加 `session messages` 入口或兼容转发 |
| Modify | `backend/risk/services/extraction_service.py` | 引入 LangChain structured output 适配层 |
| Modify | `backend/risk/services/report_service.py` | 改为“聚合 + 模型总结 + 异常降级” |
| Modify | `backend/knowledgebase/models.py` | 新增 `KnowledgeBase` 模型与关系字段 |
| Modify | `backend/knowledgebase/services/document_service.py` | 文档归属知识库、状态与 reindex 流程 |
| Modify/Create | `backend/knowledgebase/tasks.py` | 入库 / 抽取 / 报告任务统一异步边界 |
| Create | `backend/systemcheck/services/ops_log_service.py` | 替换前端 mock logs 的真实来源 |

### 2.2 前端新增/修改文件

| 类型 | 文件 | 责任 |
|---|---|---|
| Modify | `frontend/src/api/chat.js` | 支持 `session message` 新协议 |
| Modify | `frontend/src/api/qa.js` | 兼容旧 ask 与新 session message 调用 |
| Modify | `frontend/src/api/llm.js` | 支持 DeepSeek provider 配置展示 |
| Modify | `frontend/src/api/ops.js` | 去掉 mock，切真实接口 |
| Modify | `frontend/src/components/FinancialQA.vue` | 会话绑定、历史回放、来源展示增强 |
| Modify | `frontend/src/components/KnowledgeBase.vue` | 多知识库 / 重建索引 / 任务状态 |
| Modify | `frontend/src/components/ModelConfig.vue` | 展示 DeepSeek 配置与占位状态 |
| Modify | `frontend/src/components/OpsDashboard.vue` | 使用真实日志接口 |
| Create | `frontend/src/components/TaskStatus.vue` | 入库/抽取/报告任务状态卡片 |
| Create | `frontend/src/components/SourcePanel.vue` | 问答引用来源详情面板 |

---

## 3. 依赖矩阵与执行顺序

| 任务 | 依赖 | 可否并行 | 备注 |
|---|---|---|---|
| Task 1A Provider 扩展 | 无 | 可先做 | DeepSeek chat 占位 |
| Task 1B LangChain adapter | 1A 部分依赖 | 可串行 | structured output 依赖它 |
| Task 2 问答闭环 | 1A 可选依赖 | 可并行但建议随后做 | 不依赖多知识库先落地 |
| Task 3 多知识库 | Task 2 最好先完成 | 建议串行 | 会影响 session / document 关系 |
| Task 4 风险抽取升级 | 1B 完成后 | 建议串行 | structured output 必须先可用 |
| Task 5 风险报告升级 | Task 4 后 | 串行 | 依赖较高质量风险事件 |
| Task 6 评测升级 | 1A/2/4/5 后 | 可后置 | 依赖稳定输入输出结构 |
| Task 7 运维去 mock | 与 4/5/6 弱依赖 | 可并行 | 优先级最低 |

---

## 4. 下一步计划总表（给主人看的版本）

| 阶段 | 优先级 | 模块 | 目标 | 核心输出 | 验收标准 |
|---|---:|---|---|---|---|
| Phase 1 | P0 | Provider 扩展 | 加入 DeepSeek chat 占位和可选 LangChain adapter | `deepseek` provider、runtime 路由、测试 | 能创建 `provider=deepseek` 配置；缺少 API Key 时返回可预期错误 |
| Phase 2 | P0 | 问答会话闭环 | 修复 session 创建了但消息没真正落库的问题 | `session_id` / message API / ChatMessage 持久化 | 问答后能在历史会话中看到真实消息 |
| Phase 3 | P1 | 多知识库模型 | 从“隐式单知识库”升级为真正知识库管理 | `KnowledgeBase` 模型、迁移脚本、前端列表/详情 | 可创建知识库、上传文档到指定知识库、历史文档完成回填 |
| Phase 4 | P1 | 风险抽取升级 | 用 LangChain structured output 稳定输出结构化结果 | schema、去重、异步任务状态 | 抽取走任务队列；同文档重复抽取不产生 deterministic 重复事件 |
| Phase 5 | P1 | 风险报告升级 | 从规则拼接升级为“统计 + 模型总结 + 降级策略” | company/time-range 双模式报告 | 可保存报告，包含统计、事件列表、summary、source metadata |
| Phase 6 | P2 | 评测升级 | 从 smoke 评测变成真实可记录评测 | dataset/version/model_config 评测 | 指标可解释、可重复运行、可展示 |
| Phase 7 | P2 | 运维大盘去 mock | 前端日志与统计改真实接口 | 真实日志 API、前端联调 | 页面不再依赖假日志数据 |

---

## 5. 任务拆解（可直接按表执行）

### Task 1A: 扩展 LLM provider，加入 DeepSeek chat 占位

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/llm/models.py`
- Modify: `backend/llm/services/runtime_service.py`
- Create: `backend/llm/services/providers/deepseek_provider.py`
- Test: `backend/llm/tests/test_runtime_service.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | 当前 runtime service 不支持 `deepseek` |
| 2 | 跑测试确认失败 | 期望 provider unsupported |
| 3 | 扩展 provider 枚举与校验 | 支持 `provider=deepseek` |
| 4 | 实现 DeepSeek chat provider 占位 | 只实现 chat；embedding 暂不做 |
| 5 | 增加缺失 key / endpoint 的错误处理 | 返回明确配置错误 |
| 6 | 跑测试确认通过 | 配置、实例化、错误路径都有覆盖 |
| 7 | 提交 | `feat(llm): add deepseek chat provider placeholder` |

**验收标准：**
- 能保存/读取 `provider=deepseek` 的模型配置；
- runtime 能正确实例化 DeepSeek chat provider；
- 未配置 API Key 时返回可预期错误；
- **不要求** 本轮完成真实 DeepSeek 联调。

### Task 1B: 接入 LangChain adapter（chat + structured output）

**Files:**
- Create: `backend/llm/services/providers/langchain_chat_provider.py`
- Create: `backend/llm/services/providers/langchain_structured_output.py`
- Optional Create: `backend/llm/services/providers/langchain_embedding_provider.py`
- Modify: `backend/llm/services/runtime_service.py`
- Test: `backend/llm/tests/test_langchain_adapters.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | 当前不存在 LangChain adapter 路径 |
| 2 | 封装 chat adapter | 只对 service 层暴露统一接口 |
| 3 | 封装 structured output adapter | 为风险抽取服务 |
| 4 | 决定 embedding 是否延期 | 第一版默认可延后，不强行做 |
| 5 | 跑测试 | chat / structured output 路径可实例化 |
| 6 | 提交 | `feat(llm): add langchain adapters for chat and structured output` |

**验收标准：**
- chat adapter 可被 runtime 选择；
- structured output adapter 有测试覆盖；
- **embedding adapter 如未落地，需在文档中显式标注 deferred**。

### Task 2: 打通问答 session/message 落库

**Files:**
- Modify: `backend/chat/controllers/ask_controller.py`
- Modify/Create: `backend/chat/controllers/session_message_controller.py`
- Modify: `backend/chat/services/ask_service.py`
- Modify: `backend/chat/services/session_service.py`
- Modify: `frontend/src/api/chat.js`
- Modify: `frontend/src/api/qa.js`
- Modify: `frontend/src/components/FinancialQA.vue`
- Test: `backend/chat/tests.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | 问答后应新增用户/助手消息 |
| 2 | 明确新旧 API 策略 | 新增 `session messages` 语义；旧 ask 兼容 |
| 3 | 后端写入 `ChatMessage` | 用户问题与回答都保存 |
| 4 | 前端透传 `session_id` | 新会话创建后持续复用 |
| 5 | 跑测试 | 历史会话可回放 |
| 6 | 提交 | `feat(chat): persist qa messages into sessions` |

**验收标准：**
- 至少有一条标准路径可通过 `session -> messages` 回放完整问答；
- 旧 ask 接口仍可兼容；
- 历史消息页面读取真实数据库消息。

### Task 3: 引入真实 KnowledgeBase 模型与迁移回填

**Files:**
- Modify/Create: `backend/knowledgebase/models.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/chat/models.py`（如需绑定 kb）
- Modify: `backend/knowledgebase/controllers/*.py`
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Test: `backend/knowledgebase/tests.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | 文档应归属具体知识库 |
| 2 | 新增 `KnowledgeBase` 模型与迁移 | 至少含 name/description/status |
| 3 | 增加 backfill 迁移 | 为历史文档创建默认知识库并挂载 |
| 4 | 如需要，补 session 的 kb 归属 | 保证后续问答上下文清晰 |
| 5 | 调整上传/列表接口 | 支持按知识库维度工作 |
| 6 | 跑测试 | 创建知识库、上传文档、历史数据回填成功 |
| 7 | 提交 | `feat(kb): add explicit knowledge base model` |

**迁移策略：**
- 创建一个默认知识库（例如“默认知识库”）；
- 将历史 `Document` 全部回填到默认知识库；
- 若 session 暂不绑定 kb，需在文档中显式说明 deferred；
- 若迁移失败，可通过 migration rollback + 保留旧字段回退。

### Task 4: 风险抽取升级到 LangChain structured output，并走异步任务

**Files:**
- Modify: `backend/risk/services/extraction_service.py`
- Create: `backend/risk/services/extraction_schema.py`
- Modify/Create: `backend/risk/tasks.py`
- Modify: `backend/risk/controllers/*.py`
- Test: `backend/risk/tests.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | 非法 JSON 或缺字段时要稳定失败 |
| 2 | 增加 schema | 定义风险事件结构 |
| 3 | 用 LangChain structured output 封装调用 | 替代手工 JSON 解析 |
| 4 | 加入 deterministic 去重 | 规则见下文 |
| 5 | 改为 Celery 异步任务 | 接口只负责发起任务 |
| 6 | 保存任务状态和错误信息 | 前端可轮询展示 |
| 7 | 跑测试 | 成功抽取 / 非法输出 / 去重 / 任务失败均覆盖 |
| 8 | 提交 | `feat(risk): use structured output for extraction` |

**去重规则（第一版，必须可测试）：**
- 只做 deterministic 去重；
- 作用域：**同一 document**；
- 判重键：`chunk_id + risk_type + normalized(summary)`；
- `normalized(summary)` 规则：trim、lower、合并多余空白；
- **不做** embedding 近似去重。

**验收标准：**
- 抽取任务异步执行；
- 有任务状态可查；
- 同文档重复抽取不会生成 deterministic 重复事件；
- provider 输出非法时保存失败原因。

### Task 5: 风险报告升级为“统计 + 模型总结 + 降级策略”

**Files:**
- Modify: `backend/risk/services/report_service.py`
- Modify/Create: `backend/risk/tasks.py`
- Modify: `backend/prompts/risk/*.txt`
- Modify: `backend/risk/controllers/*.py`
- Test: `backend/risk/tests.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | company / time-range 两种模式都要覆盖 |
| 2 | 抽离 deterministic 报告主体 | 统计、事件列表、来源先稳定生成 |
| 3 | 增加 summary prompt | 模型只负责总结段落 |
| 4 | 改为异步任务 | 请求只触发生成 |
| 5 | 增加 provider 异常降级 | 总结失败时主体仍可返回/保存 |
| 6 | 跑测试 | 双模式、异常降级、保存 report 均覆盖 |
| 7 | 提交 | `feat(risk): add llm generated report summaries` |

**验收标准：**
- 支持按公司/时间区间生成；
- 保存 `RiskReport` 实体；
- 输出包含统计、事件列表、summary、source metadata；
- provider 异常时保留 deterministic 报告主体并标注 summary 失败。

### Task 6: 评测体系升级

**Files:**
- Modify: `backend/llm/services/evaluation_service.py`
- Create: `backend/llm/eval_datasets/*.json`
- Modify: `frontend/src/components/EvaluationResult.vue`
- Test: `backend/llm/tests.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | 评测结果不应只来自硬编码 smoke case |
| 2 | 引入最小评测样本集 | QA / extraction 各一份 |
| 3 | 定义最小指标集 | 见下文 |
| 4 | 重构评测服务 | 支持 dataset/version/model_config 维度 |
| 5 | 前端展示结果结构 | 展示数据集、版本、指标 |
| 6 | 跑测试 | 评测记录可重复生成和查询 |
| 7 | 提交 | `feat(eval): upgrade evaluation pipeline` |

**最小指标集：**
- QA：引用返回率、答案非空率、关键 token 命中率；
- Extraction：字段完整率、JSON/结构合法率、去重后重复率；
- 通用：平均耗时、模型配置版本。

### Task 7: 去掉前端 mock 运维数据

**Files:**
- Modify: `frontend/src/api/ops.js`
- Create: `backend/systemcheck/controllers/ops_log_controller.py`
- Create: `backend/systemcheck/services/ops_log_service.py`
- Modify: `backend/systemcheck/urls.py`
- Test: `backend/systemcheck/tests/*.py`

| Step | 动作 | 说明 |
|---|---|---|
| 1 | 写失败测试 | `/api/ops/logs` 不存在时先失败 |
| 2 | 后端加日志接口 | 先返回最近系统事件 / 应用日志摘要 |
| 3 | 前端改真实请求 | 删除 mock Promise |
| 4 | 跑测试和前端联调 | Dashboard 不再展示假数据 |
| 5 | 提交 | `feat(ops): replace mock dashboard logs with api` |

**优先级说明：**
- 该任务优先级低于知识库 / 问答 / 风险主线；
- 只在前面主链路稳定后再处理。

---

## 6. DeepSeek API 占位方案（等待主人提供密钥）

| 项 | 当前处理 |
|---|---|
| API Key | 先不写入仓库，后续由主人提供 |
| 配置模型 | 先支持新增 `provider=deepseek` 的模型配置记录 |
| 第一版能力 | **只要求 chat provider 占位** |
| embedding | 第一版默认 deferred，继续沿用现有 embedding provider |
| 默认用途 | 优先用于 chat / risk summary / extraction |

建议预留环境变量：

| 变量名 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | DeepSeek base URL |
| `DEEPSEEK_CHAT_MODEL` | 默认聊天模型名 |
| `DEEPSEEK_EMBEDDING_MODEL` | 若后续启用 embedding 时使用 |

---

## 7. 里程碑表（给主人看的版本）

| 里程碑 | 目标日期 | 交付物 | 风险 |
|---|---|---|---|
| M1 | T+1 | DeepSeek 占位 provider + LangChain adapter + 错误处理 | provider 兼容性 |
| M2 | T+3 | 问答 session/message 闭环 + 新旧 API 兼容 | 前后端接口收口 |
| M3 | T+5 | 多知识库 + 历史数据回填 | migration/backfill |
| M4 | T+7 | 风险抽取 structured output + 报告异步升级 | LLM 输出稳定性 / 任务状态 |
| M5 | T+9 | 评测升级 + 运维去 mock | 数据集质量与日志来源 |

---

## 8. 开发约束

| 约束 | 说明 |
|---|---|
| 先文档后开发 | 以本计划为基准推进，不跳步骤 |
| 每个任务都先补测试 | 遵循 TDD |
| 每个阶段独立 commit | 便于回退 |
| 不把 API Key 写进仓库 | 仅走 env / deploy 配置 |
| LangChain 只做适配，不替代业务层 | 避免后续维护困难 |
| 耗时任务必须异步化 | 抽取 / 报告走 Celery + 任务状态 |

---

## 9. 执行入口

当前建议开发顺序：

1. **Task 1A：DeepSeek chat provider 占位**
2. **Task 1B：LangChain adapter（chat + structured output）**
3. **Task 2：问答 session/message 闭环**
4. **Task 3：多知识库模型与迁移回填**
5. **Task 4：风险抽取 structured output + 异步化**
6. **Task 5：风险报告升级 + 异步化**
7. **Task 6：评测升级**
8. **Task 7：运维大盘去 mock**

Plan complete and saved to `docs/superpowers/plans/2026-04-02-finmodpro-langchain-deepseek-next-steps.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - 我分任务调度前后端实现并逐段 review。

**2. Inline Execution** - 在当前会话里按计划逐项推进。