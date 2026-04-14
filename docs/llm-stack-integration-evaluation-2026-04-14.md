# FinModPro 开源 LLM 基础设施接入评估

更新时间：2026-04-14

## 1. 结论先说

### 推荐结论

| 项目 | 结论 | 优先级 | 原因 |
|---|---|---:|---|
| LiteLLM | 值得接 | P0 | 最适合成为当前项目的统一 LLM Gateway，能把多模型接入、路由、鉴权、预算和后续训练产物接入收束到一个入口 |
| Langfuse | 值得接 | P0 | 能最快为 `chat / rag / risk / sentiment / evaluation` 提供可观测性，且与 LiteLLM 组合效果最好 |
| Unstructured | 值得接 | P1 | 直接补知识库入口质量，尤其能解决当前 `docx` 不可解析、PDF 解析质量弱、元数据不足的问题 |
| LLaMA-Factory | 值得接，但必须独立成子系统 | P2 | 适合承接你后面的训练页和微调流程，但不应直接塞进当前 Django 主请求链路 |
| LlamaIndex | 暂不接，按需接 | Deferred | 当前仓库已经有明确的 service/provider 边界，现阶段接入会和已有 RAG 逻辑重叠，收益不如前四项直接 |

### 对你这次排序的判断

- `Langfuse` 的优先级判断是对的，它最容易立刻让 `chat/risk/rag` 可观测。
- 但从架构收口角度看，`LiteLLM` 应该与 `Langfuse` 同级推进，甚至更像第 0 步。
- `Unstructured` 很适合做第二阶段，因为它直接改善知识库入口质量。
- `LLaMA-Factory` 不应该先做应用内接入，而应该先定义“训练子系统 + 产物回流”的边界。
- `LlamaIndex` 不是现在最该投入的点。

## 2. 当前仓库的真实情况

以下结论基于当前代码，不基于旧计划文档。

### 2.1 模型调用边界已经比较清晰

- `backend/chat/services/ask_service.py` 在检索后调用 `get_chat_provider().chat(...)`
- `backend/risk/services/extraction_service.py` 调用 `get_chat_provider()` 做风险抽取
- `backend/risk/services/sentiment_service.py` 调用 `get_chat_provider()` 做舆情分析
- `backend/knowledgebase/services/embedding_service.py` 调用 `get_embedding_provider()` 生成向量
- `backend/llm/services/runtime_service.py` 负责按 `ModelConfig` 构建 provider

这意味着：当前项目最适合接入的是“统一网关”和“统一观测”，而不是再引一个重型编排框架进入业务层。

### 2.2 RAG / 向量检索并没有依赖 LangChain

- `backend/knowledgebase/services/vector_service.py` 直接用 `pymilvus.MilvusClient`
- `backend/rag/services/vector_store_service.py` 直接调用 `VectorService().search(...)`
- `backend/rag/services/retrieval_service.py` 是自写检索 + 重排流程
- `backend/rag/services/rerank_service.py` 只是简单排序

因此当前仓库不是“LangChain 驱动的 RAG 项目”，只是“为了 DeepSeek provider 引入过 LangChain”。

### 2.3 知识库入口的真实短板在解析，而不是检索框架

- `backend/knowledgebase/services/parser_service.py` 目前只真正支持 `txt` 和 `pdf`
- `docx` 上传已放行，但解析直接抛出“DOCX 解析暂未实现”
- PDF 解析目前只依赖 `pypdf` 抽文本，页面结构、表格、版面和元素级元数据都很弱

所以如果想提升知识库质量，优先方向不是换 RAG 框架，而是补“文档解析层”。

### 2.4 LangChain 的真实运行时使用面非常小

- 直接代码引用只看到 `backend/llm/services/providers/deepseek_provider.py`
- `backend/requirements.txt` 中的 `langchain*` 依赖已移除
- `langchain-milvus` 在现有代码里本来就没有运行时代码使用

结论：你关于“LangChain 似乎可以去掉”的判断成立，且当前仓库已完成移除。

## 3. 为什么 LiteLLM 值得优先接

### 3.1 它和当前架构最匹配

LiteLLM 官方文档当前强调两条路径：

- Python SDK 统一不同模型厂商调用
- Proxy Server 作为 OpenAI 格式的统一 LLM Gateway

对 FinModPro 来说，更适合的是 **Proxy Server 模式**，不是把 LiteLLM SDK 散落到每个 service。

原因很直接：

- 你已经有 `ModelConfig` 表和 provider runtime
- 你已经有 `backend/llm/services/runtime_service.py`
- 你后面还想接训练产物、DeepSeek、Ollama，甚至别的 OpenAI-compatible 服务

这时最稳的方案不是继续堆 provider if/else，而是收口到一个统一网关。

### 3.2 它能替你解决什么

- 统一 `chat` 和 `embedding` 的上游入口
- 为 Ollama、DeepSeek、未来 vLLM 服务提供同一种 OpenAI 格式出口
- 提供路由、fallback、限额、成本统计、虚拟密钥等平台能力
- 可以直接和 Langfuse 打通 observability

### 3.3 在当前仓库里的建议接法

建议不要把 LiteLLM 当成“又一个业务 provider”；更合理的是把它当成 **LLM 网关层**。

推荐接入位点：

- `docker-compose.prod.yml`
  - 新增 `litellm` 服务
- `backend/llm/models.py`
  - 新增 `provider=litellm` 或更通用的 `provider=openai_compatible`
- `backend/llm/services/providers/`
  - 新增一个不依赖 LangChain 的 OpenAI-compatible provider
- `backend/llm/services/runtime_service.py`
  - 让 `chat` / `embedding` 都能走 LiteLLM base URL
- `frontend/src/components/ModelConfig.vue`
  - 支持配置 LiteLLM provider 与模型别名

### 3.4 最小可行落地顺序

1. 新增 LiteLLM 容器和 `config.yaml`
2. 先接两类模型：
   - `ollama/*`
   - `deepseek/*`
3. Django 只认识 LiteLLM 的 `base_url + model alias`
4. 保留旧 provider 一段时间做回退
5. 验证无误后再移除直接 DeepSeek 调用和 LangChain 依赖

### 3.5 对当前项目最重要的附加价值

如果你后面要接 `LLaMA-Factory`，训练后的模型最好不要直接让 Django 去管推理细节，而是：

- 训练在独立系统里完成
- 推理由 vLLM / 其他 OpenAI-compatible 服务暴露
- LiteLLM 再把这些模型收进统一网关

这样 FinModPro 的应用层完全不需要知道某个模型是 DeepSeek、Ollama 还是你自己微调出来的。

## 4. 为什么 Langfuse 应该和 LiteLLM 一起推进

### 4.1 它能立刻补当前项目的可观测性空白

Langfuse 官方文档当前强调：

- trace 不只记录 LLM 调用，也记录 retrieval、tool、custom logic
- 多轮应用可以按 session 追踪
- 可以通过 SDK、OpenTelemetry 或 LLM Gateway 方式接入

这和 FinModPro 当前的链路非常契合：

- `chat` 有 retrieval + answer generation
- `risk` 有 extraction
- `sentiment` 有 document-level analysis
- `evaluation` 有评测任务
- `knowledgebase` 有 ingest / parsing / chunking / indexing

这些都很适合被 trace 成一条完整链路。

### 4.2 当前仓库最应该打点的地方

建议第一批只打 5 个地方：

- `backend/chat/services/ask_service.py`
  - 记录 question、citations 数量、retrieval duration、model duration
- `backend/rag/services/retrieval_service.py`
  - 记录 query、filters、top_k、命中文档、score
- `backend/risk/services/extraction_service.py`
  - 记录 document_id、chunk 数、结构化输出是否解析成功
- `backend/risk/services/sentiment_service.py`
  - 记录文档范围、异常回退到 heuristic 的次数
- `backend/knowledgebase/services/document_service.py`
  - 记录 ingest 任务各阶段耗时

### 4.3 最适合当前项目的接法

推荐“双层接法”：

- 第一层：LiteLLM 接 Langfuse，自动采集 LLM 请求、模型、token、成本、延迟
- 第二层：Django 业务代码补自定义 trace/span，记录 retrieval、citation、document ingest、task outcome

只做其中一层都不够完整：

- 只做 Langfuse SDK，没有网关层，你后面多模型和训练产物会继续分散
- 只做 LiteLLM 网关日志，没有业务 span，你看不到 retrieval/filter/citation/task 细节

### 4.4 部署注意点

Langfuse 自托管会引入额外基础设施。官方文档强调它是开源且支持 self-host，但完整部署并不只是“再起一个容器”。

对 FinModPro 更现实的路径有两种：

- 方案 A：先用 Langfuse Cloud，最快起效
- 方案 B：单独维护 Langfuse 自托管栈，不和当前主业务 compose 强耦合

如果坚持自托管，当前仓库的 `docker-compose.prod.yml` 需要额外补它依赖的观测数据存储。`MinIO` 也许可以复用其中一部分对象存储职责，但这是部署层推断，落地前仍需按 Langfuse 官方 self-host 文档核对。

## 5. 为什么 Unstructured 值得做第二阶段

### 5.1 它补的是当前最真实的知识库痛点

FinModPro 当前的知识库入口问题不是“没有 index”，而是：

- `docx` 根本没解析
- PDF 只做了基础抽文本
- 没有元素级 metadata
- 没有版面理解
- 页面/表格/标题结构信息几乎没有被保留下来

Unstructured 正好是干这个的。

### 5.2 官方文档给你的关键信号

Unstructured 当前官方文档明确推荐优先使用：

- Unstructured UI
- Unstructured API

而不是继续把重点放在旧的 ingest CLI / Python ingest library 上。

这说明如果你现在接它，最好按“解析服务/API”方式设计，而不是把大量解析逻辑直接散落进 Django 进程。

### 5.3 在当前仓库里的合理接法

建议只替换“解析层”，不要一次性替换整条 ingest pipeline。

推荐位点：

- `backend/knowledgebase/services/parser_service.py`
  - 改为 parser adapter
- `backend/knowledgebase/services/document_service.py`
  - 维持现有 ingest orchestration
- `backend/knowledgebase/services/chunk_service.py`
  - 先保留你自己的 chunking 规则

最小可行版本：

- `txt` 继续本地解析
- `pdf/docx` 优先走 Unstructured
- 先只拿回 `text + page/element metadata`
- 仍由本项目负责 chunk、embed、index

这样改动最小，也最容易回滚。

### 5.4 你会立刻得到什么

- `docx` 从“不可用”变成“可入库”
- PDF 结构质量明显提升
- chunk metadata 更丰富，后面 citation 会更像样
- 为后续评测和风险抽取提供更干净的原文输入

## 6. 为什么 LLaMA-Factory 值得接，但必须独立成子系统

### 6.1 当前仓库已经有训练登记雏形

现有代码里已经有：

- `backend/llm/models.py` 中的 `FineTuneRun`
- `backend/llm/services/fine_tune_service.py`
- `frontend/src/components/ModelConfig.vue` 中的微调登记 UI

但这只是 registry，不是训练系统。

### 6.2 LLaMA-Factory 最适合补的不是“页面”，而是“训练执行面”

LLaMA-Factory 官方文档当前重点是：

- LoRA / QLoRA / SFT / DPO 等训练
- WebUI / CLI
- 推理支持
- 与 vLLM 等推理方式协同

这说明它很适合作为你的 **训练执行子系统**，但不适合直接嵌进 Django Web 请求。

### 6.3 推荐架构

建议把 LLaMA-Factory 放到单独边界：

1. FinModPro 负责：
   - 训练数据集登记
   - 训练任务发起
   - 训练状态同步
   - 训练产物登记
2. LLaMA-Factory 负责：
   - 真正的训练执行
   - GPU 资源消耗
   - adapter / merged model 产出
3. 推理层负责：
   - 把训练产物挂成 OpenAI-compatible 服务
4. LiteLLM 负责：
   - 把训练产物模型纳入统一网关
5. FinModPro 应用层继续只认：
   - `ModelConfig`
   - `chat provider`
   - `embedding provider`

### 6.4 为什么不能直接硬塞进当前主系统

- 训练任务是长作业
- 依赖 GPU / 大量磁盘 / 特定 Python 栈
- 和当前 Django + Celery + Milvus 的在线服务职责完全不同
- 直接耦合后，部署和排障复杂度会飙升

### 6.5 合理的第一步

不要先做“在线训练按钮一键跑”，而是先做三件事：

1. 补全 `FineTuneRun` 的 job metadata 字段设计
2. 定义训练数据集导出格式
3. 明确训练产物如何回流到 LiteLLM / 推理服务

## 7. 为什么 LlamaIndex 现在不该优先接

### 7.1 它不是没价值，而是现在收益不够大

LlamaIndex 官方文档当前最突出的价值有两类：

- data connectors / readers
- index / query engine / workflow / agent abstraction

这些能力并非没用，但对当前 FinModPro 来说不是第一性缺口。

### 7.2 当前接入它会和什么重叠

- 你已经有 `chat` / `rag` / `risk` 的 service 边界
- 你已经有 prompt 管理、session、citation、retrieval log
- 你当前最缺的并不是 agent workflow，而是：
  - 统一模型入口
  - 可观测性
  - 文档解析质量

这时候把 LlamaIndex 拉进来，很容易出现“再套一层抽象，但核心问题没解决”。

### 7.3 什么时候再考虑它

只有在下面场景出现时，LlamaIndex 才值得重新评估：

- 你要接很多外部数据连接器，比如 Notion / Google Docs / Slack
- 你要做更复杂的 workflow/agent 式 RAG
- 你想快速实验多种 query engine / retriever 组合

在此之前，它可以继续保持 Deferred。

## 8. LangChain 是否可以去掉

### 8.1 我的判断

已经完成移除，且这条方向上更稳的长期做法仍然是保持无 LangChain 运行时依赖。

### 8.2 依据

当前仓库里：

- `LangChain` 不承担 RAG 编排
- `langchain-milvus` 没有运行时代码使用
- 直接运行时依赖已经从 `DeepSeekChatProvider` 中移除

也就是说，LangChain 不是底层基石，而只是一次局部 provider 选型。

### 8.3 不建议直接裸删

这条依赖链已经从 `backend/llm/services/providers/deepseek_provider.py` 中移除。
安全路径仍然是先换掉 provider，再删依赖；当前仓库已经按这个路径完成了切换。

### 8.4 安全移除路径

建议按这个顺序做：

1. 新增一个不依赖 LangChain 的 OpenAI-compatible provider
2. 让它既能打 DeepSeek 官方接口，也能打 LiteLLM proxy
3. 把 `runtime_service.py` 切到新 provider
4. 跑通：
   - `llm`
   - `chat`
   - `risk`
   - `knowledgebase`
   相关测试
5. 删除：
   - `langchain`
   - `langchain-openai`
   - `langchain-milvus`
6. 标记旧的 LangChain 设计文档为 superseded，避免以后重复引入

### 8.5 最适合当前仓库的替代方式

考虑到仓库当前 `Ollama` provider 已经使用标准库 `urllib.request` 直连 HTTP，最一致的替代方案是：

- 新 provider 也用标准库或一个极薄的 OpenAI-compatible HTTP 客户端
- 不再引入额外编排依赖

这样能满足两个目标：

- 避免再引新的重依赖
- 保持和当前 provider 风格一致

### 8.6 需要特别注意的点

当前 `stream_question()` 会优先调用 provider 的 `stream()`。如果你替换 DeepSeek provider，不能无意中把流式能力删掉；至少要明确：

- 保持流式实现
- 或在迁移窗口内让 `/api/chat/ask/stream` 优雅降级到非流式

## 9. 推荐实施顺序

### 阶段 1：统一模型入口与观测

1. 接 LiteLLM Proxy
2. 接 Langfuse
3. 给 `chat/rag/risk/sentiment/ingest` 补 trace
4. 让 DeepSeek / Ollama 先都能从 LiteLLM 走

目标：模型入口统一，链路可观测。

### 阶段 2：修知识库入口

1. 引入 Unstructured 作为 `pdf/docx` 解析层
2. 保留现有 chunk/embed/index 流程
3. 补文档 ingest 的评测与错误追踪

目标：知识库输入质量提升，不推翻现有检索层。

### 阶段 3：移除 LangChain

1. 用 LiteLLM / OpenAI-compatible provider 替换 DeepSeek provider
2. 删除 `langchain*` 依赖
3. 更新测试和旧文档

目标：减少无效依赖，收口 provider 体系。

### 阶段 4：训练子系统

1. 用 LLaMA-Factory 承接训练执行
2. 训练产物通过 vLLM 或其他推理服务暴露
3. LiteLLM 收口训练模型入口
4. 前端再做真正的训练页

目标：把训练能力做成独立系统，而不是把训练逻辑塞进在线应用。

## 10. 这次我建议你先产出的设计文档范围

如果你下一步要继续做实现，我建议先拆成 3 份实现文档，而不是一份大而全：

1. `LiteLLM + Langfuse` 接入设计
2. `Unstructured` 知识库解析接入设计
3. `LLaMA-Factory` 训练子系统设计

这样每一块都能独立评审、独立落地、独立回滚。

## 11. 官方资料

以下结论优先参考官方文档或官方项目主页：

- LiteLLM Docs: https://docs.litellm.ai/
- Langfuse Docs: https://langfuse.com/docs
- Langfuse Self-hosting: https://langfuse.com/self-hosting/docker
- Unstructured Docs: https://docs.unstructured.io/api-reference/ingest/overview
- Unstructured Legacy API Overview: https://docs.unstructured.io/api-reference/legacy-api/overview
- LLaMA-Factory Docs: https://llamafactory.readthedocs.io/
- LLaMA-Factory Inference Docs: https://llamafactory.readthedocs.io/en/latest/getting_started/inference.html
- LlamaIndex Connectors Docs: https://docs.llamaindex.ai/en/stable/module_guides/loading/connector/
- LlamaIndex Langfuse Example: https://docs.llamaindex.ai/en/stable/examples/observability/LangfuseMistralPostHog/

## 12. 最后的明确建议

如果你现在只做一件事，我建议做：

- `LiteLLM + Langfuse` 一起设计并接入

如果你现在做两件事，我建议再加上：

- `Unstructured` 替换 `pdf/docx` 解析层

`LLaMA-Factory` 先定义子系统边界，不要急着塞进当前主系统。

`LlamaIndex` 先别接。

`LangChain` 可以准备移除，但必须在新的 OpenAI-compatible provider 或 LiteLLM 路径跑通之后再删。
