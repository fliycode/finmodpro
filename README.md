# FinModPro

FinModPro 是一个面向金融风控与金融知识管理场景的全栈智能分析系统。系统围绕“金融文档入库、向量检索、GraphRAG 问答、风险事件抽取、模型中台、权限治理与运维观测”构建，采用前后端分离与多服务部署架构。

本文档按 **LightRAG 已完整接入 FinModPro** 后的系统形态描述：现有 Milvus 向量检索、LangGraph 问答编排与 rerank 能力继续保留，LightRAG 作为图增强检索与知识图谱能力接入，Neo4j 用于承载正式图谱后端。

## 核心能力

- **认证与权限控制**
  - 用户注册、登录、Token 鉴权、当前用户资料查询
  - 基于 Django `User / Group / Permission` 的 RBAC 权限模型
  - 管理员用户管理、角色管理、角色分配与访问控制
- **金融知识库管理**
  - 支持 `txt / pdf / docx` 文档上传、解析、版本管理与数据集归类
  - 支持普通 chunk 与分层 section chunk
  - 支持 Milvus 向量化入库、文档状态跟踪与 chunk 检查
- **GraphRAG / LightRAG 增强**
  - LightRAG 负责实体抽取、关系抽取、图谱索引与图增强检索
  - Neo4j 负责实体关系图的持久化存储与图查询
  - Milvus 继续承担 chunk、entity、relation 等向量检索能力
  - 管理端提供 LightRAG 入口，用于图谱探索、图增强问答和入库调试
- **智能问答**
  - LangGraph 负责问题路由、查询重写、检索、相关性评估和回答上下文构建
  - 支持引用来源、会话历史、会话摘要、上下文过滤与记忆能力
  - 支持普通 RAG 与 LightRAG 图增强检索按场景组合
- **风险分析**
  - 从知识库文档中抽取公司、风险类型、风险等级、事件时间、证据文本和置信度
  - 支持风险事件审核、风险摘要和风险报告生成
- **LLM 中台**
  - 统一管理 chat、embedding、rerank 模型配置
  - 支持 LiteLLM Gateway、模型调用日志、路由观测、评测记录和微调任务管理
- **系统运维**
  - 健康检查、系统看板、审计日志、部署脚本和冒烟验证
  - 支持 Docker Compose 生产部署与本机脚本部署

## 技术栈

### 前端

- Vue 3
- Vue Router
- Vite
- JavaScript ES Modules
- Element Plus
- 自定义应用壳组件：`AppSidebar`、`AppTopbar`、`AppSectionCard`

### 后端

- Python
- Django 5
- Django REST Framework
- Django ORM
- Celery
- PyMySQL / MySQL 8
- Redis
- JWT 鉴权

### RAG 与模型能力

- Milvus / Milvus Lite：向量存储与相似度检索
- LightRAG：图增强 RAG、实体关系抽取、知识图谱检索
- Neo4j：实体关系图谱数据库
- LangGraph：问答流程编排
- LiteLLM Gateway：模型统一接入、路由与 fallback
- DeepSeek / DashScope / Ollama / OpenAI-compatible API：chat、embedding、rerank 后端
- PyMuPDF：PDF 文本块、页码和版面基础信息抽取
- 轻量解析服务：兼容 element 输出契约，承载 `pdf/docx/txt` 多格式解析入口

### 部署与基础设施

- Docker Compose
- Nginx
- MySQL
- Redis
- Milvus Standalone
- Etcd
- MinIO
- Neo4j
- Shell 部署脚本：`scripts/deploy.sh`、`scripts/smoke-check.sh`

## 项目结构

```text
finmodpro/
├─ frontend/                    # Vue 3 + Vite 前端
│  ├─ src/
│  │  ├─ api/                   # API 请求封装
│  │  ├─ components/            # 业务组件
│  │  ├─ components/ui/         # 通用 UI 壳组件
│  │  ├─ layouts/               # 管理端、工作区、认证布局
│  │  ├─ views/                 # 页面视图
│  │  ├─ lib/                   # 权限、会话、知识库、模型中台工具
│  │  └─ router/                # 前端路由
│  └─ public/
├─ backend/                     # Django 后端
│  ├─ authentication/           # 注册、登录、JWT 认证
│  ├─ rbac/                     # 用户、角色、权限管理
│  ├─ knowledgebase/            # 文档、数据集、入库任务、chunk
│  ├─ rag/                      # 检索 API 与检索日志
│  ├─ chat/                     # 会话、消息、记忆、问答编排
│  ├─ risk/                     # 风险事件、风险报告
│  ├─ llm/                      # 模型配置、评测、微调、调用日志
│  ├─ systemcheck/              # 健康检查、审计、看板统计
│  └─ config/                   # Django 配置、路由、Celery
├─ deploy/                      # 外部服务配置与轻量解析服务
├─ docs/                        # 项目文档
├─ scripts/                     # 部署、轮询、冒烟检查脚本
└─ docker-compose.prod.yml      # 生产部署编排
```

## 系统架构

```text
Vue 前端
  ├─ 工作区：智能问答、知识库、历史会话、风险与舆情
  └─ 管理端：看板、用户、知识库、模型中台、评测、LightRAG 图谱入口

Django API
  ├─ authentication / rbac
  ├─ knowledgebase：parse -> chunk -> vectorize -> index
  ├─ rag：Milvus 检索 + rerank
  ├─ chat：LangGraph 路由、重写、检索、引用、回答
  ├─ risk：风险抽取、审核、报告
  ├─ llm：模型配置、LiteLLM 同步、调用日志、评测、微调
  └─ systemcheck：健康检查、审计、统计

AI 与数据基础设施
  ├─ MySQL：业务数据
  ├─ Redis：缓存、Celery broker/result backend
  ├─ Milvus：向量索引
  ├─ LightRAG：图增强 RAG 服务
  ├─ Neo4j：知识图谱
  ├─ LiteLLM：模型网关
  └─ Parser Service：PyMuPDF PDF 解析与多格式 element 输出
```

## 主要模块

### 1. 用户与权限模块

用户通过认证接口登录系统，后端签发 JWT，前端保存访问令牌并在请求中携带。系统使用 Django 内置用户、用户组和权限模型实现 RBAC，管理员可以维护用户、角色与权限分配。

### 2. 知识库模块

知识库模块负责文档上传、解析、切块、入库、版本管理和检索调试。PDF 主解析由轻量解析服务内的 PyMuPDF 引擎完成，并保留统一 element 输出契约；文档解析后生成 `DocumentChunk` 或 `DocumentSectionChunk`，随后写入 Milvus。大型文档可使用分层 chunk 策略，先索引 section，再保留子 chunk 作为上下文细粒度证据。

### 3. LightRAG 图增强模块

LightRAG 在现有知识库基础上补充实体、关系和图谱索引。系统将解析后的文档内容同步给 LightRAG，由 LightRAG 生成实体关系图，并将图数据写入 Neo4j。查询阶段可同时使用向量召回和图关系扩展，提升跨文档、多跳关系和证据链分析能力。

### 4. 智能问答模块

聊天问答由 LangGraph 编排，流程包括问题路由、查询重写、检索、相关性评估和回答上下文构建。普通事实查询可走 Milvus RAG；涉及实体关系、跨文档链路、风险网络的问题可走 LightRAG 图增强检索。

### 5. 风险分析模块

风险模块基于知识库文档与模型抽取能力识别风险事件，保存公司名称、风险类型、等级、事件时间、证据文本、置信度与审核状态，并支持按公司或时间范围生成风险报告。

### 6. 模型中台模块

模型中台管理 chat、embedding、rerank 三类模型，支持不同 provider 的配置、启用状态、LiteLLM Gateway 同步、调用日志记录、模型评测和 LLaMA-Factory 微调任务跟踪。

## 数据库设计

完整数据库设计整理在：

- [docs/design/database-design.md](./docs/design/database-design.md)

当前核心设计文档统一收纳在：

- [docs/design/README.md](./docs/design/README.md)

核心业务表包括：

- `knowledgebase_dataset`
- `knowledgebase_document`
- `knowledgebase_documentversion`
- `knowledgebase_ingestiontask`
- `knowledgebase_documentchunk`
- `knowledgebase_documentsectionchunk`
- `rag_retrievallog`
- `chat_chatsession`
- `chat_chatmessage`
- `chat_memoryitem`
- `chat_memoryevidence`
- `chat_memoryactionlog`
- `risk_riskevent`
- `risk_riskreport`
- `llm_modelconfig`
- `llm_evalrecord`
- `llm_finetunerunnerserver`
- `llm_finetunerun`
- `llm_litellmsyncevent`
- `llm_modelinvocationlog`
- `systemcheck_auditrecord`
- Django 内置认证与权限表：`auth_user`、`auth_group`、`auth_permission` 等

LightRAG 与 Neo4j 图谱数据作为独立图存储管理，不直接写入 Django 业务表。FinModPro 通过文档 ID、数据集 ID、chunk 元数据和 LightRAG 文档状态建立业务数据与图谱索引之间的映射关系。

## 本地启动

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a
source .env
set +a
python manage.py migrate
python manage.py seed_rbac
python manage.py runserver 127.0.0.1:8000
```

后端默认地址：

```text
http://127.0.0.1:8000
```

### 前端

```bash
cd frontend
npm install
cp .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

前端默认地址：

```text
http://127.0.0.1:5173
```

### LightRAG / Neo4j

在完整集成形态下，LightRAG 作为独立服务运行，Neo4j 作为图后端运行。推荐通过反向代理暴露到管理端路径：

```text
/admin/lightrag
/admin/lightrag/api/*
```

LightRAG 需要配置模型、embedding、向量存储和图存储：

```env
LIGHTRAG_VECTOR_STORAGE=MilvusVectorDBStorage
LIGHTRAG_GRAPH_STORAGE=Neo4JStorage
LIGHTRAG_KV_STORAGE=JsonKVStorage
LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-password>
```

实际变量名以当前 LightRAG 版本和部署配置为准。

## 主要 API 范围

- `/api/health/`
- `/api/dashboard/stats`
- `/api/auth/...`
- `/api/admin/...`
- `/api/knowledgebase/...`
- `/api/rag/...`
- `/api/chat/...`
- `/api/risk/...`
- `/api/llm/...`
- `/api/ops/...`
- `/admin/lightrag/...`

## 测试

### 后端

```bash
cd backend
source .venv/bin/activate
python manage.py check
python manage.py test
```

### 前端

```bash
cd frontend
npm test
npm run build
```

## 部署

当前项目支持服务器本机脚本部署和 Docker Compose 部署。正常交付流程为：

```text
local change -> push -> pipeline/server pull -> scripts/deploy.sh -> smoke check
```

服务器本机部署：

```bash
./scripts/deploy.sh
./scripts/smoke-check.sh
```

生产部署涉及：

- frontend
- backend
- celery-worker
- mysql
- redis
- litellm
- unstructured-api（轻量解析服务，PDF 引擎为 PyMuPDF）
- milvus
- etcd
- minio
- lightrag
- neo4j

## 论文/报告章节材料

第二章到第七章的简短说明整理在：

- [docs/design/thesis-chapters-summary.md](./docs/design/thesis-chapters-summary.md)

可直接作为毕业设计、课程设计或项目报告的章节草稿继续扩写。

## 许可证

当前仓库未声明正式开源许可证。如需公开分发或商用，请先补充合适的 License 文件。
