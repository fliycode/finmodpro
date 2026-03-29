# FinModPro 本地启动文档

本文档面向一台新机器，目标是用仓库当前默认配置把前后端先跑起来。`MySQL / Redis / Milvus / Ollama` 的详细本地部署说明后续补充；当前先使用仓库已经支持的本地默认方案。

## 1. 前置依赖

- Git
- Python 3.12 左右，并可用 `python3`
- Node.js 20 及以上，并可用 `npm`

当前仓库默认本地方案：

- 后端数据库默认使用 SQLite
- 后端缓存默认使用 Django `LocMemCache`
- Celery 默认是内存 broker/result backend
- 前端默认请求 `http://localhost:8000`

这意味着在不额外启动 `MySQL / Redis` 的情况下，认证、RBAC、基础页面和部分 API 可以先本地跑通。

## 2. 仓库准备

```bash
git clone <your-repo-url>
cd /root/finmodpro
```

如果你已经在仓库目录里，可直接执行后续步骤。

## 3. 环境变量

### 3.1 后端

后端仓库内已有示例文件：[`backend/.env.example`](/root/finmodpro/backend/.env.example)。

```bash
cd /root/finmodpro/backend
cp .env.example .env
```

需要注意：

- 当前项目没有引入自动读取 `.env` 的库，`cp` 这一步主要用于保存一份本地配置样板
- 真正启动前，还需要把 `.env` 中的变量加载进 shell
- 最简单的方法是：

```bash
cd /root/finmodpro/backend
set -a
source .env
set +a
```

本地直接可跑的关键默认值：

- `DB_ENGINE=sqlite`
- `DB_NAME=db.sqlite3`
- `REDIS_ENABLED=false`
- `CELERY_BROKER_URL=memory://`
- `CELERY_RESULT_BACKEND=cache+memory://`
- `MILVUS_URI=milvus.db`
- `JWT_SECRET_KEY=replace-with-a-local-dev-jwt-secret`
- `DJANGO_CSRF_TRUSTED_ORIGINS` 与 `DJANGO_CORS_ALLOWED_ORIGINS` 已包含 `http://127.0.0.1:5173` 和 `http://localhost:5173`

建议至少把下面两个值改成你自己的本地值：

- `DJANGO_SECRET_KEY`
- `JWT_SECRET_KEY`

### 3.2 前端

前端仓库内已有示例文件：[`frontend/.env.example`](/root/finmodpro/frontend/.env.example)。

```bash
cd /root/finmodpro/frontend
cp .env.example .env
```

默认值如下：

```env
VITE_API_BASE_URL=http://localhost:8000
```

如果后端按本文档启动在本机 `8000` 端口，这个默认值不用改。

## 4. 后端启动

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

- `seed_rbac` 命令在仓库中真实存在：[`backend/rbac/management/commands/seed_rbac.py`](/root/finmodpro/backend/rbac/management/commands/seed_rbac.py)
- `migrate` 后执行一次 `seed_rbac`，会初始化默认角色
- 如果你修改了 `DB_ENGINE=mysql` 或启用了 `REDIS_ENABLED=true`，那就不再属于本文档覆盖的“最小本地启动”范围

## 5. 前端启动

新开一个终端：

```bash
cd /root/finmodpro/frontend
npm install
cp .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

前端脚本来源于 [`frontend/package.json`](/root/finmodpro/frontend/package.json)：

- `npm run dev`
- `npm run build`
- `npm run preview`

## 6. 基础验证

### 6.1 后端健康检查

浏览器或命令行访问：

```bash
curl http://127.0.0.1:8000/api/health/
```

预期返回包含 `status: "ok"`。

### 6.2 前端页面

打开：

```text
http://127.0.0.1:5173
```

预期能看到登录/注册页面。

### 6.3 注册并登录

可以直接在前端页面注册新用户，或手动调用接口：

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"secret123"}'
```

注册成功后，新用户默认会加入 `member` 组。然后可继续登录并验证：

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/dashboard/stats/`

### 6.4 当前功能概览

基于当前路由，仓库已经挂载的主要后端 API 包括：

- 系统检查：`/api/health/`、`/api/dashboard/stats/`
- 认证：`/api/auth/register`、`/api/auth/login`、`/api/auth/me`
- 管理/RBAC：`/api/admin/users`、`/api/admin/groups`
- 知识库：`/api/knowledgebase/...`
- 模型与评测配置：`/api/ops/...`
- 检索增强：`/api/rag/...`
- 会话问答：`/api/chat/...`
- 风险提取与报告：`/api/risk/...`

其中一部分高级能力依赖更完整的数据和模型配置；本文档只保证本地默认配置下的基础启动路径与基础验证不误导。

## 7. 常见问题

### 7.1 `source .env` 之后变量没有生效

这个项目当前不会自动读取 `.env` 文件。请确认你在启动 `manage.py` 之前执行了：

```bash
set -a
source .env
set +a
```

或使用等价的环境变量注入方式。

### 7.2 前端报跨域或请求不到接口

优先检查两件事：

- 后端是否运行在 `http://127.0.0.1:8000` 或 `http://localhost:8000`
- 前端 `.env` 中的 `VITE_API_BASE_URL` 是否与后端地址一致

仓库默认后端示例配置已经放行：

- `http://127.0.0.1:5173`
- `http://localhost:5173`

### 7.3 后端启动时报数据库或缓存相关错误

如果你只是想本地先跑通，请确认仍使用默认值：

- `DB_ENGINE=sqlite`
- `REDIS_ENABLED=false`

不要在这一步提前切到 `MySQL` 或 `Redis`。

### 7.4 某些知识库、检索、风险、问答能力不可用

这类功能可能依赖：

- 更完整的业务数据
- 模型配置
- 向量检索或其他进阶依赖

相关本地依赖启动说明会在模块 J 的后续任务中补充；本文档暂不展开 `MySQL / Redis / Milvus / Ollama` 的详细启动方法。
