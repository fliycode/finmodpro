# FinModPro 测试报告

本文档整理模块 J 当前阶段的可交付验证结果。报告仅记录本轮实际执行或可直接核验的结果，不把未执行内容写成“已通过”。

## 1. 测试范围

本轮覆盖范围：

- 后端自动化测试：Django/DRF 现有 pytest 用例
- 后端配置静态检查：`manage.py check`
- 前端构建验证：Vite 生产构建
- 容器/部署最小验证：后端 Dockerfile、前端 Dockerfile 的实际镜像构建

本轮未覆盖：

- 浏览器端 E2E 自动化
- Docker 容器启动后的运行时 smoke test
- MySQL / Redis / Ollama / Milvus 远程依赖联机验证
- CI 平台上的流水线执行

## 2. 环境与版本

- 仓库路径：`/root/finmodpro`
- 本轮测试基线提交：`e87a130a83687cbf000ace2a8d551c918fa0fb04`
- Python：`3.12.3`
- Node.js：`v22.22.1`
- npm：`10.9.4`
- Docker：`28.2.2`
- 后端测试解释器：`backend/.venv/bin/python`

## 3. 实际执行命令

### 3.1 主干同步

```bash
cd /root/finmodpro
git pull origin main
```

结果：

- `Already up to date.`

### 3.2 后端 pytest

实际有效命令：

```bash
cd /root/finmodpro/backend
../backend/.venv/bin/python -m pytest
```

结果：

- 共收集 `130` 条测试
- 结果：`130 passed`
- 耗时：`173.30s`

说明：

- 直接从仓库根目录执行 `backend/.venv/bin/python -m pytest` 时，pytest `rootdir` 会落到 `/root/finmodpro`，本轮实测为 `collected 0 items`
- 因此当前仓库的正确 pytest 入口应以 `backend/` 为工作目录
- `backend/.venv/bin/pytest` 脚本的 shebang 仍指向旧绝对路径，不能作为稳定入口

### 3.3 Django system check

```bash
cd /root/finmodpro/backend
../backend/.venv/bin/python manage.py check
```

结果：

- `System check identified no issues (0 silenced).`

### 3.4 前端生产构建

```bash
cd /root/finmodpro/frontend
npm run build
```

结果：

- 构建成功
- `43 modules transformed`
- 输出产物：
  - `dist/index.html`
  - `dist/assets/index-IjMq0iEy.css`
  - `dist/assets/index-j10E1C91.js`

说明：

- 在只读沙箱里首次执行会因为 Vite 需要写 `.vite-temp` 而报 `EACCES`
- 在可写文件系统环境中重跑后构建成功
- 该问题属于执行环境限制，不是仓库代码构建错误

### 3.5 后端 Docker 镜像构建

```bash
cd /root/finmodpro
docker build -t finmodpro-backend-test -f backend/Dockerfile backend
```

结果：

- 构建成功
- 最终镜像：`finmodpro-backend-test:latest`

补充观察：

- `backend/Dockerfile` 中依赖安装可正常完成
- `requirements.txt` 已包含 `gunicorn==23.0.0`，与 Dockerfile 启动命令一致

### 3.6 前端 Docker 镜像构建

```bash
cd /root/finmodpro
docker build -t finmodpro-frontend-test -f frontend/Dockerfile frontend
```

结果：

- 构建成功
- 构建阶段内部 `npm run build` 成功
- 最终镜像：`finmodpro-frontend-test:latest`

补充观察：

- `frontend/nginx.conf` 文件存在，Dockerfile 的 `COPY nginx.conf` 可正常完成

## 4. 结果摘要

| 项目 | 类型 | 状态 | 结论 |
| --- | --- | --- | --- |
| 后端 pytest | 实际执行 | 通过 | `130 passed` |
| Django system check | 实际执行 | 通过 | `0 issues` |
| 前端生产构建 | 实际执行 | 通过 | Vite build 成功 |
| 后端 Dockerfile build | 实际执行 | 通过 | 镜像成功构建 |
| 前端 Dockerfile build | 实际执行 | 通过 | 镜像成功构建 |
| 浏览器 E2E | 未执行 | 未覆盖 | 本轮无自动化用例 |
| 容器运行态 smoke test | 未执行 | 未覆盖 | 仅验证到镜像构建 |

## 5. 主链路验证覆盖

本轮没有新增端到端浏览器自动化，但后端 pytest 已覆盖主链路中的核心 API 能力：

- 登录/注册/当前用户：
  - `authentication/tests.py`
- 文档上传、列表、详情、摄取：
  - `knowledgebase/tests.py`
- 问答、会话创建、会话详情、检索日志：
  - `chat/tests.py`
- 风险抽取、批量抽取、事件筛选、审核、报告：
  - `risk/tests.py`
- 模型配置、Prompt 配置、基础评测：
  - `llm/tests.py`
- 管理员用户/角色与权限控制：
  - `rbac/tests.py`
- 健康检查、工作台统计：
  - `systemcheck/tests.py`

结合本轮前端构建成功，可确认：

- 当前前端代码至少能完成生产编译
- 当前后端关键业务 API 在测试环境中可通过自动化测试

不能由本轮结果直接推出的结论：

- 不能直接推出“真实浏览器点击演示链路百分之百无 UI 缺陷”
- 不能直接推出“容器启动后可在任意环境直接跑通完整依赖链”

## 6. 已知问题 / 阻塞

### 6.1 后端 pytest 入口不够稳

问题：

- `backend/.venv/bin/pytest` 的 shebang 仍指向旧路径：
  - `/root/.openclaw/workspace/projects/finmodpro-backend/.venv/bin/python3`

影响：

- 直接执行该脚本会失败
- 必须改用 `backend/.venv/bin/python -m pytest`

### 6.2 从仓库根目录执行 pytest 会收集到 0 条测试

问题：

- 从 `/root/finmodpro` 执行 pytest 时，`rootdir` 被识别为仓库根而不是 `backend/`

影响：

- 容易得到“测试全空跑”的假阳性

建议：

- 在文档、脚本或 CI 中固定使用 `cd backend && ../backend/.venv/bin/python -m pytest`

### 6.3 前端模型配置启停接口仍有前后端方法不一致

静态审查发现：

- 前端 [`frontend/src/api/llm.js`](/root/finmodpro/frontend/src/api/llm.js) 的 `activateModelConfig()` 发送的是 `POST`
- 后端 [`backend/llm/controllers/model_config_controller.py`](/root/finmodpro/backend/llm/controllers/model_config_controller.py) 当前接收的是 `PATCH`

影响：

- 模型配置“启用/停用”前端页面仍存在联调风险

### 6.4 容器只验证到了 build，没有验证运行态

本轮已验证：

- 两个 Dockerfile 都能成功构建镜像

本轮未验证：

- `docker run` 后的健康检查
- 容器内迁移、静态资源、环境变量注入
- 多服务组合启动

因此“容器化可构建”已确认，但“容器化可直接部署上线”本轮没有完成完整证明。

## 7. 结论

基于本轮实际执行结果，可以确认：

- 后端现有自动化测试套件在正确入口下全部通过，关键业务域具备较好的回归基础
- 前端生产构建通过，当前代码处于可打包状态
- 前后端 Dockerfile 均可成功构建镜像，容器化交付的基础材料已具备

当前仍需保留的谨慎结论：

- 模块 J 的“测试报告”这一项已经形成可交付文档
- 但若要把“部署可用性”证明提升到更强等级，还需要补容器运行态 smoke test 或 CI 流水线验证
- 前端模型配置启停接口仍有一个明确的请求方法错位，后续联调时应优先处理

## 8. 2026-04-07 Auth Landing Redesign

本节记录登录页重塑的专项验证结果，只标记本轮实际完成的检查项。

- [x] Login tab renders the new brand-lobby layout on desktop width
- [x] Register tab renders email, confirm password, and terms fields
- [x] Status and validation messages remain visible in the redesigned form area
- [x] Mobile width collapses the layout into a single column without horizontal scroll
- [x] Reduced-motion mode disables continuous ambient animation

实际依据：

- `frontend/src/components/AuthLanding.vue` 已改为品牌门厅式双栏布局，并保留登录 / 注册表单切换逻辑
- `frontend/src/components/AuthLanding.vue` 中注册态仍显式包含 `email`、`confirmPassword`、`agreeTerms` 字段及错误提示绑定
- `frontend/src/components/AuthLanding.vue` 中 `status-box` 与各字段 `error-msg` 仍保留在表单区内
- 已在真实浏览器预览中确认移动端单栏收敛正常，且未观察到横向滚动
- 已在真实浏览器预览中确认 reduced-motion 下持续动效按预期停用
- 本轮在 `frontend/` 下执行 `npm run build`，结果成功：
  - `dist/index.html`
  - `dist/assets/index-BBGlmUVA.css`
  - `dist/assets/index-DwWG9XHc.js`
