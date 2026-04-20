# FinModPro

FinModPro 是一个面向金融风控场景的全栈演示项目，聚焦 **知识库管理、RAG 检索问答、风险事件抽取、权限控制与运维配置** 等核心能力。仓库采用 **monorepo** 结构，前端与后端分离开发，线上环境通过服务器本机脚本直接部署。

> 当前仓库更适合用作课程项目、原型验证和功能演示。部分高级能力已落地接口与模块，但不同模块成熟度不完全一致，README 以“真实可运行、不过度承诺”为原则说明现状。

## Features

- **身份认证与权限控制**
  - 用户注册、登录、当前用户资料查询
  - 基于 Django `User / Group / Permission` 的 RBAC
  - 管理员用户列表、角色列表、角色分配接口
- **知识库管理**
  - 文档上传、文档列表、文档入库
  - 文本解析、分块、向量化与向量存储流程
- **RAG / 智能问答**
  - 检索增强问答接口
  - 聊天会话与历史消息能力
- **风险分析**
  - 风险事件抽取
  - 风险事件列表、审核、报告生成
- **运维与配置**
  - 模型配置、Prompt 配置、评测记录相关接口
  - 健康检查、工作台统计
  - 服务器部署脚本与冒烟检查

## Repository Structure

```text
finmodpro/
├─ frontend/                 # Vue 3 + Vite 前端
│  ├─ src/
│  │  ├─ api/                # 前端 API 封装
│  │  ├─ components/         # 页面/业务组件
│  │  └─ lib/                # 本地存储、权限工具
│  └─ .env.example
├─ backend/                  # Django 后端
│  ├─ authentication/        # 注册、登录、JWT
│  ├─ rbac/                  # 用户资料、角色管理、鉴权
│  ├─ knowledgebase/         # 知识库文档与入库
│  ├─ rag/                   # 检索增强查询
│  ├─ chat/                  # 会话与问答
│  ├─ risk/                  # 风险抽取、审核、报告
│  ├─ llm/                   # 模型/Prompt/评测配置
│  ├─ systemcheck/           # 健康检查、工作台统计
│  ├─ config/                # Django 配置与路由
│  └─ .env.example
├─ docs/                     # 项目文档
├─ scripts/                  # 部署与冒烟检查脚本
└─ docker-compose.prod.yml     # 生产部署 compose
```

## Tech Stack

### Frontend

- Vue 3
- Vite
- JavaScript (ES Modules)

### Backend

- Django 5
- Django REST Framework
- Celery
- PyMySQL
- Redis
- Milvus / milvus-lite

### Deployment

- Shell deployment scripts (`scripts/deploy.sh`, `scripts/poll-deploy.sh`, `scripts/smoke-check.sh`)
- Docker Compose production deployment
- 服务器本机拉取 `main` 后直接部署

## Core Modules

### Frontend

前端当前已包含以下主要功能组件：

- `Workbench`：工作台容器
- `OpsDashboard`：系统概览 / 统计面板
- `KnowledgeBase`：知识库管理
- `FinancialQA`：问答与检索体验
- `ChatHistory`：会话历史
- `RiskSummary`：风险摘要展示
- `AdminUsers`：管理员用户与角色管理
- `ModelConfig` / `EvaluationResult`：模型配置与评测结果展示

### Backend

后端当前已挂载或实现的核心模块：

- `authentication`：注册、登录、JWT 鉴权
- `rbac`：当前用户资料、管理员用户/角色管理、权限校验
- `knowledgebase`：文档管理、入库、向量化处理
- `rag`：检索与检索日志
- `chat`：问答与会话能力
- `risk`：风险抽取、复核与报告
- `llm`：模型配置、Prompt 配置、评测记录
- `systemcheck`：健康检查、工作台统计、演示数据服务

## Quick Start

### 1) Clone repository

```bash
git clone https://github.com/fliycode/finmodpro.git
cd finmodpro
```

### 2) Start backend

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

Backend default local URL:

```text
http://127.0.0.1:8000
```

### 3) Start frontend

Open a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

Frontend default local URL:

```text
http://127.0.0.1:5173
```

## Environment Variables

项目保留了可公开展示的环境变量模板；真实生产配置请使用你自己的服务器配置文件、部署平台 Secret 或 CI Secret，不要把敏感信息直接提交到仓库。

### Frontend

参考文件：[`frontend/.env.example`](./frontend/.env.example)

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Backend

参考文件：[`backend/.env.example`](./backend/.env.example)

常用变量示例：

```env
APP_ENV=development
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=<your-secret>
JWT_SECRET_KEY=<your-jwt-secret>
DB_ENGINE=sqlite
DB_NAME=db.sqlite3
REDIS_ENABLED=false
MILVUS_URI=milvus.db
```

> 说明：README 仅保留公开模板与占位符。生产环境的主机、账号、密码、SSH 密钥、私有地址等信息请通过外部安全方式管理。

## Local Development Notes

- 后端默认可用 **SQLite + LocMemCache + 内存 Celery backend/broker** 进行本地开发
- 如需切换到 MySQL / Redis / Milvus / 外部模型服务，请参考：
  - [`backend/docs/dependency-services.md`](./backend/docs/dependency-services.md)
- 当前项目没有内建 `.env` 自动加载库，因此加载 `.env` 后通常还需要显式 `source`

## Available API Areas

当前项目主要 API 范围包括：

- `/api/health`
- `/api/dashboard/stats`
- `/api/auth/...`
- `/api/admin/...`
- `/api/knowledgebase/...`
- `/api/ops/...`
- `/api/rag/...`
- `/api/chat/...`
- `/api/risk/...`

更详细的后端接口与说明可见：[`backend/README.md`](./backend/README.md)

## Testing

### Backend

```bash
cd backend
source .venv/bin/activate
python manage.py check
python manage.py test
```

### Frontend

```bash
cd frontend
npm test
npm run build
```

## Deployment Workflow

当前部署方式是 **当前服务器本机部署**：

1. 代码合入 `main`
2. 服务器上的 `/opt/finmodpro` 拉取 `origin/main`
3. 执行 `scripts/deploy.sh`
4. 使用 `scripts/smoke-check.sh` 做部署后验证

如需手动触发，也可以在服务器上执行：

```bash
cd /opt/finmodpro
./scripts/deploy.sh
```

## Documentation

- 本地启动说明：[`docs/local-setup.md`](./docs/local-setup.md)
- 部署说明：[`docs/deployment.md`](./docs/deployment.md)
- 演示脚本：[`docs/demo-script.md`](./docs/demo-script.md)
- 测试报告：[`docs/test-report.md`](./docs/test-report.md)
- 后端详细说明：[`backend/README.md`](./backend/README.md)

## Project Status

当前仓库已具备：

- 前后端独立启动能力
- 认证 / RBAC 基础链路
- 知识库、RAG、聊天、风险分析等模块化结构
- 基础 CI/CD 流程

当前仍建议按“演示项目 / 原型系统”来理解，而不是直接视为完整生产系统。以下能力仍可能需要按你的场景继续补全：

- 更完整的生产级安全加固
- 更完善的任务队列与异步任务编排
- 更稳定的向量数据库与模型服务部署方案
- 更细致的前端交互、权限策略与异常处理

## Suggested Workflow

如果你要继续开发这个项目，推荐顺序：

1. 先跑通本地前后端
2. 初始化后端迁移与 RBAC 种子数据
3. 验证认证、管理台、知识库与问答主链路
4. 再接入 MySQL / Redis / Milvus 等依赖
5. 最后接入服务器部署与线上联调

## License

当前仓库未声明正式开源许可证。如需公开分发或商用，请先补充合适的 License 文件。
