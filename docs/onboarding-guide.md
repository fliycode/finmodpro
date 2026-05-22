# FinModPro 快速上手指南

本文档面向有 Java/Spring 背景、熟悉 Redis 和 Python 语法，但未系统学过 Django 的开发者。目标是用最短时间理清项目结构、各文件职责、API 分布和数据流向。

## 目录

1. [Django 速通：用 Spring 概念对照理解](#1-django-速通用-spring-概念对照理解)
2. [项目全景架构](#2-项目全景架构)
3. [后端模块详解](#3-后端模块详解)
   - [config — Django 项目配置](#31-config--django-项目配置)
   - [common — 共享基础设施](#32-common--共享基础设施)
   - [authentication — 认证模块](#33-authentication--认证模块)
   - [rbac — 权限模块](#34-rbac--权限模块)
   - [knowledgebase — 知识库模块](#35-knowledgebase--知识库模块)
   - [rag — 检索模块](#36-rag--检索模块)
   - [chat — 问答模块](#37-chat--问答模块)
   - [risk — 风险分析模块](#38-risk--风险分析模块)
   - [llm — 模型中台模块](#39-llm--模型中台模块)
   - [ops — 运维监控模块](#310-ops--运维监控模块)
   - [systemcheck — 健康检查与审计](#311-systemcheck--健康检查与审计)
4. [前端模块详解](#4-前端模块详解)
5. [API 速查表](#5-api-速查表)
6. [数据流全景图](#6-数据流全景图)

---

## 1. Django 速通：用 Spring 概念对照理解

如果你熟悉 Spring Boot，下面这张表可以帮你快速映射 Django 概念：

| Spring 概念 | Django 对应 | 说明 |
|------------|------------|------|
| `@RestController` | `controllers/` 目录下的函数 | Django 用的是函数视图（FBV），不是类 |
| `@Service` | `services/` 目录下的类/函数 | 纯 Python 业务逻辑 |
| `@Entity` + `@Table` | `models.py` 中的 Model 类 | ORM 模型，继承 `models.Model` |
| `@Repository` / JPA | `Model.objects.filter()` | Django ORM 查询，不需要单独写 DAO |
| `application.yml` | `config/settings.py` | 所有配置集中在一个文件 |
| `@RequestMapping` | `urls.py` | URL 路由配置，每个 app 有自己的 urls.py |
| `@Bean` / `@Component` | 不需要 | Python 模块即单例，不需要 DI 容器 |
| Spring Security Filter Chain | `MIDDLEWARE` | 请求/响应处理管道 |
| `@Scheduled` | Celery Beat | 定时任务调度 |
| `@Async` / RabbitMQ | Celery | 异步任务队列 |
| JPA migrations (Flyway/Liquibase) | Django migrations | 数据库 schema 迁移，自动生成 |
| `pom.xml` | `requirements.txt` | 项目依赖声明 |
| `application-{profile}.yml` | `.env` 文件 | 环境变量，通过 `source .env` 加载 |

### Django 项目 vs Django App

```
finmodpro/backend/          ← Django 项目（相当于 Spring Boot 项目根目录）
  config/                   ← 项目级配置（settings, 根路由, celery 配置）
  authentication/           ← Django App（相当于一个微服务子模块）
  knowledgebase/            ← Django App
  chat/                     ← Django App
  ...
```

每个 Django App 是一个功能模块，有自己的 models / controllers / services / urls。这和 Spring 中按包组织 Controller / Service / Repository 不同 —— Django 是按**业务领域**垂直切分的。

### 请求处理流程

```
HTTP 请求
  → Nginx（生产环境，开发时直接到 Django）
    → MIDDLEWARE 管道（CORS → 认证 → 权限检查 → ...）
      → urls.py 路由匹配
        → controllers/ 中的视图函数（解析请求参数）
          → services/ 中的业务逻辑（核心计算）
            → models.py 中的 ORM 查询（数据库读写）
          ← 返回数据
        ← DRF Response 序列化为 JSON
      ← 响应
    ← HTTP 响应
```

Django 没有 Spring 的 `DispatcherServlet` 和 `HandlerMapping`，但其 urlpatterns 列表起到了同样的作用：逐一匹配 URL pattern，命中后调用对应的视图函数。

### Django REST Framework (DRF)

DRF 之于 Django，相当于 Spring Web 之于 Spring Boot——它提供了将 Python 函数/类变成 REST API 端点的一切：

- **`@api_view(['GET', 'POST'])`** — 等价于 `@GetMapping` / `@PostMapping`
- **`Response(data)`** — 等价于 `ResponseEntity<T>`
- **`status=201`** — 等价于 HTTP status 常量
- **`permission_classes`** — 等价于 `@PreAuthorize`
- **Serializers** — 等价于 Jackson 的序列化/反序列化 + Bean Validation

---

## 2. 项目全景架构

```text
┌─────────────────────────────────────────────────────────────┐
│                     Vue 3 前端 (Nginx)                       │
│  /workspace/*  (工作区-暖色)    /admin/*  (管理端-深海军蓝)    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + JWT Bearer Token
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               Django REST API (gunicorn :8000)               │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  auth    │ │  rbac    │ │knowledge │ │   rag    │       │
│  │ 注册/登录│ │ 用户/角色│ │base 文档 │ │ 检索API  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │   chat   │ │   risk   │ │   llm    │ │   ops    │       │
│  │LangGraph │ │ 风险/情感│ │ 模型/微调│ │ 监控/告警│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐                                               │
│  │systemchk │  健康/看板/审计                                │
│  └──────────┘                                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐ ┌──────────┐ ┌──────────┐
        │ MySQL   │ │  Redis   │ │  Milvus  │
        │ 8.4     │ │  7       │ │  2.5     │
        │ 业务数据 │ │ 缓存/队列│ │ 向量检索 │
        └─────────┘ └──────────┘ └──────────┘
              │                         │
              ▼                         ▼
        ┌──────────┐             ┌──────────┐
        │  Celery  │             │  Etcd    │
        │  异步任务│             │  元数据  │
        └──────────┘             └──────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │  MinIO   │
                                 │ 对象存储 │
                                 └──────────┘
```

### 各模块一句话职责

| 模块 | 一句话 |
|------|--------|
| **authentication** | 注册、登录、JWT 签发与验证、密码重置 |
| **rbac** | 用户 CRUD、角色 CRUD、权限分配、个人资料 |
| **knowledgebase** | 文档上传、解析(pdf/docx/txt)、清洗、分块、向量化入库 |
| **rag** | 基于 LlamaIndex+Milvus 的混合检索（向量+BM25+rerank） |
| **chat** | LangGraph 编排的 RAG 问答、会话管理、长期记忆 |
| **risk** | 从文档抽取风险事件、风险报告生成、情感分析 |
| **llm** | 模型配置管理(chat/embedding/rerank)、调用日志、评测、微调 |
| **ops** | 系统指标采集、告警规则、告警事件生命周期 |
| **systemcheck** | 健康检查、Dashboard 统计、审计日志 |

---

## 3. 后端模块详解

### 3.1 config — Django 项目配置

**位置：** `backend/config/`

**核心文件：**

| 文件 | 作用 | Java 类比 |
|------|------|----------|
| `settings.py` | 全部配置：DB/Redis/Celery/JWT/DRF/日志 | `application.yml` |
| `urls.py` | 根路由表，把 `/api/xxx` 分发给各 app | `@RequestMapping` 根路径 |
| `celery.py` | Celery 实例创建，自动发现各 app 的 tasks.py | `@EnableAsync` + RabbitMQ config |
| `env.py` | 环境变量读取工具函数 | `@Value` / `Environment` |
| `wsgi.py` | 生产环境 WSGI 入口 | `Application.main()` |
| `manage.py` | Django CLI 入口（migrate/runserver/shell/test） | `./gradlew` / `mvnw` |

**关键配置要点（settings.py）：**

```python
# INSTALLED_APPS = 注册的 Django App（类似 Spring 的 @ComponentScan 包列表）
# MIDDLEWARE = 请求管道（类似 Filter Chain）
# DATABASES = MySQL 连接（类似 spring.datasource.*）
# REST_FRAMEWORK = DRF 配置：
#   - 认证后端：自定义 JWT（HMAC-SHA256）
#   - 默认权限：IsAuthenticated
#   - 异常处理：统一 {code, message, data} 信封
# CELERY = 两个队列：celery（通用）、risk（风险抽取）
```

**URL 路由表（config/urls.py）：**

```python
urlpatterns = [
    path("api/auth/",         include("authentication.urls")),
    path("api/",              include("rbac.urls")),           # auth/me, admin/users, admin/roles
    path("api/knowledgebase/",include("knowledgebase.urls")),
    path("api/rag/",          include("rag.urls")),
    path("api/chat/",         include("chat.urls")),
    path("api/risk/",         include("risk.urls")),
    path("api/ops/",          include("llm.urls")),            # 注意：llm app 挂载在 /api/ops/
    path("api/monitoring/",   include("ops.urls")),
    path("api/systemcheck/",  include("systemcheck.urls")),
]
```

---

### 3.2 common — 共享基础设施

**位置：** `backend/common/`（不是 Django App，是工具包）

| 文件 | 作用 |
|------|------|
| `api_response.py` | 统一响应格式 `{code, message, data}`，提供 `success_response()` / `error_response()` |
| `drf_exception_handler.py` | 全局异常处理，把 DRF 异常转换为统一信封格式 |
| `exceptions.py` | 自定义异常类：`UpstreamServiceError`、`ModelNotConfiguredError`、`DuplicateDocumentError` 等 |
| `logging.py` | 结构化 JSON 日志格式化器 |
| `background_jobs.py` | `run_background_job()` — 在请求线程外执行任务（请求不需要等待完成） |
| `observability.py` | 分布式追踪占位（`trace_span` context manager） |

**响应格式约定：**

```json
// 成功
{"code": 200, "message": "success", "data": {...}}

// 失败
{"code": 400, "message": "具体错误描述", "data": null}
```

所有 API 遵循此格式，前端 `api/config.js` 据此解析。

---

### 3.3 authentication — 认证模块

**位置：** `backend/authentication/`

**模型：**

| Model | 表 | 字段 |
|-------|----|------|
| `UserProfile` | `authentication_userprofile` | user(OneToOne→auth_user), avatar |
| `PasswordResetToken` | `authentication_passwordresettoken` | token_hash, created_at, expires_at, used |

> Django 内置 `auth_user` 表已有 id/username/email/password/is_active 等字段，`UserProfile` 通过 OneToOne 扩展它（类似于给 Spring Security 的 UserDetails 加字段）。

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `drf_authentication.py` | [认证] | `JWTAuthentication` 类：从 `Authorization: Bearer <token>` 头提取 JWT，解码验证，返回 user |
| `controllers/auth_controller.py` | [CTL] | 7 个 HTTP 端点（见下表） |
| `services/auth_service.py` | [SRV] | 注册、登录验证、用户查询 |
| `services/jwt_service.py` | [SRV] | 自定义 HMAC-SHA256 JWT 的签发和验证 |
| `services/refresh_session_service.py` | [SRV] | Refresh Token 轮换：创建→轮换→撤销，存储基于 Django Cache |
| `services/password_reset_service.py` | [SRV] | 密码重置 token 的创建、验证、消费 |

**API 端点：**

| 方法 | URL | 说明 | 鉴权 |
|------|-----|------|------|
| GET | `/api/auth/csrf` | 获取 CSRF cookie | 无 |
| POST | `/api/auth/register` | 注册 | 无 |
| POST | `/api/auth/login` | 登录，返回 access token + 设置 refresh cookie | 无 |
| POST | `/api/auth/refresh` | 用 refresh cookie 换新 access token | Cookie |
| POST | `/api/auth/logout` | 登出，撤销 refresh session | JWT |
| POST | `/api/auth/forgot-password` | 发送密码重置邮件 | 无 |
| POST | `/api/auth/reset-password` | 重置密码 | Token |

**JWT 机制：**
- Access Token：HMAC-SHA256 签名，短有效期（分钟级），存前端内存（不存 localStorage）
- Refresh Token：随机字符串，存 Django Cache + HTTP-only Cookie，用于刷新 access token
- 刷新时执行轮换（旧 refresh token 立即失效，签发新的）

---

### 3.4 rbac — 权限模块

**位置：** `backend/rbac/`（无自定义模型，直接使用 Django 内置 `auth_user`/`auth_group`/`auth_permission`）

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/profile_controller.py` | [CTL] | 当前用户资料（GET/PATCH）、改密码、上传头像 |
| `controllers/admin_controller.py` | [CTL] | 管理员：用户 CRUD、角色 CRUD、权限列表、分配用户组 |
| `services/rbac_service.py` | [SRV] | 核心 RBAC：3 个默认角色、权限映射、角色/用户管理、自动角色绑定 |
| `services/authz_service.py` | [SRV] | `@jwt_login_required` / `@permission_required` 装饰器 |
| `services/profile_stats_service.py` | [SRV] | 用户统计（问题数、文档数、使用天数） |
| `management/commands/seed_rbac.py` | [命令] | `python manage.py seed_rbac` — 种子化 RBAC 数据 |

**三种系统角色（seed_rbac 创建）：**

| 角色 | 拥有的关键权限 |
|------|-------------|
| `super_admin` | 所有权限 |
| `admin` | 用户管理、角色查看、文档管理、模型配置、监控查看、审计查看 |
| `member` | 知识库文档操作、问答、风险查看 |

**API 端点：**

| 方法 | URL | 说明 | 所需权限 |
|------|-----|------|---------|
| GET/PATCH | `/api/auth/me` | 获取/更新当前用户资料 | JWT |
| POST | `/api/auth/me/password` | 修改密码 | JWT |
| POST | `/api/auth/me/avatar` | 上传头像 | JWT |
| GET/POST | `/api/admin/users` | 用户列表/创建 | `view_user` / `add_user` |
| PATCH/DELETE | `/api/admin/users/<id>` | 更新/删除用户 | `change_user` / `delete_user` |
| PUT | `/api/admin/users/<id>/groups` | 分配用户组 | `assign_role` |
| GET | `/api/admin/roles` | 角色列表 | `view_role` |
| POST | `/api/admin/roles/create` | 创建角色 | `assign_role` |
| GET/PATCH/DELETE | `/api/admin/roles/<id>` | 角色详情/更新/删除 | `view_role` / `assign_role` |
| GET | `/api/admin/permissions` | 权限列表 | `view_role` |

---

### 3.5 knowledgebase — 知识库模块

**位置：** `backend/knowledgebase/`（最大的模块）

**模型（7 个表）：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `Dataset` | `knowledgebase_dataset` | name, description, owner(FK→User) |
| `Document` | `knowledgebase_document` | title, file, status(上传→解析→清洗→分块→索引→完成/失败), file_hash(SHA256去重), visibility, parsed_text, source_date |
| `DocumentVersion` | `knowledgebase_documentversion` | root_document(FK), version_number, is_current, source_metadata |
| `IngestionTask` | `knowledgebase_ingestiontask` | document(FK), task_id(Celery ID), strategy, steps_tracking |
| `DocumentChunk` | `knowledgebase_documentchunk` | document(FK), content, section_chunk(FK, nullable), vector_id |
| `DocumentSectionChunk` | `knowledgebase_documentsectionchunk` | document(FK), section_index, section_label, section_path, vector_id |
| `CleaningRule` | `knowledgebase_cleaningrule` | name, rule_type(13种), pattern, enabled, priority |
| `DocumentCleaningResult` | `knowledgebase_documentcleaningresult` | document(FK), rules_applied, quality_score, before/after_lengths |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| **Controllers** | | |
| `controllers/dataset_controller.py` | [CTL] | 数据集 CRUD |
| `controllers/document_controller.py` | [CTL] | 文档上传（multipart）、列表、详情、删除、统计 |
| `controllers/version_controller.py` | [CTL] | 文档版本管理 |
| `controllers/ingest_controller.py` | [CTL] | 触发文档入库（parse → clean → chunk → index） |
| `controllers/batch_controller.py` | [CTL] | 批量入库/删除 |
| `controllers/chunk_controller.py` | [CTL] | 获取文档的所有 chunk |
| `controllers/cleaning_controller.py` | [CTL] | 触发清洗/获取清洗结果 |
| `controllers/cleaning_rule_controller.py` | [CTL] | 清洗规则 CRUD |
| **Services** | | |
| `services/document_service.py` | [SRV] | 核心：`ingest_document`（编排整个入库管线）、`create_document_from_upload`（SHA256 去重）、`delete_document_with_vectors`（级联删除向量） |
| `services/parser_service.py` | [SRV] | 文档解析：PDF→pymupdf4llm(pypdf兜底)、DOCX→python-docx、TXT→直接读取 |
| `services/chunk_service.py` | [SRV] | 分块策略：flat（固定大小）、element-aware（按文档元素边界）、sentence-window（滑动窗口） |
| `services/hierarchical_chunk_service.py` | [SRV] | 分层 chunk：父 section + 子 chunk 两级结构 |
| `services/cleaning_engine_service.py` | [SRV] | 清洗引擎：13 种规则 → 逐文档处理 |
| `services/cleaning_rule_service.py` | [SRV] | 清洗规则 CRUD + 默认规则引导 |
| `services/cleaning_quality_service.py` | [SRV] | 清洗质量评分（长度/符号密度/句子完整度/问题密度） |
| `services/embedding_service.py` | [SRV] | 调用活跃的 embedding provider 生成向量 |
| `services/vector_service.py` | [SRV] | Milvus 操作：建 Collection、批量写入向量（dense + 可选 BM25 sparse）、删除 |
| `services/search_text_service.py` | [SRV] | 构造 chunk 的检索文本（content + metadata 字段拼接） |
| `services/dataset_service.py` | [SRV] | 数据集 CRUD |
| `services/version_service.py` | [SRV] | 文档版本创建（原子操作，自增版本号） |
| `tasks.py` | [TSK] | `ingest_document_task` — Celery 任务，执行完整入库管线 |

**文档入库流程：**

```
上传文件
  → SHA256 计算（检查重复）
    → 保存到磁盘 + 创建 Document 记录（status=uploaded）
      → 触发 ingest（手动或自动）
        → Celery 异步任务：
          ① parse：pymupdf4llm/pypdf/python-docx 解析为纯文本
          ② clean：清洗引擎处理（13种规则）
          ③ chunk：选择分块策略（flat/hierarchical/element/sentence-window）
          ④ embed：调用 embedding provider 生成向量
          ⑤ index：写入 Milvus Collection
          ⑥ update status → indexed
```

**API 端点：**

| 方法 | URL | 说明 |
|------|-----|------|
| GET/POST | `/api/knowledgebase/datasets` | 数据集列表/创建 |
| GET | `/api/knowledgebase/datasets/<id>` | 数据集详情 |
| GET/POST | `/api/knowledgebase/documents` | 文档列表/上传(multipart) |
| GET | `/api/knowledgebase/documents/stats` | 文档统计 |
| GET/DELETE | `/api/knowledgebase/documents/<id>` | 文档详情/删除 |
| GET | `/api/knowledgebase/documents/<id>/chunks` | 获取文档 chunks |
| GET/POST | `/api/knowledgebase/documents/<id>/versions` | 版本列表/上传新版本 |
| POST | `/api/knowledgebase/documents/<id>/ingest` | 触发入库 |
| GET/POST | `/api/knowledgebase/documents/<id>/cleaning` | 获取/触发清洗 |
| POST | `/api/knowledgebase/documents/batch/ingest` | 批量入库 |
| POST | `/api/knowledgebase/documents/batch/delete` | 批量删除 |
| GET/POST | `/api/knowledgebase/cleaning/rules` | 清洗规则列表/创建 |
| GET/PATCH/DELETE | `/api/knowledgebase/cleaning/rules/<id>` | 规则详情/更新/删除 |
| POST | `/api/knowledgebase/cleaning/rules/bootstrap` | 初始化默认规则 |
| GET | `/api/knowledgebase/cleaning/summary` | 清洗概览统计 |

---

### 3.6 rag — 检索模块

**位置：** `backend/rag/`

**模型：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `RetrievalLog` | `rag_retrievallog` | query, top_k, filters, result_count, source, duration_ms |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/retrieval_controller.py` | [CTL] | `retrieval_query_view` — 独立检索 API |
| `services/retrieval_service.py` | [SRV] | 检索编排：retrieve → rerank → top-k |
| `services/retrieval_backend_service.py` | [SRV] | 分发：向量检索 vs 关键词检索策略 |
| `services/llamaindex_store_service.py` | [SRV] | **核心**：LlamaIndex + Milvus 集成。向量搜索、BM25（缓存）、MySQL 全文搜索、混合搜索（RRFRanker）、多查询融合 |
| `services/rerank_service.py` | [SRV] | Rerank 精排（单查询 / 多查询融合取最高分），无 rerank 模型时回退到原始向量分数 |
| `services/llamaindex_embedding_adapter.py` | [SRV] | 桥接 LlamaIndex embedding 接口 → 内部 provider |
| `services/llamaindex_llm_adapter.py` | [SRV] | 桥接 LlamaIndex LLM 接口 → 内部 chat provider |
| `services/retrieval_log_service.py` | [SRV] | 检索日志记录 |
| `management/commands/rebuild_llamaindex_index.py` | [命令] | 重建 LlamaIndex 索引 |

**检索策略优先级：**

```
用户查询
  → ① Milvus 向量检索（dense embedding + BM25 sparse 混合，RRF 融合）
  → ② 回退：MySQL FULLTEXT 全文搜索
  → ③ 兜底：token 关键词匹配
  → Rerank 精排（如有 active rerank 模型）
  → Top-K 截断
  → 返回 citations
```

**API 端点：**

| 方法 | URL | 说明 |
|------|-----|------|
| POST | `/api/rag/retrieval/query` | 检索查询 `{query, top_k, filters}` |

---

### 3.7 chat — 问答模块

**位置：** `backend/chat/`

**模型（5 个表）：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `ChatSession` | `chat_chatsession` | user(FK), title, rolling_summary, message_count, context_filters |
| `ChatMessage` | `chat_chatmessage` | session(FK), sequence_number(会话内自增), role(user/assistant/system), content, citations(JSON), model_metadata(JSON) |
| `MemoryItem` | `chat_memoryitem` | scope, type, source, content, confidence, is_pinned, embedding, fingerprints |
| `MemoryEvidence` | `chat_memoryevidence` | memory(FK), session(FK), message(FK), evidence_text |
| `MemoryActionLog` | `chat_memoryactionlog` | memory(FK), action, user(FK) |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/ask_controller.py` | [CTL] | `chat_ask_view`（非流式）和 `chat_ask_stream_view`（SSE 流式） |
| `controllers/session_controller.py` | [CTL] | 会话 CRUD、导出 |
| `controllers/memory_controller.py` | [CTL] | 记忆列表、证据、Pin/Unpin、删除 |
| `services/rag_graph_service.py` | [SRV] | **核心**：LangGraph StateGraph 编排 RAG 管线 |
| `services/ask_service.py` | [SRV] | 编排 RAG + LLM + 消息持久化 + 检索日志 |
| `services/context_service.py` | [SRV] | 构建 LLM 对话上下文（消息历史 + 摘要 + 记忆 + citations） |
| `services/memory_service.py` | [SRV] | 记忆 CRUD、关键词+语义搜索、LLM 自动提取 |
| `services/session_service.py` | [SRV] | 会话 CRUD、消息创建/完成、调度后台任务 |
| `services/summary_service.py` | [SRV] | 滚动对话摘要 |
| `services/title_service.py` | [SRV] | LLM 生成会话中文标题 |
| `services/store.py` | [SRV] | `DjangoMemoryStore` — LangGraph 的长期记忆后端（cosine 相似度搜索） |
| `tasks.py` | [TSK] | `update_session_title_task`, `update_session_summary_task`, `extract_session_memories_task` — 异步会话维护 |

**LangGraph RAG 管线（rag_graph_service.py）：**

```
用户问题
  → route：判断是否需要检索（直接回答 vs 检索增强）
  → rewrite_query（LLM）：改写优化查询
  → retrieve_and_merge：Milvus 向量 + BM25 关键词 + MySQL 全文搜索 → 合并去重
  → score_filter：相关性评分过滤
  → build_context：构建带引用的回答上下文
  → LLM 生成答案（流式 SSE 或非流式）
  → 保存消息 → 异步触发：更新标题、更新摘要、提取记忆
```

**API 端点：**

| 方法 | URL | 说明 |
|------|-----|------|
| POST | `/api/chat/ask` | 非流式问答 |
| POST | `/api/chat/ask/stream` | SSE 流式问答 |
| GET/POST | `/api/chat/sessions` | 会话列表/创建 |
| GET/DELETE | `/api/chat/sessions/<id>` | 会话详情/删除 |
| GET | `/api/chat/sessions/<id>/export` | 导出会话 |
| GET | `/api/chat/memories` | 记忆列表 |
| DELETE | `/api/chat/memories/<id>` | 删除记忆 |
| GET | `/api/chat/memories/<id>/evidence` | 记忆关联证据 |
| POST | `/api/chat/memories/<id>/pin` | 置顶/取消置顶记忆 |

---

### 3.8 risk — 风险分析模块

**位置：** `backend/risk/`

**模型（3 个表）：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `RiskEvent` | `risk_riskevent` | company_name, risk_type, risk_level(low/medium/high/critical), event_time, summary, evidence_text, confidence_score(0-1), review_status, document(FK), chunk(FK) |
| `RiskReport` | `risk_riskreport` | scope_type(company/document/time_range), title, company_name, period_start/end, summary, content |
| `RiskExtractionTask` | `risk_riskextractiontask` | id(UUID), document(FK), celery_task_id, steps(JSON进度), result_payload(JSON) |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/extract_controller.py` | [CTL] | 单文档风险抽取、重试、状态轮询 |
| `controllers/batch_extract_controller.py` | [CTL] | 批量文档风险抽取 |
| `controllers/list_controller.py` | [CTL] | 风险事件列表 |
| `controllers/review_controller.py` | [CTL] | 审核风险事件（approve/reject） |
| `controllers/report_controller.py` | [CTL] | 创建报告（公司/文档/时间范围）、导出报告 |
| `controllers/analytics_controller.py` | [CTL] | 风险分析概览看板 |
| `controllers/sentiment_controller.py` | [CTL] | 情感分析 |
| `services/extraction_service.py` | [SRV] | **核心**：编排风险抽取全流程（见下方管线） |
| `services/task_service.py` | [SRV] | 抽取任务管理（并发限制、心跳、超时过期） |
| `services/chunk_filter_service.py` | [SRV] | 从文档 chunks 中筛选风险相关片段 |
| `services/verification_service.py` | [SRV] | LLM 抽取 + 验证轮次 |
| `services/adjudication_service.py` | [SRV] | 事件元数据补充 |
| `services/analytics_service.py` | [SRV] | 风险看板数据聚合 |
| `services/report_service.py` | [SRV] | 报告生成（按公司/文档/时间范围） |
| `services/review_service.py` | [SRV] | 事件审核状态更新 |
| `services/query_service.py` | [SRV] | 事件查询过滤 |
| `services/sentiment_service.py` | [SRV] | 情感分析（LLM 驱动 + 关键词兜底） |
| `tasks.py` | [TSK] | `extract_document_task`（单文档，risk队列）、`batch_extract_document_task`、`expire_stale_extractions_task` |

**风险抽取管线：**

```
文档已索引
  → 提交抽取任务（Celery，risk 队列）
    → ① retrieving：获取文档所有 chunks
    → ② extracting_signals：关键词信号检测
    → ③ chunk过滤：筛选风险相关 chunks
    → ④ extracting：LLM 逐 chunk 抽取风险事件（JSON schema 约束）
    → ⑤ verifying：LLM 验证抽取结果
    → ⑥ adjudicating：补充元数据、去重
    → ⑦ persisting：写入 RiskEvent 表
    → 完成
```

**API 端点：**

| 方法 | URL | 说明 |
|------|-----|------|
| GET | `/api/risk/analytics/overview` | 风险看板 |
| GET | `/api/risk/events` | 风险事件列表 |
| POST | `/api/risk/events/<id>/review` | 审核事件 |
| POST | `/api/risk/reports/company` | 生成公司风险报告 |
| GET | `/api/risk/reports/<id>/export` | 导出报告 |
| POST | `/api/risk/reports/time-range` | 生成时间范围报告 |
| POST | `/api/risk/sentiment/analyze` | 情感分析 |
| POST | `/api/risk/documents/<id>/extract` | 触发单文档抽取 |
| POST | `/api/risk/documents/<id>/extract/retry` | 重试抽取 |
| POST | `/api/risk/documents/<id>/report` | 生成文档风险报告 |
| POST | `/api/risk/documents/extract-batch` | 批量抽取 |
| POST | `/api/risk/documents/extract-batch/retry` | 批量重试 |
| GET | `/api/risk/documents/extract/status/<task_id>` | 轮询抽取状态 |

---

### 3.9 llm — 模型中台模块

**位置：** `backend/llm/`（注意：URL 前缀是 `/api/ops/`，不是 `/api/llm/`）

**模型（5 个表）：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `ModelConfig` | `llm_modelconfig` | capability(chat/embedding/rerank), provider(deepseek/dashscope/ollama/openai_compatible), model_name, endpoint, pricing, is_active(同 capability 唯一) |
| `ModelInvocationLog` | `llm_modelinvocationlog` | provider, model_config(FK), model_name, input_tokens, output_tokens, cost_usd, trace_id, error_message |
| `EvalRecord` | `llm_evalrecord` | mode(baseline/rag/fine_tuned), task_type, metrics(JSON), model_config(FK) |
| `FineTuneRunnerServer` | `llm_finetunerunnerserver` | name, base_url, auth_token |
| `FineTuneRun` | `llm_finetunerun` | base_model, runner_server(FK), dataset, strategy(lora/qlora), status, metrics(JSON), artifact_path |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/model_config_controller.py` | [CTL] | 模型配置 CRUD、激活切换、连接测试 |
| `controllers/gateway_controller.py` | [CTL] | 网关可观测性（摘要、日志、trace、错误、成本分析） |
| `controllers/console_controller.py` | [CTL] | 模型中台控制台（摘要、可观测性、知识管线） |
| `controllers/evaluation_controller.py` | [CTL] | 评测记录管理 |
| `controllers/fine_tune_controller.py` | [CTL] | 微调完整生命周期管理 |
| `controllers/prompt_config_controller.py` | [CTL] | Prompt 模板管理 |
| `services/runtime_service.py` | [SRV] | **关键**：解析 active ModelConfig → 实例化对应 Provider 类 |
| `services/model_config_service.py` | [SRV] | 获取 active / manageable 模型配置 |
| `services/model_invocation_log_service.py` | [SRV] | 记录每次模型调用（token 数、cost、trace_id） |
| `services/model_usage_query_service.py` | [SRV] | 网关数据分析（成本曲线、模型分布、错误统计） |
| `services/prompt_service.py` | [SRV] | 加载 Prompt 模板（从 `prompts/` 目录，LRU 缓存）+ 渲染 |
| `services/evaluation_service.py` | [SRV] | 评测逻辑 |
| `services/fine_tune_service.py` | [SRV] | 微调任务 CRUD |
| `services/fine_tune_dispatch_service.py` | [SRV] | 下发微调任务到远程 runner |
| `services/fine_tune_runner_client.py` | [SRV] | LLaMA-Factory runner HTTP 客户端 |
| `services/providers/` | | |
| `providers/base.py` | [SRV] | 抽象基类：`BaseChatProvider`、`BaseEmbeddingProvider`、`BaseRerankProvider` |
| `providers/openai_compatible_provider.py` | [SRV] | OpenAI 兼容协议（认证、重试、传输层）+ Chat/Embedding/Rerank 实现 |
| `providers/deepseek_provider.py` | [SRV] | 继承 OpenAICompatibleChatProvider，设置 DeepSeek 默认值 |
| `providers/ollama_provider.py` | [SRV] | Ollama Chat + Embedding |
| `providers/dashscope_provider.py` | [SRV] | 阿里 DashScope Embedding + Rerank |
| `providers/registry.py` | [SRV] | Provider 注册表：`(provider, capability) → ProviderClass` |

**Provider 模式说明：**

这是一个典型的**策略模式**。运行时根据数据库中 `ModelConfig` 的 `provider` 和 `capability` 字段，动态选择对应的 Provider 实现：

```python
# runtime_service.py 的核心逻辑（伪代码）
def get_chat_provider():
    config = get_active_model_config(capability='chat')
    provider_cls = PROVIDER_REGISTRY[(config.provider, 'chat')]
    return provider_cls(config)
```

当前支持的 provider：
- **DeepSeek** — Chat（OpenAI 兼容协议）
- **DashScope** — Embedding + Rerank
- **Ollama** — Chat + Embedding（本地部署）
- **OpenAI Compatible** — Chat + Embedding + Rerank（任何兼容 API）

**API 端点：**

| 方法 | URL | 说明 |
|------|-----|------|
| GET/POST | `/api/ops/model-configs` | 模型配置列表/创建 |
| PATCH/DELETE | `/api/ops/model-configs/<id>` | 更新/删除模型配置 |
| PATCH | `/api/ops/model-configs/<id>/activation` | 切换激活状态 |
| POST | `/api/ops/model-configs/test-connection` | 测试模型连接 |
| GET | `/api/ops/llm/summary` | 控制台摘要 |
| GET | `/api/ops/llm/observability` | 控制台可观测性 |
| GET | `/api/ops/llm/knowledge` | 控制台知识管线 |
| GET | `/api/ops/llm/gateway/summary` | 网关摘要 |
| GET | `/api/ops/llm/gateway/logs` | 网关调用日志 |
| GET | `/api/ops/llm/gateway/logs/summary` | 日志摘要 |
| GET | `/api/ops/llm/gateway/traces/<trace_id>` | Trace 详情 |
| GET | `/api/ops/llm/gateway/errors` | 错误日志 |
| GET | `/api/ops/llm/gateway/costs/summary` | 成本摘要 |
| GET | `/api/ops/llm/gateway/costs/timeseries` | 成本时序 |
| GET | `/api/ops/llm/gateway/costs/models` | 按模型成本分布 |
| GET/POST | `/api/ops/evaluations` | 评测列表/运行评测 |
| GET/POST | `/api/ops/fine-tune-servers` | 微调服务器管理 |
| GET/POST | `/api/ops/fine-tunes` | 微调任务管理 |
| POST | `/api/ops/fine-tunes/<id>/dispatch` | 下发微调任务 |
| GET | `/api/ops/fine-tunes/<id>/export` | 导出微调结果 |
| GET/PATCH | `/api/ops/prompt-configs` | Prompt 模板管理 |

---

### 3.10 ops — 运维监控模块

**位置：** `backend/ops/`（URL 前缀是 `/api/monitoring/`）

**模型（3 个表）：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `SystemMetric` | `ops_systemmetric` | metric_name, value, unit, tags(JSON), collected_at |
| `AlertRule` | `ops_alertrule` | metric_name, condition(gt/lt/gte/lte/eq), threshold, severity(info/warning/critical), enabled |
| `AlertEvent` | `ops_alertevent` | rule(FK), status(firing/resolved/acknowledged), triggered_value, triggered_at, resolved_at, acknowledged_by |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/metrics_controller.py` | [CTL] | 系统状态、指标时序查询 |
| `controllers/alert_rule_controller.py` | [CTL] | 告警规则 CRUD + 默认规则种子 |
| `controllers/alert_event_controller.py` | [CTL] | 告警事件列表、确认 |
| `services/monitoring_query_service.py` | [SRV] | 系统状态查询、指标时序、告警查询 |
| `services/alert_engine_service.py` | [SRV] | 告警引擎：评估规则 → 触发/恢复告警事件 |
| `services/metrics_collector_service.py` | [SRV] | 指标采集（文档数、chunk 数、向量数等） |
| `tasks.py` | [TSK] | `collect_metrics_task`、`evaluate_alerts_task` — 周期性 Celery Beat 任务 |

**API 端点：**

| 方法 | URL | 说明 |
|------|-----|------|
| GET | `/api/monitoring/monitoring/status` | 系统当前状态 |
| GET | `/api/monitoring/monitoring/metrics` | 指标时序数据 |
| GET/POST | `/api/monitoring/alerts/rules` | 告警规则列表/创建 |
| GET/PATCH/DELETE | `/api/monitoring/alerts/rules/<id>` | 规则详情/更新/删除 |
| POST | `/api/monitoring/alerts/rules/seed-defaults` | 初始化默认告警规则 |
| GET | `/api/monitoring/alerts/events` | 告警事件列表 |
| POST | `/api/monitoring/alerts/events/<id>/acknowledge` | 确认告警 |

---

### 3.11 systemcheck — 健康检查与审计

**位置：** `backend/systemcheck/`

**模型（1 个表）：**

| Model | 表 | 核心字段 |
|-------|----|---------|
| `AuditRecord` | `systemcheck_auditrecord` | actor(FK→User), action, target_type, target_id, status(submitted/succeeded/failed), detail_payload(JSON，自动脱敏) |

**文件清单：**

| 文件 | 角色 | 说明 |
|------|------|------|
| `controllers/health_controller.py` | [CTL] | 健康检查（检查 DB + Redis 连通性） |
| `controllers/dashboard_controller.py` | [CTL] | Dashboard 统计聚合 |
| `controllers/audit_controller.py` | [CTL] | 审计日志列表（分页+筛选） |
| `services/dashboard_service.py` | [SRV] | 聚合 knowledgebase/risk/chat/ops 各模块统计数据 |
| `services/audit_service.py` | [SRV] | 审计事件记录（自动脱敏 password/token/secret 等敏感字段） |
| `services/demo_data_service.py` | [SRV] | 演示数据种子 |

**API 端点：**

| 方法 | URL | 说明 | 鉴权 |
|------|-----|------|------|
| GET | `/api/health` | 健康检查 | 无 |
| GET | `/api/dashboard/stats` | 看板统计 | `view_dashboard` |
| GET | `/api/systemcheck/audits` | 审计日志 | `view_audit_log` |

---

## 4. 前端模块详解

### 4.1 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 (Composition API + `<script setup>`) | UI 框架 |
| Vue Router | 前端路由 |
| Vite | 构建工具 |
| Element Plus | UI 组件库（表格、表单、对话框、卡片等） |
| ECharts | 图表（风险趋势、模型用量、Dashboard） |
| marked + highlight.js | Markdown 渲染 + 代码高亮 |
| DOMPurify | XSS 防护，清洗 HTML |
| SheetJS (xlsx) | Excel 导出 |
| @iconify/vue | 图标系统（Lucide 图标集） |
| 无 TypeScript | 纯 JavaScript ES Modules |

### 4.2 目录结构

```text
frontend/src/
├── api/                    # API 请求封装（每个文件对应一个后端模块）
│   ├── config.js           # 核心 HTTP 客户端（JWT 注入、401 自动刷新、统一错误处理）
│   ├── auth.js             # 认证 API（login/register/refresh/logout/me）
│   ├── admin.js            # 管理端 API（用户/角色/权限 CRUD）
│   ├── chat.js             # 问答 API（会话列表/创建/删除/导出）
│   ├── qa.js               # 问答请求（ask 非流式 / ask/stream SSE 流式）
│   ├── knowledgebase.js   # 知识库 API（文档/数据集/版本/入库/清洗）
│   ├── cleaning.js         # 清洗规则 API
│   ├── risk.js             # 风险 API（事件/报告/抽取/情感分析）
│   ├── dashboard.js        # Dashboard 统计 + 审计日志
│   ├── llm.js              # 模型中台 API（模型配置/微调）
│   ├── llm-gateway.js      # 网关可观测性 API
│   ├── llm-console.js      # 控制台 API
│   ├── monitoring.js       # 监控 API（系统状态/指标/告警）
│   └── ops.js              # 运维 API（mock 数据）
├── router/
│   ├── index.js            # 路由实例 + beforeEach 守卫（认证/权限检查）
│   └── routes.js           # 路由表定义（workspace + admin + auth）
├── layouts/
│   ├── WorkspaceLayout.vue # 工作区壳（侧边栏 + 顶栏 + 内容区）
│   ├── AdminLayout.vue     # 管理端壳（侧边栏 + 顶栏 + 内容区）
│   └── AuthLayout.vue      # 认证壳（纯内容）
├── components/
│   ├── ui/                 # 通用 UI 组件
│   │   ├── AppSidebar.vue  # 左侧导航栏（工作区/管理端双形态）
│   │   ├── AppTopbar.vue   # 顶部栏（标题/搜索/主题/通知/头像）
│   │   ├── AppAvatar.vue   # 头像（图片/首字母渐变）
│   │   ├── AppIcon.vue     # 图标（Iconify + Lucide）
│   │   ├── AppSectionCard.vue # 卡片容器
│   │   ├── AppToolbar.vue  # 工具栏容器
│   │   ├── FlashStack.vue  # Toast 通知栈
│   │   ├── ThemeToggle.vue # 主题切换按钮
│   │   └── MetaChips.vue   # 标签行
│   ├── AuthLanding.vue     # 登录/注册全页表单（品牌动画 + 表单）
│   ├── FinancialQA.vue     # 智能问答主界面（对话 + 引用 + SSE流式）
│   ├── KnowledgeBase.vue   # 知识库管理（上传/列表/入库）
│   ├── RiskSummary.vue     # 风险提取页面（上传→入库→抽取→查看）
│   ├── ChatHistory.vue     # 会话历史列表
│   ├── ChatMemoryDrawer.vue# 长期记忆管理抽屉
│   ├── AdminUsers.vue      # 用户管理表格
│   ├── MarkdownRenderer.vue# Markdown 渲染（marked + highlight.js + DOMPurify）
│   ├── ModelConfig.vue     # 模型配置页面（模型CRUD + 微调管理）
│   ├── OpsDashboard.vue    # 管理端 Dashboard（图表/指标）
│   └── admin/              # 管理端子组件
│       ├── AdminChart.vue  # ECharts 图表包装器
│       ├── AdminDataTable.vue # 通用数据表格
│       ├── AdminRoleManagement.vue # 角色管理
│       └── ops/            # 运维监控子组件
├── views/                  # 页面视图（薄层，组装组件）
│   ├── auth/AuthView.vue
│   ├── workspace/          # 6 个工作区页面
│   └── admin/              # 14 个管理端页面
├── lib/                    # 工具库（数据规范化/状态管理/图表配置）
│   ├── auth-storage.js     # Token + Profile 内存存储
│   ├── auth-session.js     # 会话生命周期（登录/刷新/登出）
│   ├── session-state.js    # 路由解析、权限校验
│   ├── permission.js       # 权限检查工具
│   ├── flash.js            # Toast 通知（响应式）
│   ├── theme.js            # 主题管理（亮/暗）
│   ├── admin-dashboard.js  # Dashboard 图表配置（ECharts option）
│   ├── admin-audit.js      # 审计日志格式化
│   ├── admin-roles.js      # 角色管理工具
│   ├── admin-monitoring.js # 监控数据规范化
│   ├── llm-gateway.js      # 网关数据规范化
│   ├── llm-console.js      # 控制台数据规范化
│   ├── llamafactory-config.js # LLaMA-Factory 训练配置
│   ├── risk-workspace.js   # 风险图表配置
│   ├── risk-summary-export.js # Excel 导出
│   ├── chat-memory.js      # 记忆类型/范围标签
│   ├── knowledgebase-actions.js # 文档入库状态判断
│   ├── workspace-qa.js     # Q&A 会话工具
│   └── ...
├── config/
│   └── navigation.js       # 导航结构定义（侧边栏菜单项+权限过滤）
└── style.css               # 全局样式 + 设计 Token + 暗色模式
```

### 4.3 数据流

```
用户操作 (Component)
  → lib/ 层规范化/校验
    → api/ 层发起 HTTP 请求
      → config.js：注入 JWT → 发送 → 解析响应/处理 401
        → Django API
      ← JSON {code, message, data}
    ← 抛异常或返回数据
  → lib/ 层规范化响应数据
  → Component 响应式更新 UI
```

### 4.4 认证流程

```
页面加载
  → router beforeEach 守卫
    → auth-session.js bootstrap()
      → 检查内存中是否有 token（当前会话）
      → 有：用 /api/auth/me 验证有效性
      → 无但有 refresh cookie：调用 /api/auth/refresh 换新 token
      → 都没有：跳转 /login
    → 根据 profile.groups 判断用户角色
      → admin → /admin/overview
      → member → /workspace/qa

登录
  → POST /api/auth/login {username, password}
    → 成功：保存 token 到内存 + 保存 profile → 跳转首页
    → 失败：显示错误

Token 刷新
  → API 返回 401
    → config.js 拦截
      → auth-session.js refresh()
        → POST /api/auth/refresh（带去重，防止并发刷新）
        → 成功：更新内存 token → 重试原请求
        → 失败：清除状态 → 跳转 /login
```

---

## 5. API 速查表

按 URL 前缀分组，标注对应的后端 Controller 文件和所需权限。

### 认证 (`/api/auth/`)

| 方法 | URL | Controller | 鉴权 |
|------|-----|-----------|------|
| GET | `/api/auth/csrf` | auth_controller.csrf_view | 无 |
| POST | `/api/auth/register` | auth_controller.register_view | 无 |
| POST | `/api/auth/login` | auth_controller.login_view | 无 |
| POST | `/api/auth/refresh` | auth_controller.refresh_view | Cookie |
| POST | `/api/auth/logout` | auth_controller.logout_view | JWT |
| POST | `/api/auth/forgot-password` | auth_controller.forgot_password_view | 无 |
| POST | `/api/auth/reset-password` | auth_controller.reset_password_view | Token |

### 个人资料 & 管理 (`/api/`)

| 方法 | URL | Controller | 权限 |
|------|-----|-----------|------|
| GET/PATCH | `/api/auth/me` | profile_controller | JWT |
| POST | `/api/auth/me/password` | profile_controller | JWT |
| POST | `/api/auth/me/avatar` | profile_controller | JWT |
| GET/POST | `/api/admin/users` | admin_controller | view_user / add_user |
| PATCH/DELETE | `/api/admin/users/<id>` | admin_controller | change_user / delete_user |
| PUT | `/api/admin/users/<id>/groups` | admin_controller | assign_role |
| GET | `/api/admin/roles` | admin_controller | view_role |
| POST | `/api/admin/roles/create` | admin_controller | assign_role |
| GET/PATCH/DEL | `/api/admin/roles/<id>` | admin_controller | view_role / assign_role |
| GET | `/api/admin/permissions` | admin_controller | view_role |

### 知识库 (`/api/knowledgebase/`)

| 方法 | URL | Controller | 权限 |
|------|-----|-----------|------|
| GET/POST | `/api/knowledgebase/datasets` | dataset_controller | view_document |
| GET | `/api/knowledgebase/datasets/<id>` | dataset_controller | view_document |
| GET/POST | `/api/knowledgebase/documents` | document_controller | view_document |
| GET | `/api/knowledgebase/documents/stats` | document_controller | view_document |
| GET/DELETE | `/api/knowledgebase/documents/<id>` | document_controller | view_document / delete_document |
| GET | `/api/knowledgebase/documents/<id>/chunks` | chunk_controller | view_document |
| GET/POST | `/api/knowledgebase/documents/<id>/versions` | version_controller | view_document |
| POST | `/api/knowledgebase/documents/<id>/ingest` | ingest_controller | trigger_ingest |
| GET/POST | `/api/knowledgebase/documents/<id>/cleaning` | cleaning_controller | view_document |
| POST | `/api/knowledgebase/documents/batch/ingest` | batch_controller | trigger_ingest |
| POST | `/api/knowledgebase/documents/batch/delete` | batch_controller | delete_document |
| GET/POST | `/api/knowledgebase/cleaning/rules` | cleaning_rule_controller | manage_cleaning_rules |
| GET/PATCH/DEL | `/api/knowledgebase/cleaning/rules/<id>` | cleaning_rule_controller | manage_cleaning_rules |
| POST | `/api/knowledgebase/cleaning/rules/bootstrap` | cleaning_rule_controller | manage_cleaning_rules |
| GET | `/api/knowledgebase/cleaning/summary` | cleaning_rule_controller | manage_cleaning_rules |

### 检索 (`/api/rag/`)

| 方法 | URL | Controller | 权限 |
|------|-----|-----------|------|
| POST | `/api/rag/retrieval/query` | retrieval_controller | ask_financial_qa |

### 问答 (`/api/chat/`)

| 方法 | URL | Controller | 权限 |
|------|-----|-----------|------|
| POST | `/api/chat/ask` | ask_controller | ask_financial_qa |
| POST | `/api/chat/ask/stream` | ask_controller | ask_financial_qa |
| GET/POST | `/api/chat/sessions` | session_controller | ask_financial_qa |
| GET/DELETE | `/api/chat/sessions/<id>` | session_controller | ask_financial_qa |
| GET | `/api/chat/sessions/<id>/export` | session_controller | ask_financial_qa |
| GET | `/api/chat/memories` | memory_controller | ask_financial_qa |
| DELETE | `/api/chat/memories/<id>` | memory_controller | ask_financial_qa |
| GET | `/api/chat/memories/<id>/evidence` | memory_controller | ask_financial_qa |
| POST | `/api/chat/memories/<id>/pin` | memory_controller | ask_financial_qa |

### 风险 (`/api/risk/`)

| 方法 | URL | Controller | 权限 |
|------|-----|-----------|------|
| GET | `/api/risk/analytics/overview` | analytics_controller | view_document |
| GET | `/api/risk/events` | list_controller | view_document |
| POST | `/api/risk/events/<id>/review` | review_controller | review_risk_event |
| POST | `/api/risk/reports/company` | report_controller | view_document |
| GET | `/api/risk/reports/<id>/export` | report_controller | view_document |
| POST | `/api/risk/reports/time-range` | report_controller | view_document |
| POST | `/api/risk/sentiment/analyze` | sentiment_controller | JWT |
| POST | `/api/risk/documents/<id>/extract` | extract_controller | trigger_ingest |
| POST | `/api/risk/documents/<id>/extract/retry` | extract_controller | trigger_ingest |
| POST | `/api/risk/documents/<id>/report` | report_controller | view_document |
| POST | `/api/risk/documents/extract-batch` | batch_extract_controller | trigger_ingest |
| POST | `/api/risk/documents/extract-batch/retry` | batch_extract_controller | trigger_ingest |
| GET | `/api/risk/documents/extract/status/<task_id>` | extract_controller | JWT |

### 模型中台 (`/api/ops/`)

| 方法 | URL | Controller |
|------|-----|-----------|
| GET/POST | `/api/ops/model-configs` | model_config_controller |
| PATCH/DEL | `/api/ops/model-configs/<id>` | model_config_controller |
| PATCH | `/api/ops/model-configs/<id>/activation` | model_config_controller |
| POST | `/api/ops/model-configs/test-connection` | model_config_controller |
| GET | `/api/ops/llm/summary` | console_controller |
| GET | `/api/ops/llm/observability` | console_controller |
| GET | `/api/ops/llm/knowledge` | console_controller |
| GET | `/api/ops/llm/gateway/summary` | gateway_controller |
| GET | `/api/ops/llm/gateway/logs` | gateway_controller |
| GET | `/api/ops/llm/gateway/logs/summary` | gateway_controller |
| GET | `/api/ops/llm/gateway/traces/<id>` | gateway_controller |
| GET | `/api/ops/llm/gateway/errors` | gateway_controller |
| GET | `/api/ops/llm/gateway/costs/summary` | gateway_controller |
| GET | `/api/ops/llm/gateway/costs/timeseries` | gateway_controller |
| GET | `/api/ops/llm/gateway/costs/models` | gateway_controller |
| GET/POST | `/api/ops/evaluations` | evaluation_controller |
| GET/POST | `/api/ops/fine-tune-servers` | fine_tune_controller |
| GET/POST | `/api/ops/fine-tunes` | fine_tune_controller |
| POST | `/api/ops/fine-tunes/<id>/dispatch` | fine_tune_controller |
| GET | `/api/ops/fine-tunes/<id>/export` | fine_tune_controller |
| GET/PATCH | `/api/ops/prompt-configs` | prompt_config_controller |

### 监控 (`/api/monitoring/`)

| 方法 | URL | Controller |
|------|-----|-----------|
| GET | `/api/monitoring/monitoring/status` | metrics_controller |
| GET | `/api/monitoring/monitoring/metrics` | metrics_controller |
| GET/POST | `/api/monitoring/alerts/rules` | alert_rule_controller |
| GET/PATCH/DEL | `/api/monitoring/alerts/rules/<id>` | alert_rule_controller |
| POST | `/api/monitoring/alerts/rules/seed-defaults` | alert_rule_controller |
| GET | `/api/monitoring/alerts/events` | alert_event_controller |
| POST | `/api/monitoring/alerts/events/<id>/acknowledge` | alert_event_controller |

### 系统 (`/api/`)

| 方法 | URL | Controller | 鉴权 |
|------|-----|-----------|------|
| GET | `/api/health` | health_controller | 无 |
| GET | `/api/dashboard/stats` | dashboard_controller | view_dashboard |
| GET | `/api/systemcheck/audits` | audit_controller | view_audit_log |

---

## 6. 数据流全景图

### 用户上传文档 → 问答 → 风险抽取 完整链路

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 文档入库                                                         │
│                                                                     │
│  POST /api/knowledgebase/documents (multipart file)                 │
│    → document_controller: 保存文件，创建 Document (status=uploaded) │
│    → POST /api/knowledgebase/documents/<id>/ingest                  │
│      → ingest_controller → Celery Task (celery 队列):               │
│         ① parser_service: pymupdf4llm/pypdf → 纯文本                │
│         ② cleaning_engine_service: 13种规则清洗                      │
│         ③ chunk_service: 分块 (flat/hierarchical/element)           │
│         ④ embedding_service: embedding provider → 向量             │
│         ⑤ vector_service: 写入 Milvus Collection                   │
│         ⑥ llamaindex_store_service: 同步 LlamaIndex 索引           │
│       → Document.status = 'indexed'                                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. 智能问答                                                         │
│                                                                     │
│  POST /api/chat/ask  (或 /ask/stream for SSE)                      │
│    → ask_controller → ask_service → rag_graph_service (LangGraph):  │
│       ① route: 判断是否需要检索                                     │
│       ② rewrite_query: LLM 改写查询                                 │
│       ③ retrieve_and_merge:                                        │
│          → Milvus 向量检索 (dense)                                  │
│          → BM25 关键词检索 (sparse)                                 │
│          → MySQL 全文搜索 (fallback)                                │
│          → RRF 融合                                                  │
│       ④ score_filter: 相关性过滤                                    │
│       ⑤ rerank: rerank provider 精排                               │
│       ⑥ build_context: 组装 prompt (历史+摘要+记忆+citations)       │
│       ⑦ LLM chat: 生成答案                                         │
│    → 保存 ChatMessage (content + citations + model_metadata)        │
│    → 异步触发: 更新标题 + 更新摘要 + 提取记忆                       │
│       → MemoryItem 写入 (with embedding)                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. 风险抽取                                                         │
│                                                                     │
│  POST /api/risk/documents/<id>/extract                             │
│    → extract_controller → Celery Task (risk 队列):                  │
│       ① 获取文档所有 chunks                                         │
│       ② 关键词信号检测                                               │
│       ③ chunk_filter: 筛选风险相关片段                              │
│       ④ LLM 抽取: RiskEvent JSON schema 约束输出                    │
│       ⑤ LLM 验证: 复核抽取结果                                      │
│       ⑥ 去重 + 元数据补充                                           │
│       ⑦ 持久化: RiskEvent 写入 MySQL                                │
│    → RiskExtractionTask 状态跟踪 (前端轮询)                          │
│                                                                     │
│  GET /api/risk/events → 查看风险事件列表                             │
│  POST /api/risk/reports/company → 生成公司风险报告                   │
│  POST /api/risk/sentiment/analyze → 文档情感分析                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Celery 任务队列

```
┌─────────────────────────────────────────┐
│           Celery Beat (调度器)           │
│                                         │
│  ops: collect_metrics_task (定期采集)    │
│  ops: evaluate_alerts_task (定期评估)    │
└──────────────┬──────────────────────────┘
               │ 发送定时任务
               ▼
┌──────────────────────────────────────────┐
│          Redis (Broker + Result)          │
└──────┬──────────────────────┬────────────┘
       │ celery 队列           │ risk 队列
       ▼                       ▼
┌──────────────┐        ┌──────────────┐
│celery-worker │        │celery-worker │
│              │        │   -risk      │
│ 文档解析     │        │              │
│ 清洗        │        │ 风险抽取     │
│ 分块        │        │ 批量抽取     │
│ 向量化      │        │ 过期清理     │
│ 索引同步    │        │              │
│ 标题生成    │        │              │
│ 摘要更新    │        │              │
│ 记忆提取    │        │              │
└──────────────┘        └──────────────┘
```

### 关键文件快速索引

当你想了解某个功能的实现时，按此顺序阅读：

| 想知道... | 先看 | 再看 | 最后看 |
|----------|------|------|--------|
| 某个 API 的 URL 和参数 | `app/urls.py` | `app/controllers/xxx_controller.py` | — |
| 某个业务逻辑怎么实现 | `app/services/xxx_service.py` | `app/models.py`（看数据结构） | `app/tasks.py`（如果是异步的） |
| 数据库有哪些表 | `app/models.py` | `app/migrations/` | `docs/design/database-design.md` |
| 前端调用了哪些 API | `frontend/src/api/xxx.js` | Chrome DevTools Network | `backend/app/controllers/` |
| 配置在哪里 | `backend/config/settings.py` | 环境变量 `.env` | `docker-compose.prod.yml` |
| 权限定义 | `Django admin → Permissions` | `rbac/services/rbac_service.py` | `rbac/management/commands/seed_rbac.py` |

---

> 最后更新: 2026-05-22
