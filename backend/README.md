# finmodpro-backend

`finmodpro` 后端当前版本基于 Django 提供健康检查、JWT 登录闭环，以及基于 Django `User / Group / Permission` 的最小 RBAC 演示能力。

## 当前完成范围

- 健康检查：`GET /api/health`
- 注册：`POST /api/auth/register`
- 登录：`POST /api/auth/login`
- 当前用户资料：`GET /api/auth/me`
- 管理员用户列表：`GET /api/admin/users`
- 管理员角色列表：`GET /api/admin/groups`
- 管理员更新用户角色：`PUT /api/admin/users/<id>/groups`
- 认证：仅 `access token`
- RBAC：直接复用 Django `User / Group / Permission`
- 注册默认角色：新用户自动加入 `member`
- RBAC 初始化：`python manage.py seed_rbac`
- 配置：已整理为面向 MySQL / Redis 的环境变量结构
- 本地默认运行：SQLite + LocMemCache，避免没有 MySQL / Redis 时无法启动

## 当前未做

- `refresh token`
- JWT 黑名单 / 退出登录
- 邮箱验证码、找回密码
- 实际 Redis 业务使用
- 实际 MySQL 联通验证

## MVC 结构说明

本阶段按 Django 习惯落成清晰分层：

- `config/`
  - 项目级配置与环境变量解析
- `authentication/models.py`
  - 认证域模型入口，当前复用 Django 内置 `User`
- `authentication/services/`
  - 认证业务与 JWT 生成/校验
- `authentication/controllers/`
  - 请求解析、参数校验、响应组装
- `authentication/urls.py`
  - 认证路由
- `rbac/services/`
  - Group / Permission 种子、用户角色摘要、管理员列表与角色覆盖 helper
- `rbac/controllers/`
  - 当前用户 RBAC profile 接口、管理员用户/角色管理接口
- `rbac/management/commands/seed_rbac.py`
  - 初始化 `super_admin` / `admin` / `member` 及默认权限映射
- `systemcheck/controllers/`
  - 健康检查控制层
- `systemcheck/urls.py`
  - 健康检查路由

## 环境变量

可参考 [`.env.example`](/root/.openclaw/workspace/projects/finmodpro-backend/.env.example)。

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
cd /root/.openclaw/workspace/projects/finmodpro-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_rbac
python manage.py runserver 127.0.0.1:8000
```

说明：

- 当前项目未引入 `.env` 自动加载库，环境变量可通过 `export` 或进程前缀方式注入
- 如果直接本地启动，默认配置已可使用 SQLite 跑通
- `seed_rbac` 建议在 `migrate` 后执行一次；命令幂等，可重复执行

示例：

```bash
export APP_ENV=development
export DJANGO_DEBUG=true
export JWT_SECRET_KEY=local-dev-secret
python manage.py runserver 127.0.0.1:8000
```

## 测试方式

```bash
cd /root/.openclaw/workspace/projects/finmodpro-backend
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
cd /root/.openclaw/workspace/projects/finmodpro-backend
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

这是“毕设演示可运行版本”，目标是稳定提供最小认证 + RBAC 闭环，而不是一次做完整企业级权限平台。当前方案明确直接复用 Django 内置 `User / Group / Permission`，不自建独立 RBAC 数据模型。
