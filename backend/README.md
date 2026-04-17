# finmodpro-backend

`finmodpro` 后端当前版本基于 Django，已挂载系统检查、认证/RBAC、知识库、模型配置、RAG、聊天问答和风险分析相关 API。不同模块完成度不完全一致，但当前启动方式和功能范围不应再按“只有最小认证示例”理解。

## 当前功能概览

- 健康检查：`GET /api/health`
- 工作台统计：`GET /api/dashboard/stats`
- 注册：`POST /api/auth/register`
- 登录：`POST /api/auth/login`
- 当前用户资料：`GET /api/auth/me`
- 管理员用户列表：`GET /api/admin/users`
- 管理员角色列表：`GET /api/admin/groups`
- 管理员更新用户角色：`PUT /api/admin/users/<id>/groups`
- 知识库文档列表/新增：`/api/knowledgebase/documents`
- 知识库文档入库：`/api/knowledgebase/documents/<id>/ingest`
- 模型配置/Prompt 配置/评测：`/api/ops/...`
- RAG 检索：`POST /api/rag/retrieval/query`
- 聊天问答/会话：`/api/chat/...`
- 风险事件/抽取/报告：`/api/risk/...`
- 认证：仅 `access token`
- RBAC：直接复用 Django `User / Group / Permission`
- 注册默认角色：新用户自动加入 `member`
- RBAC 初始化：`python manage.py seed_rbac`
- 配置：已整理为面向 SQLite / MySQL、LocMemCache / Redis 的环境变量结构
- 本地默认运行：SQLite + LocMemCache + 内存 Celery backend/broker

说明：

- 以上接口已在 [`config/urls.py`](/root/finmodpro/backend/config/urls.py) 挂载
- 部分高级能力依赖模型、数据或进阶服务配置；当前 README 只保证启动说明和范围概览不误导
- 依赖服务的本地启动说明见 [`backend/docs/dependency-services.md`](/root/finmodpro/backend/docs/dependency-services.md)

## 当前仍有限制

- `refresh token`
- JWT 黑名单 / 退出登录
- 邮箱验证码、找回密码
- 一键式依赖编排（当前只提供手动启动说明）

## 项目结构说明

当前项目按 Django app 拆分：

- `config/`
  - 项目级配置、URL 和环境变量解析
- `authentication/`
  - 注册、登录、JWT 鉴权
- `rbac/`
  - 当前用户资料、管理员用户/角色管理、RBAC 种子命令
- `knowledgebase/`
  - 文档管理与入库
- `llm/`
  - 模型配置、Prompt 配置、评测记录
- `rag/`
  - 检索增强查询
- `chat/`
  - 问答与会话历史
- `risk/`
  - 风险事件抽取、审核、报告
- `systemcheck/`
  - 健康检查和工作台统计
- `rbac/management/commands/seed_rbac.py`
  - 初始化 `super_admin` / `admin` / `member` 及默认权限映射

## 环境变量

可参考 [`.env.example`](/root/finmodpro/backend/.env.example)。

### Django

- `APP_ENV`：运行环境标识，默认 `development`
- `DJANGO_DEBUG`：是否开启调试，默认 `true`
- `DJANGO_SECRET_KEY`：Django secret
- `DJANGO_ALLOWED_HOSTS`：逗号分隔

### Database

- `DB_ENGINE`：`sqlite` 或 `mysql`，默认 `sqlite`
- `DB_NAME`
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_CONN_MAX_AGE`

说明：

- 本地默认 `DB_ENGINE=sqlite`
- 若切到 `mysql`，需自行准备对应 MySQL 驱动与数据库实例

### Redis

- `REDIS_ENABLED`：默认 `false`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `REDIS_PASSWORD`

说明：

- 关闭时使用 Django 本地内存缓存
- 打开后会切换到 Redis cache 配置

### Celery

- `CELERY_BROKER_URL`：默认 `memory://`
- `CELERY_RESULT_BACKEND`：默认 `cache+memory://`
- `CELERY_TASK_ALWAYS_EAGER`
- `CELERY_TASK_EAGER_PROPAGATES`
- `CELERY_TASK_STORE_EAGER_RESULT`

说明：

- 当前默认值适合本地开发
- 聊天会话标题、滚动摘要、长期记忆提取这 3 个维护任务共用当前 Celery 配置
- 当 `CELERY_TASK_ALWAYS_EAGER=true`，或 `CELERY_BROKER_URL` 仍是默认 `memory://` 时，这些维护任务会在 Django 进程内直接执行
- 当你切到真实 broker（如 Redis）且未开启 eager 时，任务会改为异步入队；此时需要有 Celery worker 消费，否则聊天主流程仍返回成功，但标题/摘要/记忆不会被后台刷新

### Chat

- `CHAT_CONTEXT_RECENT_MESSAGES`：默认 `8`
- `CHAT_MEMORY_RESULT_LIMIT`：默认 `5`
- `CHAT_SUMMARY_TRIGGER_MESSAGES`：默认 `6`

说明：

- `CHAT_CONTEXT_RECENT_MESSAGES` 控制问答上下文中带入多少条最近的已完成消息
- `CHAT_MEMORY_RESULT_LIMIT` 控制单次问答最多带入多少条长期记忆
- `CHAT_SUMMARY_TRIGGER_MESSAGES` 控制会话累计多少条已完成消息后才开始生成 `rolling_summary`
- 以上变量都要求整数；如果写成非法非整数值，Django 会在加载 `settings.py` 时启动失败
- 如果值是合法整数但写成 `0` 或负数，服务层会按至少 `1` 条处理

### Knowledge Base / Milvus

- `MILVUS_URI`：默认 `milvus.db`
- `MILVUS_COLLECTION_NAME`
- `KB_CHUNK_SIZE`
- `KB_CHUNK_OVERLAP`
- `KB_EMBEDDING_DIMENSION`

说明：

- 当前 `.env.example` 已给出本地默认值
- 进阶依赖和更完整部署说明后续补充

### JWT

- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`：默认 `HS256`
- `JWT_ACCESS_TOKEN_LIFETIME_SECONDS`：默认 `7200`

### RBAC

无新增环境变量。当前 RBAC 固定复用 Django 内置表：

- 角色：`Group`
- 权限：`Permission`
- 用户角色关系：`User.groups`

## 运行方式

```bash
cd /root/finmodpro/backend
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

说明：

- 当前项目未引入 `.env` 自动加载库，`cp .env.example .env` 后还要显式加载环境变量
- 如果直接本地启动，默认配置已可使用 SQLite 跑通
- `seed_rbac` 建议在 `migrate` 后执行一次；命令幂等，可重复执行
- 如果你要切到 MySQL / Redis / Milvus / Ollama，请先看 [`backend/docs/dependency-services.md`](/root/finmodpro/backend/docs/dependency-services.md)

示例：

```bash
export APP_ENV=development
export DJANGO_DEBUG=true
export JWT_SECRET_KEY=local-dev-secret
python manage.py runserver 127.0.0.1:8000
```

## 测试方式

```bash
cd /root/finmodpro/backend
source .venv/bin/activate
python manage.py test authentication systemcheck
python manage.py test authentication rbac systemcheck
python manage.py test rbac -v 2
python manage.py check
```

## 接口清单

### 1. 健康检查

`GET /api/health`

示例响应：

```json
{
  "status": "ok",
  "service": "finmodpro-backend",
  "environment": "development",
  "timestamp": "2026-03-24T10:00:00.000000+08:00"
}
```

### 2. 注册

`POST /api/auth/register`

请求体：

```json
{
  "username": "alice",
  "password": "secret123",
  "email": "alice@example.com"
}
```

示例响应：

```json
{
  "message": "注册成功。",
  "access_token": "<jwt>",
  "access_token_type": "Bearer",
  "expires_in": 7200,
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com"
  }
}
```

说明：

- 注册成功后，后端会自动把新用户加入 `member` 组
- JWT 仍保持轻量，不直接携带完整角色和权限集合

### 3. 登录

`POST /api/auth/login`

请求体：

```json
{
  "username": "alice",
  "password": "secret123"
}
```

示例响应：

```json
{
  "message": "登录成功。",
  "access_token": "<jwt>",
  "access_token_type": "Bearer",
  "expires_in": 7200,
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com"
  }
}
```

### 4. 当前用户资料与权限摘要

`GET /api/auth/me`

请求头：

```http
Authorization: Bearer <jwt>
```

示例响应：

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "groups": ["member"],
  "permissions": ["view_dashboard"]
}
```

用途：

- 前端登录后读取当前用户角色与权限
- 用于菜单、页面、按钮的基础可见性控制
- 权限变更后，无需把完整权限塞进 JWT

### 5. 管理员用户列表

`GET /api/admin/users`

请求头：

```http
Authorization: Bearer <jwt>
```

权限要求：

- `auth.view_user`

示例响应：

```json
[
  {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "groups": ["member"],
    "permissions": ["view_dashboard"],
    "is_superuser": false,
    "is_staff": false,
    "date_joined": "2026-03-24T15:00:00+08:00"
  }
]
```

### 6. 管理员角色列表

`GET /api/admin/groups`

请求头：

```http
Authorization: Bearer <jwt>
```

权限要求：

- `auth.view_role`

示例响应：

```json
[
  { "id": 1, "name": "admin" },
  { "id": 2, "name": "member" },
  { "id": 3, "name": "super_admin" }
]
```

### 7. 管理员更新用户角色

`PUT /api/admin/users/<id>/groups`

请求头：

```http
Authorization: Bearer <jwt>
Content-Type: application/json
```

权限要求：

- `auth.assign_role`

请求体：

```json
{
  "groups": ["admin", "member"]
}
```

说明：

- `groups` 采用整集合覆盖更新，不区分 add/remove 子接口
- 支持一次提交多个角色
- 权限汇总仍由 Django `Group / Permission` 自动聚合

示例响应：

```json
{
  "id": 2,
  "username": "bob",
  "email": "bob@example.com",
  "groups": ["admin", "member"],
  "permissions": [
    "add_user",
    "change_user",
    "view_dashboard",
    "view_role",
    "view_user"
  ],
  "is_superuser": false,
  "is_staff": false,
  "date_joined": "2026-03-24T16:00:00+08:00"
}
```

## 管理员演示链路

推荐演示顺序：

1. 使用普通用户登录，只展示普通页面，不展示后台入口
2. 使用管理员登录，先调用 `GET /api/auth/me` 确认具备后台权限
3. 进入管理员仪表盘后调用 `GET /api/admin/users` 和 `GET /api/admin/groups`
4. 在用户管理页提交 `PUT /api/admin/users/<id>/groups`，用完整 `groups` 数组覆盖目标用户角色
5. 前端局部刷新当前用户行，重新展示角色与权限摘要变化

## RBAC 初始化与演示角色

执行：

```bash
cd /root/finmodpro/backend
source .venv/bin/activate
python manage.py migrate
python manage.py seed_rbac
```

默认角色：

- `super_admin`
- `admin`
- `member`

默认映射：

- `super_admin`：拥有当前演示范围内全部已定义权限
- `admin`：`view_dashboard`、`view_user`、`add_user`、`change_user`、`view_role`
- `member`：`view_dashboard`

当前自定义权限：

- `view_dashboard`
- `view_role`
- `assign_role`

## 当前边界说明

这是“毕设演示可运行版本”。当前仓库已经进入多模块并行阶段，但不同模块成熟度不同；文档中的重点仍是提供不误导的启动说明、基础认证/RBAC 链路和当前已挂载 API 范围说明。RBAC 方案仍明确直接复用 Django 内置 `User / Group / Permission`，不自建独立 RBAC 数据模型。
