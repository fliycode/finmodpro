# FinModPro CI/CD 与自动部署设计

**日期：** 2026-03-29  
**适用仓库：** `/root/finmodpro`  
**部署目标：** 当前线上服务器  
**代码基准：** GitHub `main`

---

## 1. 目标

为 FinModPro 建立一条可维护、可重复执行的 CI/CD 链路：

1. GitHub Actions 负责前后端测试与构建校验。
2. 当 `main` 分支通过校验后，通过 SSH 连接当前服务器。
3. 服务器使用 Docker Compose 完成更新、构建、重启与基础健康检查。
4. 前端与后端统一纳入同一套生产编排，降低手工部署成本。

本设计优先追求 **先跑通、易维护、适合毕设项目迭代**，暂不引入镜像仓库、蓝绿发布或复杂回滚系统。

---

## 2. 锁定的一版架构

采用 **GitHub Actions + SSH + Docker Compose** 模式：

- **CI 侧（GitHub Actions）**
  - 后端：安装依赖、运行 Django 检查和测试
  - 前端：安装依赖、执行构建
  - 通过后进入 deploy job
- **CD 侧（服务器）**
  - SSH 登录当前服务器
  - 进入 `/opt/finmodpro`
  - 拉取 GitHub 最新代码
  - 执行 `docker compose -f docker-compose.prod.yml up -d --build`
  - 执行基础冒烟检查

### 一版入口拓扑（明确锁定）

第一版**不单独增加统一网关容器**，避免部署拓扑反复摇摆：

- `frontend` 容器对外提供 `80`
- `backend` 容器对外提供 `8000`
- 冒烟检查固定验证：
  - `http://127.0.0.1/`
  - `http://127.0.0.1:8000/api/health/`

这样可以让部署脚本、compose、文档和验收标准保持一致；如果后续再加统一 Nginx 网关，应另开一个增强计划，不在本次任务内混做。

---

## 3. 已确认的现有接口与配置前提

### 后端健康检查接口已存在

仓库当前已经挂载：

- `GET /api/health`
- `GET /api/health/`

来源：

- `backend/config/urls.py`
- `backend/systemcheck/urls.py`

所以本次部署链路中的健康检查地址可以稳定锁定为：

- `http://127.0.0.1:8000/api/health/`

### 前端 API 配置策略已锁定

前端当前已有：

- `frontend/src/api/config.js`
- `VITE_API_BASE_URL`

第一版生产部署明确采用 **构建时环境变量** 方案：

- 继续使用 `VITE_API_BASE_URL`
- 不引入运行时动态注入脚本
- 不引入 Nginx 模板替换方案

这样 Gemini 的实现边界清楚：只需保证生产构建读取正确的 `VITE_API_BASE_URL`，并清理不适合生产的 localhost 回退逻辑。

### 后端环境变量策略已锁定

后端当前已经具备 env 驱动配置基础，本次只允许做**最小必要补充**：

- `ALLOWED_HOSTS`
- CORS / CSRF trusted origins
- DB / Redis / Celery / Milvus 相关 env 读取

本次不引入新的配置框架，不做大规模重构，只修正生产容器启动所必需的缺口。

---

## 4. 部署拓扑

生产环境由 `docker-compose.prod.yml` 编排，第一版包含以下服务：

- `frontend`：Vite 构建后的静态站点，由容器内 Nginx 提供
- `backend`：Django API 服务
- `mysql`：主业务数据库
- `redis`：缓存与 Celery broker/result backend
- `milvus`：向量库
- `ollama`：本地模型服务

说明：

- 第一版要求 `frontend` 和 `backend` 都纳入 compose
- 第一版不额外加入单独“反向代理总入口”容器
- 如果某些依赖服务暂时只做编排占位，也必须在文档中写清当前是否真正启用

---

## 5. 分工

### Dora（我）
- 负责方案设计、文件结构约束、Secrets 设计、验收标准
- 负责 `docs/deployment.md` 的**最终收口与验收版本**
- 负责统筹 Codex / Gemini 的边界，避免部署链路割裂

### Codex
- 后端生产容器化
- Docker Compose 生产编排
- 部署脚本
- GitHub Actions 的后端测试与部署流程
- 健康检查与失败退出逻辑

### Gemini
- 前端生产容器化
- 前端构建时环境变量接入
- 前端构建与静态资源部署适配
- 前端线上冒烟检查清单

---

## 6. Secrets、服务器前置条件与权限

### GitHub Actions Secrets

至少配置：

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`

本次**不再单独设置 `DEPLOY_PATH`**，因为部署路径已锁定为 `/opt/finmodpro`。

### 服务器前置条件

首次上线前必须具备：

- Git
- Docker
- Docker Compose Plugin
- 能拉取 GitHub 仓库的权限（deploy key 或其他可行方式）
- `/opt/finmodpro` 可读写
- 生产环境变量文件已准备完毕
- 80 与 8000 端口策略明确、无冲突

### 服务器侧环境变量文件

生产敏感配置仅保留在服务器，例如：

- `/opt/finmodpro/.env.backend`
- `/opt/finmodpro/.env.frontend`
- 可选 `/opt/finmodpro/.env.deploy`

第一版推荐 **生产敏感配置只存服务器，不提交仓库**。

---

## 7. 验证分层

### CI 层验证

GitHub Actions 中只验证**不依赖外部服务的稳定步骤**：

- 后端 `python manage.py check`
- 后端测试（优先使用当前仓库已可在 SQLite / 内存配置下运行的测试）
- 前端 `npm run build`

CI 中不强制拉起 MySQL / Redis / Milvus / Ollama 全量依赖；这些留到部署层验证。

### 部署层验证

服务器部署完成后验证：

- `http://127.0.0.1:8000/api/health/` 返回 200
- `http://127.0.0.1/` 返回 200
- 前端至少一次真实 API 请求成功命中后端

### 首次线上验证前置检查

首次 live deploy 前，必须人工确认：

- GitHub Secrets 已配好
- 服务器已装 Git / Docker / Compose
- `/opt/finmodpro` 仓库已 clone
- `.env.backend` / `.env.frontend` 已存在
- 端口占用无冲突
- 仓库拉取权限可用

---

## 8. 回滚策略

第一版只做**基础可执行回滚**：

- 部署脚本在每次部署前记录当前 commit 到文件，例如 `/opt/finmodpro/.last_deployed_commit`
- 发生异常时，可以手动执行：
  - `git checkout <previous-commit>`
  - `docker compose -f docker-compose.prod.yml up -d --build`

本次不做自动数据库回滚、不做蓝绿发布。

---

## 9. 验收标准

当以下条件全部满足时，认为 CI/CD 第一版完成：

1. push 到 `main` 后，GitHub Actions 自动执行前后端校验。
2. 校验通过后，服务器自动完成部署。
3. 新版本能通过 `http://127.0.0.1:8000/api/health/` 健康检查。
4. 前端页面可访问，并能请求真实后端。
5. 部署失败时，Actions 日志能明确看出失败步骤。
6. 仓库内存在可复用的部署文档，换人也能理解并复现。

---

## 10. 第一版不做的内容

以下内容明确不纳入本次任务范围：

- Docker 镜像推送 GHCR / Docker Hub
- 蓝绿部署 / 金丝雀发布
- 自动数据库回滚
- 多环境（dev / staging / prod）完整隔离
- 自动化域名、HTTPS、证书编排
- 统一反向代理网关重构

这些都可以留作后续增强项，不影响当前毕设项目先形成稳定交付链路。
