# FinModPro 论文/报告章节简要说明

本文按 FinModPro 已完整接入 LightRAG 与 Neo4j 图增强能力后的系统形态整理，可作为毕业设计、课程设计或项目说明书的章节草稿。

## 第二章 相关知识和技术

本章主要介绍系统开发过程中使用的关键技术。

FinModPro 前端采用 Vue 3、Vue Router、Vite 和 Element Plus 构建，负责用户登录、工作区、知识库管理、智能问答、风险分析和管理端界面展示。后端采用 Django 5 和 Django REST Framework 构建 REST API，使用 Django ORM 管理业务数据，使用 JWT 实现前后端分离场景下的身份认证。

数据库方面，系统使用 MySQL 保存用户、权限、文档、问答、风险事件、模型配置和审计日志；使用 Redis 作为缓存和 Celery 异步任务队列的消息中间件；使用 Milvus 保存文档 chunk、实体和关系的向量索引；使用 Neo4j 保存 LightRAG 抽取出的实体关系图谱。

文档解析方面，系统保留轻量解析服务边界，对外输出统一的 element 结构；其中 PDF 主解析和后端 fallback 统一采用 PyMuPDF，以提升文本块、页码和基础版面信息抽取质量。智能算法方面，系统采用 RAG 和 GraphRAG 技术。传统 RAG 由文档解析、文本切块、embedding、Milvus 检索、rerank 和大模型回答组成；GraphRAG 通过 LightRAG 对文档进行实体抽取、关系抽取和图谱构建，使系统可以支持跨文档、多跳关系和证据链问答。系统还使用 LangGraph 编排问答流程，使用 LiteLLM Gateway 统一管理不同模型服务。

## 第三章 需求分析

本章明确系统的用户角色、功能需求和非功能需求。

### 用户角色

系统主要包含三类用户：

| 角色 | 说明 |
|---|---|
| 普通用户 | 使用智能问答、知识库检索、风险摘要和历史会话功能 |
| 管理员 | 管理用户、角色、知识库、模型配置、评测结果和 LightRAG 图谱入口 |
| 系统运维人员 | 负责部署、模型服务、数据库、向量库、图数据库和运行状态监控 |

### 功能需求

| 模块 | 功能需求 |
|---|---|
| 用户认证 | 支持注册、登录、Token 鉴权、退出登录和当前用户信息查询 |
| 权限管理 | 支持角色管理、权限分配、管理员访问控制 |
| 知识库管理 | 支持文档上传、PyMuPDF PDF 解析、切块、向量化、入库、版本管理和 chunk 查看 |
| GraphRAG | 支持 LightRAG 图谱索引、Neo4j 图存储、实体关系检索和图增强问答 |
| 智能问答 | 支持问题路由、知识库检索、引用来源、历史会话和上下文过滤 |
| 风险分析 | 支持风险事件抽取、风险等级识别、证据保存、审核和报告生成 |
| 模型中台 | 支持模型配置、模型路由、LiteLLM 同步、调用日志、评测和微调任务管理 |
| 运维看板 | 支持健康检查、统计看板、审计日志和系统状态展示 |

### 非功能需求

系统需要满足以下非功能需求：

- **安全性**：使用 JWT 和 RBAC 控制接口访问，敏感配置不写入代码仓库。
- **可扩展性**：RAG、LightRAG、模型网关和图数据库采用独立服务设计，便于后续替换和扩容。
- **可靠性**：文档入库采用任务状态跟踪和失败记录，LightRAG 故障不影响基础知识库主链路。
- **可维护性**：前后端分层清晰，业务模块按 Django app 和 Vue 组件拆分。
- **可观测性**：保存检索日志、模型调用日志、审计日志和系统健康状态。
- **性能要求**：通过 Milvus 提升向量检索效率，通过 Redis 和 Celery 支持异步处理，通过 Neo4j 提升图关系查询能力。

## 第四章 系统设计

本章介绍系统模块、架构、数据库和机器学习模型设计。

### 系统架构设计

系统采用前后端分离和多服务协同架构。前端 Vue 应用负责页面展示和用户交互，后端 Django 提供统一 API。MySQL 保存业务数据，Milvus 保存向量索引，Neo4j 保存知识图谱，Redis 负责缓存和异步队列，LiteLLM Gateway 统一接入大模型服务，LightRAG 负责图增强索引和 GraphRAG 查询。

```text
用户浏览器
  -> Vue 前端
  -> Django REST API
  -> MySQL / Redis / Milvus / Neo4j / LightRAG / LiteLLM
```

### 模块设计

系统主要划分为：

- 认证与权限模块
- 知识库管理模块
- RAG 检索模块
- LightRAG 图增强模块
- 智能问答模块
- 风险分析模块
- 模型中台模块
- 运维审计模块

各模块之间保持边界清晰。知识库模块负责文档处理和向量入库；LightRAG 负责实体关系图谱；问答模块负责调度普通 RAG 和 GraphRAG；风险模块复用知识库与模型能力完成金融风险识别。

### 数据库设计

系统业务数据库采用 MySQL。主要表包括用户权限表、知识库表、聊天问答表、风险分析表、模型中台表和审计表。完整表结构见 [database-design.md](./database-design.md)。

核心关系为：

- 一个用户可以上传多个文档、创建多个会话和记忆条目。
- 一个数据集包含多个文档。
- 一个文档包含多个版本、入库任务、section chunk 和 chunk。
- 风险事件可以关联来源文档和来源 chunk。
- 模型配置可以关联评测记录、微调任务和调用日志。
- LightRAG 图谱节点通过 `document_id`、`chunk_id`、`dataset_id` 与业务数据关联。

### 机器学习模型设计

系统使用的大模型能力主要包括：

| 模型类型 | 作用 |
|---|---|
| Chat Model | 问答生成、查询重写、相关性判断、风险摘要 |
| Embedding Model | 文档 chunk、实体、关系和查询向量化 |
| Rerank Model | 对召回片段进行相关性重排序 |
| LightRAG Extraction | 实体抽取、关系抽取、图谱构建 |
| Fine-tuned Model | 面向特定金融任务的模型增强 |

文档解析层使用 PyMuPDF 处理 PDF，将页面和文本块映射为统一 element，再进入 chunk 和向量化流程。该设计不把 PyMuPDF 扩展为所有格式的解析器，DOCX/TXT 仍通过轻量解析服务的对应路径处理。

问答流程设计为：用户提问后，系统先判断是否需要检索；若需要，则进行查询重写，并根据问题类型选择 Milvus RAG 或 LightRAG GraphRAG；检索结果经过 rerank 和相关性评估后，作为上下文传入大模型生成答案。

## 第五章 系统实现

本章展示主要功能模块的实现界面和核心代码。

### 用户认证与权限实现

前端提供登录界面，用户提交账号密码后调用后端认证接口。后端验证成功后签发 JWT，前端将 Token 存储在本地，并在后续请求中通过请求头携带。路由守卫根据 Token、用户角色和权限决定是否允许进入工作区或管理端。

核心代码位置：

- `backend/authentication/`
- `backend/rbac/`
- `frontend/src/api/auth.js`
- `frontend/src/router/routes.js`
- `frontend/src/lib/permission.js`

### 知识库实现

知识库页面支持文档上传、列表筛选、批量入库、处理状态查看和 chunk 检查。后端接收文件后创建 `Document`，入库任务依次执行解析、切块和向量化。PDF 解析优先调用轻量解析服务中的 PyMuPDF 路径，服务失败时由后端 PyMuPDF fallback 接管；解析后的文本片段写入 MySQL，向量写入 Milvus。

核心代码位置：

- `backend/knowledgebase/models.py`
- `backend/knowledgebase/services/document_service.py`
- `backend/knowledgebase/services/parser_service.py`
- `backend/knowledgebase/services/vector_service.py`
- `frontend/src/components/KnowledgeBase.vue`
- `frontend/src/api/knowledgebase.js`

### LightRAG 图增强实现

LightRAG 作为独立服务接入系统。文档完成解析后，同步到 LightRAG 进行实体和关系抽取。LightRAG 将图谱写入 Neo4j，并提供图谱检索、图谱探索和图增强问答接口。管理端通过 `/admin/lightrag` 进入图谱管理界面。

核心实现关注点：

- 文档同步：将 `Document.parsed_text`、`document_id`、`dataset_id`、chunk metadata 同步给 LightRAG。
- 图谱索引：LightRAG 抽取实体和关系，Neo4j 保存图节点与边。
- 查询增强：问答模块根据问题类型调用 LightRAG 检索结果，与 Milvus 召回结果共同构建上下文。

### 智能问答实现

问答模块使用 LangGraph 编排流程，包括路由、查询重写、检索、相关性评估和上下文构建。系统会保存用户消息、助手消息、引用来源和模型元数据，支持历史会话与上下文过滤。

核心代码位置：

- `backend/chat/services/rag_graph_service.py`
- `backend/chat/models.py`
- `backend/rag/services/retrieval_service.py`
- `frontend/src/components/FinancialQA.vue`
- `frontend/src/api/chat.js`

### 风险分析实现

风险模块从知识库文档中抽取风险事件，保存风险等级、事件时间、证据文本和置信度。管理员或用户可以查看风险事件列表，对事件进行审核，并基于公司或时间范围生成风险报告。

核心代码位置：

- `backend/risk/models.py`
- `backend/risk/services/extraction_service.py`
- `backend/risk/services/sentiment_service.py`
- `frontend/src/components/RiskSummary.vue`
- `frontend/src/api/risk.js`

### 模型中台实现

模型中台支持管理 chat、embedding、rerank 模型配置，并通过 LiteLLM Gateway 统一路由模型调用。系统记录模型调用日志、评测指标和微调任务状态，用于分析模型质量、延迟和失败原因。

核心代码位置：

- `backend/llm/models.py`
- `backend/llm/services/`
- `frontend/src/components/LlmGatewayDashboard.vue`
- `frontend/src/components/ModelConfig.vue`
- `frontend/src/api/llm.js`

## 第六章 系统测试

本章通过测试用例验证系统功能是否满足需求。

### 测试方法

系统测试包括后端接口测试、前端单元测试、构建测试和部署后冒烟测试。后端使用 Django test runner，前端使用 Node test，并通过 `npm run build` 验证生产构建。

### 主要测试用例

| 编号 | 测试模块 | 测试内容 | 预期结果 |
|---|---|---|---|
| TC-01 | 用户认证 | 输入正确账号密码登录 | 返回 Token 和用户信息 |
| TC-02 | 权限控制 | 普通用户访问管理端 | 请求被拒绝或页面跳转 |
| TC-03 | 文档上传 | 上传 txt/pdf/docx 文件 | 创建文档记录，状态为 uploaded |
| TC-04 | 文档入库 | 执行 PyMuPDF PDF 解析、切块、向量化 | 文档状态变为 indexed，生成 chunk 和向量 ID |
| TC-05 | 普通 RAG | 输入知识库相关问题 | 返回答案和引用来源 |
| TC-06 | LightRAG | 查询跨文档实体关系问题 | 返回图增强结果和相关证据 |
| TC-07 | 会话历史 | 多轮问答后查看历史 | 正确展示会话和消息 |
| TC-08 | 风险抽取 | 对文档执行风险识别 | 生成风险事件和证据文本 |
| TC-09 | 模型配置 | 启用某个 chat 模型 | 同类其它模型自动取消启用 |
| TC-10 | 调用日志 | 发起模型调用 | 保存 provider、延迟、状态和 token 信息 |
| TC-11 | 审计日志 | 执行关键操作 | 生成审计记录 |
| TC-12 | 部署冒烟 | 调用健康检查接口 | 返回系统健康状态 |

### 测试命令

后端测试：

```bash
cd backend
source .venv/bin/activate
python manage.py check
python manage.py test
```

前端测试：

```bash
cd frontend
npm test
npm run build
```

部署后验证：

```bash
./scripts/smoke-check.sh
```

## 第七章 总结与展望

本章总结系统成果、当前不足和未来改进方向。

### 总结

FinModPro 实现了一个面向金融风控场景的智能知识分析系统。系统完成了用户认证、权限控制、金融知识库管理、RAG 检索问答、LightRAG 图增强检索、风险事件抽取、模型中台、评测记录和运维审计等功能。通过 MySQL、Milvus、Neo4j、Redis、LiteLLM 和 LightRAG 等技术组合，系统具备了从非结构化金融文档到向量索引、知识图谱和智能问答的完整处理链路。

接入 LightRAG 后，系统不仅可以基于语义相似度检索文档片段，还可以基于实体关系图谱回答跨文档、多跳关系和证据链问题，使金融风险分析能力更加完整。

### 不足

当前系统仍存在以下不足：

- LightRAG 和 Neo4j 增加了部署复杂度，对服务器内存和磁盘资源要求更高。
- 图谱实体消歧、关系置信度评估和图谱质量治理仍需进一步完善。
- 风险事件抽取依赖模型能力，复杂金融文本下仍可能出现漏抽或误抽。
- 模型评测数据集规模有限，评测结果还需要更多真实业务数据验证。
- 前端图谱探索、可视化分析和批量治理能力仍可继续增强。

### 展望

后续可以从以下方向继续改进：

- 引入更完善的实体消歧、关系合并和图谱质量评估机制。
- 将 LightRAG 结果与现有 LangGraph 问答流程进一步融合，形成可配置检索路由。
- 增强 Neo4j 图谱可视化，支持实体搜索、关系路径分析和风险传播链展示。
- 建立金融领域评测集，持续评估 RAG、GraphRAG、risk extraction 和 report generation 效果。
- 增加多租户、数据隔离、审计追踪和生产级安全加固。
- 优化异步任务调度、增量索引、失败重试和大规模文档处理性能。
