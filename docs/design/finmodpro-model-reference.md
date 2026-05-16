# FinModPro 项目参考文档（专业模型版）

> 用途：供更专业的代码模型、架构模型或研究模型快速理解 `finmodpro` 当前真实实现。
> 事实优先级：**代码 > 本文档 > 旧 README/历史说明**。

## 摘要

FinModPro 是一个面向金融风控、金融知识管理与模型运维的全栈系统，采用 Vue 3 + Vite 前端与 Django 5 + DRF 后端的前后端分离架构。系统核心围绕 **认证与 RBAC、知识库文档入库、RAG（LlamaIndex-over-Milvus）检索增强、金融问答、风险事件抽取、模型中台与运维观测** 展开，并通过 Docker Compose 连接 MySQL、Redis、Milvus、MinIO、Etcd 等服务形成完整运行链路。

当前项目已经具备两类主要产品面：一类是面向金融分析师的 `/workspace` 工作区，用于问答、知识检索、风险分析；另一类是面向系统管理员的 `/admin` 管理台，用于数据看板、用户治理、模型管理、观测、成本、评测和系统监控。前端采用双壳结构，后端按 Django app 分域组织，模型调用通过 OpenAI 兼容 provider 直连，检索层通过 LlamaIndex 统一抽象。

本文档重点不是"产品宣传"，而是帮助专业模型在接手新需求时，先理解当前代码边界、依赖拓扑、模块职责、协作约束与可信事实来源，避免被过时文档误导。

**关键词：** Vue 3，Django 5，金融风控，RAG，LlamaIndex，Milvus，RBAC

## 第一章 前言

### 1.1 项目定位

FinModPro 的目标不是单点聊天工具，而是一个把 **金融文档治理、检索增强问答、风险抽取、模型配置与运维治理** 放到同一平台中的复合系统。它同时服务两类角色：

1. **金融分析师**：在工作区完成问答、文档检索、风险分析等任务。
2. **系统管理员 / 模型运营人员**：在管理台维护用户权限、知识库链路、模型配置、评测结果、成本与观测数据。

### 1.2 当前实现形态

当前仓库是单体 monorepo：

- `frontend/`：Vue 3 + Vite + Element Plus 管理/工作区前端
- `backend/`：Django 5 + DRF API 服务
- `docker-compose.prod.yml`：生产级多服务编排
- `scripts/`：部署与冒烟检查脚本

### 1.3 对专业模型的意义

如果专业模型要继续开发本项目，它不能把 FinModPro 当成"普通后台模板"或"单一 RAG demo"。它必须同时理解：

- 这是一个**双端壳**产品：`/workspace` 与 `/admin`
- 这是一个**多后端能力拼接**系统：业务 API、向量检索、模型调用
- 这是一个**代码优先**项目：旧文档可能落后，尤其不能再假设默认 SQLite 或存在已移除的 LiteLLM/LightRAG/Neo4j

## 第二章 相关技术与技术栈

### 2.1 前端技术栈

| 类别 | 技术 |
| --- | --- |
| 核心框架 | Vue 3 |
| 构建工具 | Vite 8 |
| 路由 | Vue Router 4 |
| UI 组件 | Element Plus |
| 图表 | ECharts |
| 图标 | Iconify |
| 语言 | JavaScript ES Modules |

前端结构采用两套共享壳：

- `WorkspaceLayout.vue`：分析师工作区
- `AdminLayout.vue`：管理员控制台

共享 UI 原语强调复用而非重造，包括：

- `AppSidebar`
- `AppTopbar`
- `AppSectionCard`

### 2.2 后端技术栈

| 类别 | 技术 |
| --- | --- |
| Web 框架 | Django 5 |
| API 层 | Django REST Framework |
| 鉴权 | 自定义 JWT + refresh cookie 流程 |
| 异步任务 | Celery |
| 数据库 | MySQL 8 / PyMySQL |
| 缓存与消息 | Redis |
| 应用组织 | Django app + controllers/services 模式 |

后端 app 主要包括：

- `authentication`
- `rbac`
- `knowledgebase`
- `rag`
- `chat`
- `risk`
- `llm`
- `ops`
- `systemcheck`

### 2.3 AI / RAG / 模型基础设施

| 能力 | 组件 |
| --- | --- |
| 向量存储 | Milvus（通过 LlamaIndex 抽象层） |
| 检索抽象 | LlamaIndex（`llama-index-core`、`llama-index-vector-stores-milvus`） |
| 问答编排 | LangGraph |
| 嵌入缓存 | Django cache（Redis 24h TTL） |
| 重排序 | DashScope Rerank |
| 文档解析 | pymupdf4llm（PDF 主路径）+ pypdf fallback + python-docx（DOCX） |
| Chat Provider | DeepSeek、Ollama、OpenAI 兼容（直连，无中间网关） |
| Embedding Provider | DashScope、Ollama |
| Rerank Provider | DashScope |

### 2.4 部署与运行基础设施

生产编排由 `docker-compose.prod.yml` 驱动，核心服务包括：

- frontend（Nginx）
- backend（Gunicorn / Django）
- celery-worker
- celery-worker-risk
- celery-beat
- mysql:8.4
- redis:7-alpine
- etcd
- minio
- milvus standalone

## 第三章 需求分析与整体功能

### 3.1 核心用户

#### 3.1.1 金融分析师

工作重点：

- 基于知识库进行智能问答
- 检索和管理金融文档
- 查看历史会话与上下文
- 进行风险分析

对应前端路由：

- `/workspace/qa`
- `/workspace/knowledge`
- `/workspace/knowledge/documents/:id`
- `/workspace/history`
- `/workspace/risk`
- `/workspace/profile`

#### 3.1.2 系统管理员 / 模型运营

工作重点：

- 查看平台总体运行状态
- 维护用户与角色权限
- 管理知识库与模型中台
- 查看成本、观测、评测
- 系统监控与告警管理

对应前端路由：

- `/admin/overview`
- `/admin/users`
- `/admin/roles`
- `/admin/knowledge`
- `/admin/llm/models`
- `/admin/llm/logs`
- `/admin/llm/usage`
- `/admin/llm/knowledge`
- `/admin/monitoring`
- `/admin/notifications`
- `/admin/cleaning`
- `/admin/audit-logs`

### 3.2 已落地的整体功能

#### 3.2.1 认证与权限控制

- 用户注册、登录、退出
- refresh token cookie 刷新 access token
- 当前用户资料查询 `GET /api/auth/me`
- 基于 Django `Group / Permission` 的 RBAC
- 管理台用户与角色组维护

#### 3.2.2 知识库文档治理

- 数据集列表与详情
- 文档上传、详情、版本、chunk 查看
- 单文档/批量文档 ingest
- `txt / pdf / docx` 解析
- chunk 元数据、页码、element 类型等结构化输出

#### 3.2.3 RAG 与聊天问答

- 普通问答接口
- SSE 流式问答接口
- 检索结果引用回传
- 会话创建、详情、导出、删除
- 会话记忆列表、证据查看
- 问答链路中的检索日志记录

#### 3.2.4 风险分析

- 风险分析总览
- 风险事件列表
- 风险事件审核
- 单文档 / 批量文档风险抽取
- 公司维度与时间区间维度的风险报告生成
- 报告导出（xlsx）
- 情感分析 API

#### 3.2.5 LLM 中台与运维

- 模型配置列表、详情、激活、连接测试
- Prompt 配置列表与更新
- 网关日志 / traces / errors / costs
- 评测记录
- 微调 runner server / fine-tune run / dispatch / callback / export
- 系统监控与告警

#### 3.2.6 系统健康与审计

- 健康检查
- 数据看板统计
- 审计日志
- 系统指标监控

### 3.3 非功能性要求

从当前代码可以推断出的非功能要求包括：

- **权限边界清晰**：前端通过 `meta.requiresAuth` / `meta.requiresAdmin` 控制路由，后端继续做真实鉴权
- **部署可编排**：生产方案依赖 Docker Compose 与本地脚本
- **接口兼容性**：已有 Django URL 模块普遍保留带斜杠与不带斜杠写法，不能随意删减
- **文档解析要容错**：PDF 主路径由 pymupdf4llm 承担，服务失败时回退到 `pypdf`
- **模型链路可观测**：检索日志、模型调用日志、评测记录、系统指标等构成可追踪运行面

## 第四章 系统设计

### 4.1 仓库结构设计

```text
finmodpro/
├─ frontend/                   # Vue 3 + Vite 前端
│  └─ src/
│     ├─ api/                  # API 包装
│     ├─ components/           # 业务组件与 UI 组件
│     ├─ layouts/              # Auth / Workspace / Admin 壳
│     ├─ lib/                  # 会话、权限、状态工具
│     ├─ router/               # 路由与访问守卫
│     └─ views/                # 页面视图
├─ backend/                    # Django API
│  ├─ authentication/          # 认证
│  ├─ rbac/                    # 角色权限
│  ├─ knowledgebase/           # 文档与入库
│  ├─ rag/                     # 检索（LlamaIndex）
│  ├─ chat/                    # 聊天与记忆
│  ├─ risk/                    # 风险与报告
│  ├─ llm/                     # 模型中台 / 评测 / 微调
│  ├─ ops/                     # 运维监控与告警
│  ├─ systemcheck/             # 健康 / 看板 / 审计
│  └─ config/                  # settings / urls / celery
├─ docs/                       # 项目与设计文档
├─ scripts/                    # deploy / smoke check
└─ docker-compose.prod.yml     # 生产编排
```

### 4.2 前端架构设计

前端不是"一个 dashboard"，而是两个互相一致但视觉与任务不同的壳：

1. **Workspace**：面向分析工作流，入口偏知识消费与分析执行
2. **Admin**：面向治理与运维，入口偏配置、监控与审阅

认证设计采用：

- access token **只保存在内存**
- refresh token 由后端放入 HTTP-only cookie
- 前端请求 401 后自动尝试一次 refresh
- refresh 失败后清理本地态并跳回 `/login`

这意味着后续改动不能随意改成"长期 localStorage token 方案"，否则会破坏现有安全模型。

### 4.3 后端模块设计

后端总路由由 `backend/config/urls.py` 统一挂载：

- `/api/auth/` → `authentication`
- `/api/` + `/api/systemcheck/` → `systemcheck`
- `/api/` → `rbac`
- `/api/knowledgebase/` → `knowledgebase`
- `/api/ops/` → `llm`、`ops`
- `/api/rag/` → `rag`
- `/api/chat/` → `chat`
- `/api/risk/` → `risk`

各模块职责：

| 模块 | 职责 |
| --- | --- |
| authentication | 登录、注册、刷新、退出 |
| rbac | 当前用户信息、后台用户/角色组维护 |
| knowledgebase | 数据集、文档、版本、chunk、ingest、清洗 |
| rag | 检索 API（LlamaIndex-over-Milvus） |
| chat | 问答、流式问答、会话、记忆 |
| risk | 风险事件、审核、报告、情感分析 |
| llm | 模型配置、Prompt 配置、评测、微调 |
| ops | 系统监控、告警管理、指标收集 |
| systemcheck | 健康、统计、审计 |

### 4.4 文档与问答链路设计

当前主链路可以概括为：

```text
上传文档
  -> 解析（pymupdf4llm / pypdf fallback / python-docx）
  -> 结构化文本与 metadata
  -> chunk / section chunk
  -> Milvus 向量入库（通过 LlamaIndex 适配器）
  -> RAG 检索（混合检索：MySQL 全文 + 关键词回退 + RRF 融合）
  -> LangGraph 组织问答上下文
  -> LLM 生成回答
  -> 返回 citations / answer_notice / duration
```

### 4.5 风险链路设计

风险能力建立在知识文档和模型抽取基础上：

```text
知识文档
  -> 风险抽取（结构化输出 + 裁决丰富 + 验证）
  -> 风险事件列表
  -> 人工审核
  -> 公司 / 时间区间报告生成
  -> 导出（xlsx）
```

### 4.6 部署拓扑设计

生产环境中，前端容器通过 Nginx 对外提供页面，并把 `/api/` 反代到后端容器。后端依赖：

- MySQL：业务数据
- Redis：缓存与 Celery broker/result backend
- Milvus：向量检索
- Etcd + MinIO：Milvus standalone 依赖

## 第五章 当前实现映射

### 5.1 关键前端事实

- 真实前端依赖在 `frontend/package.json`
- 真实业务入口在 `frontend/src/router/routes.js`
- 鉴权存储在 `frontend/src/lib/auth-storage.js`
- 会话刷新逻辑在 `frontend/src/lib/auth-session.js`
- API 重试与 401 处理在 `frontend/src/api/config.js`

### 5.2 关键后端事实

- 真实依赖在 `backend/requirements.txt`
- 真实运行约束在 `backend/config/settings.py`
- 真实接口挂载在 `backend/config/urls.py`
- 业务域接口分别位于各 app 的 `urls.py`

### 5.3 当前必须牢记的实现约束

1. **数据库以代码为准是 MySQL-only。** `settings.py` 会在 `DB_ENGINE != mysql` 时直接报错。
2. **不要假设 `.env` 自动加载。** Django 读取的是 shell 环境变量。
3. **不要删掉 URL 的双写兼容。** `llm/urls.py` 等处明确保留带斜杠与不带斜杠路径。
4. **不要打破双壳 UI 模式。** 新页面应沿用现有 shell 原语，而不是再造第三套顶层布局。
5. **不要把 token 长期持久化到浏览器。** 现有前端 access token 为内存态，refresh 依赖 cookie。

### 5.4 建议专业模型优先阅读的文件

| 目标 | 文件 |
| --- | --- |
| 技术栈与依赖 | `frontend/package.json`, `backend/requirements.txt`, `docker-compose.prod.yml` |
| 前端路由与页面地图 | `frontend/src/router/routes.js` |
| 认证链路 | `frontend/src/lib/auth-storage.js`, `frontend/src/lib/auth-session.js`, `frontend/src/api/config.js`, `backend/authentication/urls.py`, `backend/rbac/urls.py` |
| 后端总边界 | `backend/config/settings.py`, `backend/config/urls.py` |
| 知识库入库 | `backend/knowledgebase/urls.py`, `backend/knowledgebase/services/parser_service.py` |
| 问答与记忆 | `backend/chat/urls.py`, `backend/chat/services/ask_service.py` |
| 风险模块 | `backend/risk/urls.py` |
| 模型中台 | `backend/llm/urls.py` |
| RAG 检索 | `backend/rag/services/llamaindex_store_service.py` |

## 第六章 面向专业模型的协作约束

### 6.1 事实判断原则

- 当 README、历史清单、旧方案和代码冲突时，以代码为准
- 当同一能力同时涉及前端和后端时，必须双向核对，不能只改一侧
- 当接口路径已经对外暴露时，要优先兼容已有调用方

### 6.2 实施原则

1. 先读路由、设置、依赖，再动实现
2. 优先复用现有 service、controller、layout、UI 原语
3. 不要用看似"更现代"的改法破坏当前系统边界
4. 任何关于模型、检索、权限、部署的改动，都要检查跨模块影响

### 6.3 常用命令

#### 前端

```bash
cd frontend
npm install
npm test
npm run build
```

#### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a
source .env
set +a
python manage.py check
python manage.py test
```

#### 部署

```bash
./scripts/deploy.sh
./scripts/smoke-check.sh
```

## 第七章 总结

FinModPro 当前已经形成了一个较完整的金融风控智能平台骨架，特点不是"某一个 AI 能力"，而是把 **知识治理、问答、风险分析、模型中台和运维观测** 放在同一项目内协同运行。对于更专业的模型来说，最重要的不是重新发明架构，而是先承认并理解现有系统的真实边界：

- 前端是双壳、双角色产品
- 后端是多 app 分域系统
- MySQL / Redis / Milvus 共同构成运行底座
- LlamaIndex 抽象检索层，LangGraph 编排问答
- 安全、兼容性与运维可观测性比"快速改出一个页面"更重要

只要模型先吃透本文档列出的事实来源和约束，再进入具体实现，它就能更稳定地在本项目上继续迭代，而不会被过期认知带偏。
