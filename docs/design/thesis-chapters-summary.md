# FinModPro 论文/报告章节简要说明

本文按 FinModPro 当前系统形态整理，可作为毕业设计、课程设计或项目说明书的章节草稿。

## 第二章 相关知识和技术

本章主要介绍系统开发过程中使用的关键技术。

FinModPro 前端采用 Vue 3、Vue Router、Vite 和 Element Plus 构建，负责用户登录、工作区、知识库管理、智能问答、风险分析和管理端界面展示。后端采用 Django 5 和 Django REST Framework 构建 REST API，使用 Django ORM 管理业务数据，使用 JWT 实现前后端分离场景下的身份认证。

数据库方面，系统使用 MySQL 保存用户、权限、文档、问答、风险事件、模型配置和审计日志；使用 Redis 作为缓存和 Celery 异步任务队列的消息中间件；使用 Milvus 保存文档 chunk 的向量索引。

文档解析方面，PDF 主解析由 pymupdf4llm 承担，后端 fallback 使用 pypdf，DOCX 使用 python-docx 解析。智能算法方面，系统采用 RAG 技术，由文档解析、文本切块、embedding、Milvus 检索、rerank 和大模型回答组成。检索抽象层使用 LlamaIndex，通过 LlamaIndex-over-Milvus 统一向量存储接口，并支持混合检索（MySQL 全文 + 关键词回退 + RRF 融合）。系统还使用 LangGraph 编排问答流程，使用 OpenAI 兼容 provider 直连不同模型服务。模型微调方面，系统通过 LLaMA-Factory 框架实现参数高效微调，由平台内登记数据集和训练配置，导出为 LLaMA-Factory 兼容格式，通过 runner agent 桥接外部训练执行与状态回调。

## 第三章 需求分析

本章明确系统的用户角色、功能需求和非功能需求。

### 用户角色

系统主要包含两类用户：

| 角色 | 说明 |
|---|---|
| 普通用户 | 使用智能问答、知识库检索、风险摘要和历史会话功能 |
| 管理员 | 管理用户、角色、知识库、模型配置、评测结果和系统监控 |

### 功能需求

| 模块 | 功能需求 |
|---|---|
| 用户认证 | 支持注册、登录、Token 鉴权、退出登录和当前用户信息查询 |
| 权限管理 | 支持角色管理、权限分配、管理员访问控制 |
| 知识库管理 | 支持文档上传、PDF/DOCX/TXT 解析、切块、向量化、入库、版本管理和 chunk 查看 |
| 智能问答 | 支持问题路由、知识库检索、引用来源、历史会话和上下文过滤 |
| 风险分析 | 支持风险事件抽取、风险等级识别、裁决丰富、验证、审核和报告生成导出 |
| 模型中台 | 支持模型配置、调用日志、评测和微调任务管理 |
| 运维看板 | 支持健康检查、统计看板、审计日志、系统监控与告警 |

### 非功能需求

系统需要满足以下非功能需求：

- **安全性**：使用 JWT 和 RBAC 控制接口访问，敏感配置不写入代码仓库。
- **可扩展性**：RAG、模型调用和向量数据库采用独立服务设计，便于后续替换和扩容。
- **可靠性**：文档入库采用任务状态跟踪和失败记录，解析链路有多级 fallback。
- **可维护性**：前后端分层清晰，业务模块按 Django app 和 Vue 组件拆分。
- **可观测性**：保存检索日志、模型调用日志、审计日志和系统健康状态。
- **性能要求**：通过 Milvus 提升向量检索效率，通过 Redis 和 Celery 支持异步处理。

## 第四章 系统设计

本章介绍系统模块、架构、数据库和机器学习模型设计。

### 系统架构设计

系统采用前后端分离和多服务协同架构。前端 Vue 应用负责页面展示和用户交互，后端 Django 提供统一 API。MySQL 保存业务数据，Milvus 保存向量索引，Redis 负责缓存和异步队列，模型调用通过 OpenAI 兼容 provider 直连。

```text
用户浏览器
  -> Vue 前端
  -> Django REST API
  -> MySQL / Redis / Milvus
  -> OpenAI 兼容 Provider（DeepSeek / DashScope / Ollama）
```

### 模块设计

系统主要划分为：

- 认证与权限模块
- 知识库管理模块
- RAG 检索模块
- 智能问答模块
- 风险分析模块
- 模型中台模块
- 运维审计模块

各模块之间保持边界清晰。知识库模块负责文档处理和向量入库；RAG 模块负责混合检索与重排序；问答模块负责调度检索与大模型生成；风险模块复用知识库与模型能力完成金融风险识别。

### 数据库设计

系统业务数据库采用 MySQL。主要表包括用户权限表、知识库表、聊天问答表、风险分析表、模型中台表和审计表。完整表结构见 [database-design.md](./database-design.md)。

核心关系为：

- 一个用户可以上传多个文档、创建多个会话和记忆条目。
- 一个数据集包含多个文档。
- 一个文档包含多个版本、入库任务、section chunk 和 chunk。
- 风险事件可以关联来源文档和来源 chunk。
- 模型配置可以关联评测记录、微调任务和调用日志。

### 机器学习模型设计

系统使用的大模型能力主要包括：

| 模型类型 | 作用 |
|---|---|
| Chat Model | 问答生成、查询重写、相关性判断、风险摘要 |
| Embedding Model | 文档 chunk 和查询向量化 |
| Rerank Model | 对召回片段进行相关性重排序 |
| Fine-tuned Model | 面向特定金融任务的模型增强 |

文档解析层使用 pymupdf4llm 处理 PDF，将页面和文本块映射为统一 element，再进入 chunk 和向量化流程。DOCX 使用 python-docx 解析。

问答流程设计为：用户提问后，系统先判断是否需要检索；若需要，则进行查询重写，通过 Milvus 进行向量检索；检索结果经过 rerank 和相关性评估后，作为上下文传入大模型生成答案。

## 第五章 系统实现

本章展示主要功能模块的实现界面和核心代码。

### 用户认证与权限实现

前端提供登录界面，用户提交账号密码后调用后端认证接口。后端验证成功后签发 JWT，前端将 Token 存储在内存中，并在后续请求中通过请求头携带。路由守卫根据 Token、用户角色和权限决定是否允许进入工作区或管理端。

核心代码位置：

- `backend/authentication/`
- `backend/rbac/`
- `frontend/src/api/auth.js`
- `frontend/src/router/routes.js`

### 知识库实现

知识库页面支持文档上传、列表筛选、入库、处理状态查看和 chunk 检查。后端接收文件后创建 `Document`，入库任务依次执行解析、切块和向量化。PDF 解析优先使用 pymupdf4llm，失败时由 pypdf fallback 接管；DOCX 使用 python-docx 解析。解析后的文本片段写入 MySQL，向量写入 Milvus。

核心代码位置：

- `backend/knowledgebase/models.py`
- `backend/knowledgebase/services/document_service.py`
- `backend/knowledgebase/services/parser_service.py`
- `backend/knowledgebase/services/vector_service.py`
- `frontend/src/components/KnowledgeBase.vue`
- `frontend/src/api/knowledgebase.js`

### RAG 检索与智能问答实现

RAG 检索使用 LlamaIndex-over-Milvus 统一架构。嵌入层通过 `FinModProEmbeddingAdapter` 实现 DashScope 嵌入调用和 Redis 24h 缓存。检索层支持混合检索：MySQL 全文检索 + 关键词回退 + RRF 融合重排序。问答编排使用 LangGraph，支持查询重写、多条检索路径和路由守卫。

核心代码位置：

- `backend/rag/services/llamaindex_store_service.py`
- `backend/rag/services/llamaindex_embedding_adapter.py`
- `backend/chat/services/rag_graph_service.py`
- `backend/chat/services/ask_service.py`

### 风险分析实现

风险模块实现了结构化抽取管道：基于文档 chunk 调用 LLM 进行风险事件抽取（JSON 结构化输出），经过裁决丰富（adjudication）和验证（verification）后生成风险事件，支持跨 chunk 去重和中文字段翻译。用户可审核风险事件，生成公司维度或时间区间的风险报告并导出 xlsx。

核心代码位置：

- `backend/risk/services/extraction_service.py`
- `backend/risk/services/adjudication_service.py`
- `backend/risk/services/verification_service.py`
- `backend/risk/services/report_service.py`
- `backend/risk/services/sentiment_service.py`
- `frontend/src/components/RiskSummary.vue`

### 模型中台与运维实现

模型中台支持 chat、embedding、rerank 三类模型的配置、启停、连接测试。LLM 控制台展示模型总览、调用日志、链路追踪、错误分布和成本统计。微调管理集成在模型配置页面，支持微调服务器配置、任务记录和数据导出。运维模块提供系统监控、告警管理和指标收集。

核心代码位置：

- `backend/llm/controllers/`
- `backend/llm/services/`
- `backend/ops/services/`
- `deploy/llamafactory-runner-agent/`
- `frontend/src/components/ModelConfig.vue`
- `frontend/src/components/LlmModelOverview.vue`
- `frontend/src/views/admin/AdminMonitoringView.vue`

### 微调管理实现

微调管理集成在模型配置页面（`/admin/llm/models`）。平台支持 LLaMA-Factory 作为训练框架，前端配置微调运行服务器、数据集名称/版本、训练策略（SFT/LoRA）和训练参数。后端通过 `fine_tune_export_service` 将数据集导出为 sharegpt 格式的 JSONL 文件，并通过 runner agent（`deploy/llamafactory-runner-agent/`）桥接外部 LLaMA-Factory 训练引擎。训练完成后，runner agent 通过回调接口将结果（状态、指标、产物路径）回写平台，更新微调运行记录。当前阶段训练样本为占位数据，真实监督数据集构建回路尚未接入。

核心代码位置：

- `backend/llm/controllers/fine_tune_controller.py`
- `backend/llm/services/fine_tune_service.py`
- `backend/llm/services/fine_tune_export_service.py`
- `backend/llm/services/fine_tune_runner_client.py`
- `deploy/llamafactory-runner-agent/app.py`
- `frontend/src/components/ModelConfig.vue`
- `frontend/src/lib/fine-tune-form.js`
- `frontend/src/lib/llamafactory-config.js`

## 第六章 系统测试

本章建议采用黑盒测试风格，可从以下维度展开：

- 功能测试：认证流程、文档上传入库、问答、风险抽取、报告生成
- 接口测试：主要 API 的正确性、错误处理和权限校验
- 性能测试：问答响应时间、入库吞吐量
- 兼容性测试：浏览器兼容性、移动端适配

## 第七章 总结与展望

总结部分建议涵盖：

- 系统完成的主要工作
- 各模块的实现成果
- 系统的技术特点和创新点

展望部分可写：

- 更细粒度的离线评测体系
- 情感分析独立前端页面
- 微调闭环补全
- 多源金融数据接入
- 知识图谱能力的重新评估与集成
