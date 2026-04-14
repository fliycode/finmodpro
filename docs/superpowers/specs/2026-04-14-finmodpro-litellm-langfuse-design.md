# FinModPro LiteLLM + Langfuse 接入设计

日期：2026-04-14

## 1. 目标

为 FinModPro 引入一套适配当前架构的 LLM 网关与观测方案：

- 使用 `LiteLLM self-host` 作为统一模型网关
- 使用 `Langfuse Cloud` 作为第一阶段观测后端
- 保持现有 `Django service -> provider -> upstream` 的调用边界
- 为未来外部部署的训练模型预留统一接入路径

本设计只覆盖第一阶段，不包含知识库解析升级和训练执行子系统。

## 2. 当前事实

当前仓库已经具备接入这套方案的基础边界：

- `chat`、`risk`、`sentiment` 通过 `get_chat_provider()` 调模型
- `knowledgebase` 通过 `get_embedding_provider()` 调 embedding
- `llm.ModelConfig` 已经是 `provider + capability + model_name + endpoint + options` 的配置模型
- 管理端已有模型配置页和连接测试接口
- 训练相关当前只有 `FineTuneRun` 登记层，没有训练执行层

这意味着第一阶段最合理的做法不是改业务 API，而是补一个更高层的网关和观测面。

## 3. 范围

### 3.1 In Scope

- 新增 `LiteLLM` 作为统一模型网关
- 新增 `litellm` provider 类型
- 让 `chat` 与 `embedding` 都可以走 LiteLLM
- 接入 `Langfuse Cloud`
- 为 `chat/rag/risk/sentiment/ingest` 增加业务级 trace/span
- 保留现有 `ollama/deepseek` provider 作为回退路径

### 3.2 Out of Scope

- `Langfuse self-host`
- `LiteLLM` 多租户、预算、虚拟 key、高级路由治理
- `Unstructured` 接入
- `LLaMA-Factory` 训练执行接入
- 修改现有前端业务页面对话、检索、风险分析接口形状
- 引入 agent/workflow 式 RAG 编排

## 4. 设计原则

- 不打破当前 `provider` 抽象
- 不把 LiteLLM SDK 散落进业务 service
- 观测是旁路能力，不能阻断主业务
- 第一阶段优先低风险、可回退、可验证
- 外部训练模型未来必须能通过同一配置面接入

## 5. 架构设计

### 5.1 组件职责

#### Django / FinModPro

职责：

- 管理模型配置
- 选择激活的 `chat` / `embedding` 模型
- 构建 provider
- 执行业务逻辑
- 上报业务级 trace/span

不负责：

- 管理真实上游厂商差异
- 训练模型路由
- LLM 调用统一审计与成本聚合

#### LiteLLM

职责：

- 作为统一 OpenAI-compatible 网关
- 将 `DeepSeek`、`Ollama`、未来外部训练模型统一映射为模型别名
- 将 LLM 请求/响应、token、延迟等上报到 Langfuse

不负责：

- 业务级 retrieval/span 语义
- 文档解析、风险抽取业务逻辑

#### Langfuse Cloud

职责：

- 承接 LiteLLM 的 LLM 调用观测
- 承接 Django 业务级 trace/span
- 提供链路、延迟、成本、失败定位能力

不负责：

- 决定模型路由
- 承担业务主路径依赖

### 5.2 运行时数据流

第一阶段目标数据流：

1. 管理员在模型配置页创建 `provider=litellm` 的 `chat` / `embedding` 配置
2. Django `runtime_service` 根据激活配置构建 `LiteLLMChatProvider` 或 `LiteLLMEmbeddingProvider`
3. provider 通过 LiteLLM proxy 发起 OpenAI-compatible 请求
4. LiteLLM 将请求路由到 `DeepSeek`、`Ollama` 或未来外部模型
5. LiteLLM 将 LLM 级日志发送到 Langfuse
6. Django 在关键业务链路补业务 span，并发送到 Langfuse

### 5.3 为什么不直接在 Django 里用 LiteLLM SDK

不采用 SDK 直连，原因是：

- 会把网关职责重新散回应用层
- 不利于未来外部训练模型统一接入
- 不利于统一路由、统一 alias、统一观测
- 与当前 `ModelConfig -> provider -> upstream` 结构不匹配

因此第一阶段必须采用 `LiteLLM proxy` 模式。

## 6. 配置模型设计

### 6.1 ModelConfig 扩展

当前 `provider` 仅支持：

- `ollama`
- `deepseek`

第一阶段新增：

- `litellm`

第一阶段不新增新的 capability 类型，继续沿用：

- `chat`
- `embedding`

### 6.2 litellm 类型配置语义

当 `provider=litellm` 时：

- `endpoint`：LiteLLM proxy 地址，例如 `http://litellm:4000`
- `model_name`：LiteLLM 内部模型别名，例如 `chat-default`、`embed-default`
- `options.api_key`：LiteLLM master key 或访问 key
- `options.temperature` / `options.max_tokens`：继续沿用现有配置方式

### 6.3 管理台行为

管理台 [ModelConfig.vue](/root/finmodpro/frontend/src/components/ModelConfig.vue) 第一阶段需要：

- 增加 `litellm` provider 选项
- `chat` 与 `embedding` 都允许选择 `litellm`
- 表单保留现有结构，不新增复杂字段
- 连接测试继续使用现有“测试连接”动作

第一阶段不做：

- LiteLLM 模型别名自动发现
- 从 LiteLLM 控制台自动同步模型列表

## 7. Provider 设计

### 7.1 新增 Provider

新增两个 provider：

- `LiteLLMChatProvider`
- `LiteLLMEmbeddingProvider`

它们对业务层暴露的接口必须与现有抽象保持一致：

- `chat(messages, options=None)`
- `stream(messages, options=None)`
- `embed(texts, options=None)`

### 7.2 HTTP 协议

第一阶段直接调用 LiteLLM OpenAI-compatible 接口：

- chat: `/v1/chat/completions`
- embedding: `/v1/embeddings`

不使用 LiteLLM Python SDK。

### 7.3 外部训练模型兼容

未来如果训练模型部署在外部推理服务上，只要它满足以下之一：

- OpenAI-compatible API
- Ollama-compatible endpoint
- LiteLLM 已支持 provider

就只需要：

1. 在 LiteLLM 注册模型别名
2. 在 FinModPro 新增或切换一条 `ModelConfig`

业务层无需再改。

## 8. LiteLLM 部署设计

### 8.1 服务形态

在 [docker-compose.prod.yml](/root/finmodpro/docker-compose.prod.yml) 中新增 `litellm` 服务。

第一阶段 LiteLLM 作为独立容器运行，不与 Django 合并。

### 8.2 配置文件

新增 LiteLLM 配置文件，例如：

- `deploy/litellm/config.yaml`

第一阶段只注册最小模型集合：

- `chat-default` -> 当前默认 chat 上游
- `embed-default` -> 当前默认 embedding 上游
- 可选 `risk-analyst` -> 单独的风险分析模型别名

### 8.3 第一阶段上游映射建议

- `chat-default` -> `deepseek` 或 `ollama`
- `embed-default` -> `ollama embedding`

第一阶段不做自动 fallback 策略，先保持显式 alias。

## 9. Langfuse 接入设计

### 9.1 第一阶段采用 Langfuse Cloud

采用 `Langfuse Cloud`，不做 self-host。

原因：

- self-host 会显著增加部署复杂度
- 当前目标是先把 LLM 网关和观测链路跑通
- 先验证 trace 结构和使用方式，比先搭一套新观测基础设施更重要

### 9.2 双层观测

第一阶段采用两层观测：

#### LLM 层

由 LiteLLM 负责将模型调用、token、延迟、成本打到 Langfuse。

#### 业务层

由 Django 负责补业务 span，重点覆盖：

- `chat.services.ask_service`
- `rag.services.retrieval_service`
- `risk.services.extraction_service`
- `risk.services.sentiment_service`
- `knowledgebase.services.document_service`

### 9.3 观测失败原则

Langfuse 上报失败不得阻断主业务。

要求：

- trace/span 发送失败只记日志
- 不改变问答、抽取、ingest 的成功或失败语义

## 10. 错误处理与回退

### 10.1 错误处理

LiteLLM provider 必须复用当前异常模型：

- 401/403 -> `llm_provider_auth_failed`
- 404/invalid model -> `llm_provider_invalid_model`
- 429 -> `upstream_rate_limited`
- 网络/超时/5xx -> `llm_provider_unavailable` 或 `llm_provider_error`

不得发明新的前端错误结构。

### 10.2 回退策略

第一阶段保留现有 provider：

- `ollama`
- `deepseek`

上线顺序：

1. 先新增 `litellm`
2. 管理员手动切换激活模型配置
3. 观察稳定性
4. 如有问题，直接切回旧 provider

第一阶段不删除旧 provider。

## 11. 验证方案

### 11.1 Provider 单测

验证：

- `LiteLLMChatProvider` 正常调用
- `LiteLLMChatProvider` 流式调用
- `LiteLLMEmbeddingProvider` 正常调用
- 401/404/429/5xx/超时映射

### 11.2 llm app 集成测试

验证：

- `provider=litellm` 的模型配置创建与更新
- key 掩码不回显
- chat / embedding 连接测试

### 11.3 业务回归

验证：

- `chat`
- `risk extraction`
- `sentiment`
- `knowledgebase embedding`

在切换到 `litellm` 后仍保持原有 API 契约。

### 11.4 部署级冒烟

验证：

- LiteLLM 容器可启动
- Django 可通过 LiteLLM 调 chat
- embedding 可调用
- Langfuse 中能看到 trace
- Langfuse 不可达时，主业务不失败

## 12. 非目标与后续阶段

### 第一阶段非目标

- Langfuse self-host
- Unstructured
- LLaMA-Factory
- LiteLLM 预算/多租户/虚拟 key
- 自动 fallback 路由
- 模型别名自动发现

### 后续阶段顺序

1. LiteLLM + Langfuse
2. Unstructured
3. 外部训练子系统（LLaMA-Factory）

## 13. 风险

- `litellm` provider 需要同时覆盖 chat 和 embedding，否则会形成半切换状态
- 连接测试当前更偏向 chat，embedding 连通性需要补足
- Langfuse 业务 span 如果做得太重，可能让业务代码侵入过多

## 14. 决策总结

第一阶段采用：

- `LiteLLM self-host`
- `Langfuse Cloud`
- `provider=litellm`
- 保留旧 provider 作为回退

这是当前对 FinModPro 最低风险、最可回滚、且能兼容未来外部训练模型的接法。
