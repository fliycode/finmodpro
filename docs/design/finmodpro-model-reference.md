# FinModPro 项目参考文档（专业模型版）

> 用途：供更专业的代码模型、架构模型或研究模型快速理解 `finmodpro` 当前真实实现。  
> 事实优先级：**代码 > 本文档 > 旧 README/历史说明**。

## 摘要

FinModPro 是一个面向金融风控、金融知识管理与模型运维的全栈系统，采用 Vue 3 + Vite 前端与 Django 5 + DRF 后端的前后端分离架构。系统核心围绕 **认证与 RBAC、知识库文档入库、RAG/图增强检索、金融问答、风险事件抽取、模型中台与运维观测** 展开，并通过 Docker Compose 连接 MySQL、Redis、Milvus、Neo4j、LiteLLM、LightRAG、MinIO、Etcd 等服务形成完整运行链路。

当前项目已经具备两类主要产品面：一类是面向金融分析师的 `/workspace` 工作区，用于问答、知识检索、风险与舆情分析；另一类是面向系统管理员的 `/admin` 管理台，用于数据看板、用户治理、模型路由、观测、成本、评测和 LightRAG 图谱管理。前端采用双壳结构，后端按 Django app 分域组织，模型与检索能力通过 LiteLLM、LangGraph、Milvus、LightRAG、Unstructured/PyPDF 等组件协同完成。

本文档重点不是“产品宣传”，而是帮助专业模型在接手新需求时，先理解当前代码边界、依赖拓扑、模块职责、协作约束与可信事实来源，避免被过时文档误导。

**关键词：** Vue 3，Django 5，金融风控，RAG，LightRAG，LiteLLM，Milvus，RBAC

## 第一章 前言

### 1.1 项目定位

FinModPro 的目标不是单点聊天工具，而是一个把 **金融文档治理、检索增强问答、风险抽取、模型配置与运维治理** 放到同一平台中的复合系统。它同时服务两类角色：

1. **金融分析师**：在工作区完成问答、文档检索、风险分析、舆情判断等任务。
2. **系统管理员 / 模型运营人员**：在管理台维护用户权限、知识库链路、模型配置、LiteLLM 网关、评测结果、成本与观测数据。

### 1.2 当前实现形态

当前仓库是单体 monorepo：

- `frontend/`：Vue 3 + Vite + Element Plus 管理/工作区前端
- `backend/`：Django 5 + DRF API 服务
- `deploy/`：LiteLLM、轻量解析服务等部署配置
- `docker-compose.prod.yml`：生产级多服务编排
- `scripts/`：部署与冒烟检查脚本

### 1.3 对专业模型的意义

如果专业模型要继续开发本项目，它不能把 FinModPro 当成“普通后台模板”或“单一 RAG demo”。它必须同时理解：

- 这是一个**双端壳**产品：`/workspace` 与 `/admin`
- 这是一个**多后端能力拼接**系统：业务 API、向量检索、图增强检索、模型网关、外部解析服务
- 这是一个**代码优先**项目：旧文档可能落后，尤其不能再假设默认 SQLite 或简单静态页面

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
- `systemcheck`

### 2.3 AI / RAG / 模型基础设施

| 能力 | 组件 |
| --- | --- |
| 向量存储 | Milvus / milvus-lite（开发兼容） |
| 问答编排 | LangGraph |
| 模型网关 | LiteLLM |
| 图增强检索 | LightRAG |
| 图存储 | 当前生产 compose 为 `Neo4JStorage`，并显式编排 Neo4j 服务；`settings.py` 在未注入环境变量时仍保留 `NetworkXStorage` 默认回退值 |
| 文档解析 | Unstructured API + `pypdf` fallback |
| 可观测性 | Langfuse（可选环境集成） |

### 2.4 部署与运行基础设施

生产编排由 `docker-compose.prod.yml` 驱动，核心服务包括：

- frontend（Nginx）
- backend（Gunicorn / Django）
- celery-worker
- mysql:8.4
- redis:7-alpine
- litellm
- unstructured-api
- etcd
- minio
- milvus standalone
- neo4j
- lightrag

需要特别注意：**当前生产 compose 已显式启用 Neo4j 服务，并将 LightRAG 图存储配置为 `Neo4JStorage`。** 同时，`backend/config/settings.py` 里仍保留 `LIGHTRAG_GRAPH_STORAGE=NetworkXStorage` 的默认值，因此在未注入部署环境变量的非生产场景中，仍可能退回本地图存储配置。

## 第三章 需求分析与整体功能

### 3.1 核心用户

#### 3.1.1 金融分析师

工作重点：

- 基于知识库进行智能问答
- 检索和管理金融文档
- 查看历史会话与上下文
- 进行风险与舆情分析

对应前端路由：

- `/workspace/qa`
- `/workspace/knowledge`
- `/workspace/history`
- `/workspace/profile`
- `/workspace/risk`
- `/workspace/sentiment`

#### 3.1.2 系统管理员 / 模型运营

工作重点：

- 查看平台总体运行状态
- 维护用户与角色权限
- 管理知识库与模型中台
- 查看成本、观测、评测
- 使用 LightRAG 图谱检索与治理能力

对应前端路由：

- `/admin/overview`
- `/admin/users`
- `/admin/knowledge`
- `/admin/llm`
- `/admin/llm/models`
- `/admin/llm/observability`
- `/admin/llm/costs`
- `/admin/llm/knowledge`
- `/admin/lightrag/*`
- `/admin/evaluation`

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
- `txt / pdf / docx` 解析入口
- chunk 元数据、页码、element 类型等结构化输出

#### 3.2.3 RAG 与聊天问答

- 普通问答接口
- SSE 流式问答接口
- 检索结果引用回传
- 会话创建、详情、导出
- 会话记忆列表、证据查看、置顶、删除
- 问答链路中的检索日志记录

#### 3.2.4 风险分析

- 风险分析总览
- 风险事件列表
- 风险事件审核
- 单文档 / 批量文档风险抽取与重试
- 公司维度与时间区间维度的风险报告生成
- 舆情分析接口

#### 3.2.5 LLM 中台与运维

- 模型配置列表、详情、激活、连接测试、LiteLLM 同步
- Prompt 配置列表与更新
- 网关 summary / logs / traces / errors / costs
- 评测记录
- 微调 runner server / fine-tune run / dispatch / callback / export
- LightRAG 概览与代理访问

#### 3.2.6 系统健康与审计

- 健康检查
- 数据看板统计
- 审计日志

### 3.3 非功能性要求

从当前代码可以推断出的非功能要求包括：

- **权限边界清晰**：前端通过 `meta.requiresAuth` / `meta.requiresAdmin` 控制路由，后端继续做真实鉴权
- **部署可编排**：生产方案依赖 Docker Compose 与本地脚本
- **接口兼容性**：已有 Django URL 模块普遍保留带斜杠与不带斜杠写法，不能随意删减
- **文档解析要容错**：PDF 首选 Unstructured，失败后允许 `pypdf` fallback
- **模型链路可观测**：LiteLLM、Langfuse、检索日志、评测记录等构成可追踪运行面

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
│  ├─ rag/                     # 检索
│  ├─ chat/                    # 聊天与记忆
│  ├─ risk/                    # 风险与报告
│  ├─ llm/                     # 模型中台 / LightRAG / 评测 / 微调
│  ├─ systemcheck/             # 健康 / 看板 / 审计
│  └─ config/                  # settings / urls / celery
├─ deploy/                     # LiteLLM 与解析服务配置
├─ docs/                       # 项目与设计文档
├─ scripts/                    # deploy / smoke check
└─ docker-compose.prod.yml     # 生产编排
```

### 4.2 前端架构设计

前端不是“一个 dashboard”，而是两个互相一致但视觉与任务不同的壳：

1. **Workspace**：面向分析工作流，入口偏知识消费与分析执行
2. **Admin**：面向治理与运维，入口偏配置、监控与审阅

认证设计采用：

- access token **只保存在内存**
- refresh token 由后端放入 HTTP-only cookie
- 前端请求 401 后自动尝试一次 refresh
- refresh 失败后清理本地态并跳回 `/login`

这意味着后续改动不能随意改成“长期 localStorage token 方案”，否则会破坏现有安全模型。

### 4.3 后端模块设计

后端总路由由 `backend/config/urls.py` 统一挂载：

- `/api/auth/` → `authentication`
- `/api/` + `/api/systemcheck/` → `systemcheck`
- `/api/` → `rbac`
- `/api/knowledgebase/` → `knowledgebase`
- `/api/ops/` → `llm`
- `/api/rag/` → `rag`
- `/api/chat/` → `chat`
- `/api/risk/` → `risk`

各模块职责：

| 模块 | 职责 |
| --- | --- |
| authentication | 登录、注册、刷新、退出、CSRF |
| rbac | 当前用户信息、后台用户/角色组维护 |
| knowledgebase | 数据集、文档、版本、chunk、ingest |
| rag | 检索 API |
| chat | 问答、流式问答、会话、记忆 |
| risk | 风险事件、审核、报告、舆情 |
| llm | 模型配置、LiteLLM 网关、Prompt 配置、评测、微调、LightRAG 代理 |
| systemcheck | 健康、统计、审计 |

### 4.4 文档与问答链路设计

当前主链路可以概括为：

```text
上传文档
  -> 解析（Unstructured / pypdf fallback）
  -> 结构化文本与 metadata
  -> chunk / section chunk
  -> Milvus 向量入库
  -> RAG 检索
  -> LangGraph 组织问答上下文
  -> LLM 生成回答
  -> 返回 citations / answer_notice / duration
```

并行存在的图增强链路为：

```text
文档 / 图谱数据
  -> LightRAG
  -> Neo4j 图存储
  -> 图增强检索 / 图谱浏览 / 文档管线治理
  -> 通过后端 /api/ops/lightrag* 暴露给管理台
```

按当前 `docker-compose.prod.yml`，LightRAG 的图存储已经切换为 `Neo4JStorage`，向量存储为 Milvus。若描述本地默认配置，则需要额外注明 `settings.py` 在未覆盖环境变量时仍保留 `NetworkXStorage` 回退值。

### 4.5 风险链路设计

风险能力建立在知识文档和模型抽取基础上：

```text
知识文档
  -> 风险抽取
  -> 风险事件列表
  -> 人工审核
  -> 公司 / 时间区间报告生成
  -> 导出
```

### 4.6 部署拓扑设计

生产环境中，前端容器通过 Nginx 对外提供页面，并把 `/api/` 反代到后端容器。后端依赖：

- MySQL：业务数据
- Redis：缓存与 Celery broker/result backend
- Milvus：向量检索
- Neo4j：图谱节点、关系边与图查询后端
- LiteLLM：统一模型入口
- Unstructured API：文档解析
- LightRAG：图增强检索与图谱工作流
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
| 模型中台 / LightRAG | `backend/llm/urls.py`, `backend/llm/controllers/lightrag_controller.py` |

## 第六章 面向专业模型的协作约束

### 6.1 事实判断原则

- 当 README、历史清单、旧方案和代码冲突时，以代码为准
- 当同一能力同时涉及前端和后端时，必须双向核对，不能只改一侧
- 当接口路径已经对外暴露时，要优先兼容已有调用方

### 6.2 实施原则

1. 先读路由、设置、依赖，再动实现
2. 优先复用现有 service、controller、layout、UI 原语
3. 不要用看似“更现代”的改法破坏当前系统边界
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

FinModPro 当前已经形成了一个较完整的金融风控智能平台骨架，特点不是“某一个 AI 能力”，而是把 **知识治理、问答、风险分析、模型中台和运维观测** 放在同一项目内协同运行。对于更专业的模型来说，最重要的不是重新发明架构，而是先承认并理解现有系统的真实边界：

- 前端是双壳、双角色产品
- 后端是多 app 分域系统
- MySQL / Redis / Milvus / Neo4j / LiteLLM / LightRAG / Unstructured 共同构成运行底座
- 安全、兼容性与运维可观测性比“快速改出一个页面”更重要

只要模型先吃透本文档列出的事实来源和约束，再进入具体实现，它就能更稳定地在本项目上继续迭代，而不会被过期认知带偏。
