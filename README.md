# FinModPro

FinModPro 是一个面向金融风控与金融知识管理场景的全栈智能分析系统。系统围绕"金融文档入库、向量检索、RAG 问答、风险事件抽取、情感分析、模型中台、权限治理与运维观测"构建，采用前后端分离与 Docker Compose 多服务部署架构。

RAG 层基于 **LlamaIndex + Milvus** 统一检索管线，支持向量检索与 BM25 关键词检索，并通过 embedding cache 加速重复查询。

## 核心能力

- **认证与权限控制**
  - 用户注册、登录、JWT Token 鉴权、当前用户资料查询
  - 基于 Django `User / Group / Permission` 的 RBAC 权限模型
  - 管理员用户管理、角色管理、角色分配与访问控制
- **金融知识库管理**
  - 支持 `txt / pdf / docx` 文档上传、解析、版本管理与数据集归类
  - 支持普通 chunk 与分层 section chunk
  - 支持 Milvus 向量化入库、文档状态跟踪与 chunk 检查
  - 内置文档清洗规则引擎（去空格、编码修复、去重、OCR 等 13 种规则）
- **智能问答**
  - LangGraph 负责问题路由、查询重写、检索、相关性评估和回答上下文构建
  - LlamaIndex 检索管线：向量检索（Milvus）+ BM25 关键词检索 + rerank
  - 支持引用来源、会话历史、滚动摘要、上下文过滤与长期记忆能力
  - 支持 SSE 流式回答
- **风险分析**
  - 从知识库文档中抽取公司、风险类型、风险等级、事件时间、证据文本和置信度
  - 支持风险事件审核、风险摘要和按公司/时间范围生成风险报告
  - 异步抽取管线，独立 Celery worker 队列
- **情感分析**
  - 对知识库文档进行 LLM 驱动的逐文档情感分类（正面/中性/负面）
  - 支持启发式关键词兜底，返回分布统计与置信度
- **LLM 中台**
  - 统一管理 chat、embedding、rerank 模型配置
  - 支持 DeepSeek / DashScope / Ollama / OpenAI-compatible 多 provider
  - 模型调用日志、成本分析、网关可观测性
  - 评测记录管理与 LLaMA-Factory 微调任务全生命周期管理
- **系统运维与监控**
  - 健康检查、系统看板、审计日志
  - 系统指标采集、告警规则管理、告警事件生命周期（firing / resolved / acknowledged）
  - 部署脚本和冒烟验证

## 技术栈

### 前端

- Vue 3 + Vue Router + Vite
- JavaScript ES Modules
- Element Plus + Iconify
- ECharts（图表）、marked + highlight.js（Markdown 渲染）、DOMPurify（XSS 防护）、SheetJS（导出）
- 自定义应用壳组件：`AppSidebar`、`AppTopbar`、`AppSectionCard`
- 两种视觉主题：工作区（暖羊皮纸色调）+ 管理端（深海军蓝色调）

### 后端

- Python 3.12 + Django 5 + Django REST Framework
- Celery（多队列：通用任务 `celery` + 风险抽取 `risk`）+ django-celery-beat
- PyMySQL / MySQL 8.4 + Redis 7
- JWT 鉴权（access token 内存存储 + refresh token HTTP-only cookie）

### RAG 与模型能力

- **LlamaIndex**：统一检索编排，向量检索 + BM25 混合检索
- **Milvus 2.5**：向量存储与相似度检索（standalone 模式）
- **LangGraph**：问答流程编排
- **PyMuPDF4LLM / pypdf**：PDF 文档解析
- **python-docx**：DOCX 文档解析
- DeepSeek / DashScope / OpenAI-compatible API：chat、embedding、rerank 后端

### 部署与基础设施

- Docker Compose（11 个服务 + 7 个命名卷）
- Nginx（前端静态服务 + `/api/` 反向代理）
- MySQL 8.4 + Redis 7-alpine
- Milvus Standalone + Etcd + MinIO
- Shell 部署脚本：`scripts/deploy.sh`、`scripts/smoke-check.sh`

## 项目结构

```text
finmodpro/
├─ frontend/                    # Vue 3 + Vite 前端
│  ├─ src/
│  │  ├─ api/                   # API 请求封装（14 个模块）
│  │  ├─ components/            # 业务组件
│  │  ├─ components/ui/         # 通用 UI 壳组件
│  │  ├─ layouts/               # 管理端、工作区、认证布局
│  │  ├─ views/                 # 页面视图（21 个页面）
│  │  ├─ lib/                   # 权限、会话、工具函数
│  │  └─ router/                # 前端路由与守卫
│  └─ public/
├─ backend/                     # Django 后端
│  ├─ authentication/           # 注册、登录、JWT 认证、密码重置
│  ├─ rbac/                     # 用户、角色、权限管理
│  ├─ knowledgebase/            # 文档、数据集、入库任务、chunk、清洗规则
│  ├─ rag/                      # 检索 API 与检索日志
│  ├─ chat/                     # 会话、消息、记忆、问答编排
│  ├─ risk/                     # 风险事件、风险报告、情感分析
│  ├─ llm/                      # 模型配置、评测、微调、网关可观测性
│  ├─ ops/                      # 系统指标、告警规则、告警事件
│  ├─ systemcheck/              # 健康检查、审计、看板统计
│  ├─ common/                   # 共享工具（响应格式、异常处理、日志、可观测性）
│  └─ config/                   # Django 配置、根路由、Celery、WSGI/ASGI
├─ deploy/                      # LLaMA-Factory runner agent
├─ docs/                        # 项目文档（设计文档、功能清单、部署指南等）
├─ scripts/                     # 部署、冒烟检查脚本
└─ docker-compose.prod.yml      # 生产部署编排
```

## 系统架构

```text
Vue 前端 (Nginx)
  ├─ 工作区：智能问答、知识库、历史会话、风险与舆情
  └─ 管理端：看板、用户、知识库、模型中台、评测、清洗规则、监控告警

Django API (gunicorn)
  ├─ authentication / rbac     — 认证与权限
  ├─ knowledgebase             — parse → clean → chunk → vectorize → index
  ├─ rag                       — LlamaIndex 混合检索（向量 + BM25）+ rerank
  ├─ chat                      — LangGraph 路由、重写、检索、引用、回答、记忆
  ├─ risk                      — 风险抽取、审核、报告、情感分析
  ├─ llm                       — 模型配置、多 provider、调用日志、评测、微调
  ├─ ops                       — 系统指标、告警规则、告警事件
  └─ systemcheck               — 健康检查、审计、统计

Celery Workers
  ├─ celery-worker             — 通用任务（文档解析、清洗、入库）
  └─ celery-worker-risk        — 风险抽取专用队列

数据与基础设施
  ├─ MySQL 8.4                 — 业务数据
  ├─ Redis 7                   — 缓存、Celery broker/result backend
  ├─ Milvus 2.5                — 向量索引（standalone）
  ├─ Etcd                      — Milvus 元数据
  └─ MinIO                     — Milvus 对象存储
```

## 主要模块

### 1. 用户与权限模块

用户通过认证接口登录系统，后端签发 JWT，前端保存访问令牌并在请求中携带。系统使用 Django 内置用户、用户组和权限模型实现 RBAC，管理员可以维护用户、角色与权限分配。

### 2. 知识库模块

知识库模块负责文档上传、解析、清洗、切块、入库、版本管理和检索调试。PDF 解析由 PyMuPDF4LLM / pypdf 完成；文档解析后生成 `DocumentChunk` 或 `DocumentSectionChunk`，随后写入 Milvus。大型文档可使用分层 chunk 策略，先索引 section，再保留子 chunk 作为上下文细粒度证据。内置清洗规则引擎支持空白清理、编码修复、引号/项目符号规范化、页眉页脚去除、MinHash 去重等 13 种规则。

### 3. 智能问答模块

聊天问答由 LangGraph 编排，流程包括问题路由、查询重写、检索、相关性评估和回答上下文构建。检索层基于 LlamaIndex 统一管线，支持 Milvus 向量检索与 BM25 关键词检索混合召回，并经 rerank 模型精排。系统支持会话滚动摘要、长期记忆存储与证据追溯，以及 SSE 流式回答。

### 4. 风险分析模块

风险模块基于知识库文档与模型抽取能力识别风险事件，保存公司名称、风险类型、等级、事件时间、证据文本、置信度与审核状态，并支持按公司或时间范围生成风险报告。异步抽取管线运行在独立 Celery worker 队列上，避免阻塞通用任务。

### 5. 情感分析模块

情感分析作为风险模块的子功能，支持对指定数据集或文档批量进行 LLM 驱动的情感分类（正面/中性/负面），并返回分布统计、逐文档标签及置信度。在 LLM 不可用时自动降级为关键词启发式分析。

### 6. 模型中台模块

模型中台管理 chat、embedding、rerank 三类模型，支持 DeepSeek、DashScope、Ollama、OpenAI-compatible 等多种 provider。提供模型配置 CRUD、启用状态切换、连接测试、调用日志与成本分析、网关可观测性、评测记录管理和 LLaMA-Factory 微调任务全生命周期管理。

### 7. 运维监控模块

`ops` 应用提供系统指标时间序列采集与查询、告警规则管理（支持 gt/lt/gte/lte/eq 五种比较条件，info/warning/critical 三级严重度）、告警事件生命周期管理（firing → acknowledged → resolved），支持预设默认告警规则。

## 数据库设计

完整数据库设计整理在：

- [docs/design/database-design.md](./docs/design/database-design.md)

当前核心设计文档统一收纳在：

- [docs/design/README.md](./docs/design/README.md)

核心业务表包括：

- `knowledgebase_dataset` / `knowledgebase_document` / `knowledgebase_documentversion`
- `knowledgebase_ingestiontask` / `knowledgebase_documentchunk` / `knowledgebase_documentsectionchunk`
- `knowledgebase_cleaningrule` / `knowledgebase_documentcleaningresult`
- `rag_retrievallog`
- `chat_chatsession` / `chat_chatmessage` / `chat_memoryitem` / `chat_memoryevidence` / `chat_memoryactionlog`
- `risk_riskevent` / `risk_riskreport` / `risk_riskextractiontask`
- `llm_modelconfig` / `llm_evalrecord` / `llm_finetunerunnerserver` / `llm_finetunerun` / `llm_modelinvocationlog`
- `ops_systemmetric` / `ops_alertrule` / `ops_alertevent`
- `systemcheck_auditrecord`
- Django 内置认证与权限表：`auth_user`、`auth_group`、`auth_permission` 等

## 本地启动

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a && source .env && set +a
python manage.py migrate
python manage.py seed_rbac
python manage.py runserver 127.0.0.1:8000
```

后端默认地址：`http://127.0.0.1:8000`

### 前端

```bash
cd frontend
npm install
cp .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

前端默认地址：`http://127.0.0.1:5173`

## 主要 API 范围

- `/api/health` — 健康检查
- `/api/dashboard/stats` — 看板统计
- `/api/auth/...` — 认证（注册、登录、刷新、登出、密码重置）
- `/api/auth/me` — 当前用户资料
- `/api/admin/...` — 管理端（用户、角色、权限）
- `/api/knowledgebase/...` — 知识库（数据集、文档、chunk、版本、入库、清洗规则）
- `/api/rag/...` — 检索
- `/api/chat/...` — 问答、会话、记忆
- `/api/risk/...` — 风险事件、报告、情感分析、文档抽取
- `/api/ops/...` — 模型中台（模型配置、网关可观测性、评测、微调）
- `/api/monitoring/...` — 系统监控（指标、告警规则、告警事件）

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

当前项目支持 Docker Compose 生产部署。正常交付流程为：

```text
local change → push → server pull → scripts/deploy.sh → smoke check
```

服务器部署：

```bash
./scripts/deploy.sh
./scripts/smoke-check.sh
```

Docker Compose 生产服务（`docker-compose.prod.yml`）：

| 服务 | 说明 |
|------|------|
| `frontend` | Nginx 静态服务 + `/api/` 反向代理 |
| `backend` | Django / gunicorn API 服务器 |
| `celery-worker` | 通用异步任务队列 |
| `celery-worker-risk` | 风险抽取专用队列 |
| `celery-beat` | 定时任务调度 |
| `mysql` | MySQL 8.4 关系数据库 |
| `redis` | Redis 7 缓存与消息队列 |
| `etcd` | Milvus 元数据存储 |
| `minio` | Milvus 对象存储 |
| `milvus` | Milvus 2.5 向量数据库 |

## 论文/报告章节材料

第二章到第七章的简短说明整理在：

- [docs/design/thesis-chapters-summary.md](./docs/design/thesis-chapters-summary.md)

可直接作为毕业设计、课程设计或项目报告的章节草稿继续扩写。

## 许可证

当前仓库未声明正式开源许可证。如需公开分发或商用，请先补充合适的 License 文件。
