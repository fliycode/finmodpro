# FinModPro 当前已实现功能清单

更新日期：2026-04-13

本文档基于当前仓库代码整理，目标是说明“已经实现并可在代码中验证”的能力，而不是产品规划。范围覆盖 `frontend/` 与 `backend/` 当前主干代码。

## 1. 项目当前形态

当前项目是一个前后端分离的金融知识与风险分析系统：

- 前端：Vue 3 + Vite，提供登录页、工作区和管理台。
- 后端：Django，已挂载认证、RBAC、知识库、RAG、聊天、风险分析、模型配置、评测和系统概览接口。
- 默认本地运行方案：SQLite + LocMemCache + 内存 Celery broker/backend。

代码入口：

- 前端路由：[frontend/src/router/routes.js](/Users/td/code/finmodpro/finmodpro/frontend/src/router/routes.js:1)
- 后端总路由：[backend/config/urls.py](/Users/td/code/finmodpro/finmodpro/backend/config/urls.py:1)

## 2. 前端已实现页面

### 2.1 登录与注册

已实现页面：

- `/login`

已实现能力：

- 登录表单与注册表单切换
- 前端字段校验
- 登录后拉取当前用户资料并按角色跳转
- token、本地资料、登录失效提示的本地存储

对应代码：

- [frontend/src/views/auth/AuthView.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/views/auth/AuthView.vue:1)
- [frontend/src/api/auth.js](/Users/td/code/finmodpro/finmodpro/frontend/src/api/auth.js:1)

### 2.2 工作区

已实现页面：

- `/workspace/qa`
- `/workspace/knowledge`
- `/workspace/history`
- `/workspace/risk`

已实现能力：

- 工作区与管理台分开的导航壳
- 智能问答页面
  - 新建会话
  - 基于流式接口输出回答
  - 展示引用依据、来源文档、相关度、耗时
  - 支持从 URL `session` 参数恢复会话
- 知识库页面
  - 文档列表
  - 文档上传
  - 手动触发入库
  - 入库状态轮询
  - 文档详情查看
  - 处理状态、失败状态、已入库状态展示
- 风险页
  - 风险事件、审核和报告的前端工作台组件已接入

对应代码：

- [frontend/src/views/workspace/WorkspaceQaView.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/views/workspace/WorkspaceQaView.vue:1)
- [frontend/src/components/FinancialQA.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/FinancialQA.vue:1)
- [frontend/src/components/KnowledgeBase.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/KnowledgeBase.vue:1)
- [frontend/src/views/workspace/WorkspaceRiskView.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/views/workspace/WorkspaceRiskView.vue:1)

当前限制：

- `/workspace/history` 页面当前直接复用了 `ChatHistory` 展示组件，但没有在该页面内完成会话数据加载，因此独立历史页还不是完整闭环。
  - 代码位置：[frontend/src/views/workspace/WorkspaceHistoryView.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/views/workspace/WorkspaceHistoryView.vue:1)
- 历史会话能力目前在问答页内的抽屉使用体验更完整。
  - 代码位置：[frontend/src/components/FinancialQA.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/FinancialQA.vue:1)

### 2.3 管理台

已实现页面：

- `/admin/overview`
- `/admin/users`
- `/admin/models`
- `/admin/evaluation`

已实现能力：

- 仪表盘
  - 文档数量、待审风险、高风险数量、启用模型数、近 24h 问答量
  - 近 7 天问答/命中趋势
  - 风险等级分布
  - 文档处理状态分布
  - 最近活动与运行证据列表
- 用户管理
  - 用户列表
  - 角色组筛选
  - 编辑用户角色
- 模型配置
  - 查看 chat / embedding 配置
  - 新增配置
  - 编辑配置
  - 启用/停用配置
  - 连接测试
- 评测结果
  - 查看评测记录
  - 手动触发评测任务

对应代码：

- [frontend/src/components/OpsDashboard.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/OpsDashboard.vue:1)
- [frontend/src/components/AdminUsers.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/AdminUsers.vue:1)
- [frontend/src/components/ModelConfig.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/ModelConfig.vue:1)
- [frontend/src/components/EvaluationResult.vue](/Users/td/code/finmodpro/finmodpro/frontend/src/components/EvaluationResult.vue:1)

## 3. 后端已实现能力

### 3.1 认证与 RBAC

已实现接口：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/admin/users`
- `GET /api/admin/groups`
- `PUT /api/admin/users/<id>/groups`

已实现能力：

- 用户注册、登录
- JWT access token 鉴权
- 当前用户资料查询
- 角色组和权限初始化命令 `seed_rbac`
- 基于 Django `Group` / `Permission` 的 RBAC
- 后台用户角色调整

默认角色：

- `super_admin`
- `admin`
- `member`

权限覆盖范围包含：

- 查看仪表盘
- 查看与上传文档
- 触发入库
- 智能问答
- 风险审核
- 模型配置管理
- 评测查看与触发

对应代码：

- [backend/authentication/controllers/auth_controller.py](/Users/td/code/finmodpro/finmodpro/backend/authentication/controllers/auth_controller.py:1)
- [backend/rbac/services/rbac_service.py](/Users/td/code/finmodpro/finmodpro/backend/rbac/services/rbac_service.py:1)

当前限制：

- 只有 access token，没有 refresh token
- 没有退出登录黑名单、找回密码、邮箱验证码能力

### 3.2 系统概览

已实现接口：

- `GET /api/health`
- `GET /api/dashboard/stats`

已实现能力：

- 服务健康检查
- 管理台统计汇总
- 最近活动聚合
- 文档、风险、检索、评测等维度的数据汇总

对应代码：

- [backend/systemcheck/controllers/health_controller.py](/Users/td/code/finmodpro/finmodpro/backend/systemcheck/controllers/health_controller.py:1)
- [backend/systemcheck/services/dashboard_service.py](/Users/td/code/finmodpro/finmodpro/backend/systemcheck/services/dashboard_service.py:1)

### 3.3 知识库

已实现接口：

- `GET /api/knowledgebase/documents`
- `POST /api/knowledgebase/documents`
- `GET /api/knowledgebase/documents/<id>`
- `POST /api/knowledgebase/documents/<id>/ingest`

已实现能力：

- 文档上传
- 按用户权限控制文档可见性
- 文档详情查询
- 摄取任务入队
- 文档解析
- 文本切块
- 向量写入
- 入库状态与失败信息回传

当前支持的上传类型：

- `txt`
- `pdf`
- `docx`

当前真实处理情况：

- `txt` 已实现解析
- `pdf` 已实现解析，依赖 `pypdf`
- `docx` 上传已放行，但解析尚未实现，触发入库时会失败

对应代码：

- [backend/knowledgebase/controllers/document_controller.py](/Users/td/code/finmodpro/finmodpro/backend/knowledgebase/controllers/document_controller.py:1)
- [backend/knowledgebase/controllers/ingest_controller.py](/Users/td/code/finmodpro/finmodpro/backend/knowledgebase/controllers/ingest_controller.py:1)
- [backend/knowledgebase/services/document_service.py](/Users/td/code/finmodpro/finmodpro/backend/knowledgebase/services/document_service.py:1)
- [backend/knowledgebase/services/parser_service.py](/Users/td/code/finmodpro/finmodpro/backend/knowledgebase/services/parser_service.py:1)
- [backend/knowledgebase/services/chunk_service.py](/Users/td/code/finmodpro/finmodpro/backend/knowledgebase/services/chunk_service.py:1)
- [backend/knowledgebase/services/vector_service.py](/Users/td/code/finmodpro/finmodpro/backend/knowledgebase/services/vector_service.py:1)

### 3.4 RAG 与智能问答

已实现接口：

- `POST /api/rag/retrieval/query`
- `POST /api/chat/ask`
- `POST /api/chat/ask/stream`
- `GET /api/chat/sessions`
- `POST /api/chat/sessions`
- `GET /api/chat/sessions/<id>`

已实现能力：

- 检索召回与重排
- 问答前先从知识库检索引用片段
- 普通问答接口
- SSE 流式问答接口
- 引用依据回传
- 无引用时给出 fallback 提示
- 问答检索日志记录
- 会话创建、历史查询、会话详情查看

当前模型运行时：

- chat provider 支持 `DeepSeek` 与 `Ollama`
- embedding provider 支持 `Ollama`

对应代码：

- [backend/rag/services/retrieval_service.py](/Users/td/code/finmodpro/finmodpro/backend/rag/services/retrieval_service.py:1)
- [backend/chat/controllers/ask_controller.py](/Users/td/code/finmodpro/finmodpro/backend/chat/controllers/ask_controller.py:1)
- [backend/chat/controllers/session_controller.py](/Users/td/code/finmodpro/finmodpro/backend/chat/controllers/session_controller.py:1)
- [backend/chat/services/ask_service.py](/Users/td/code/finmodpro/finmodpro/backend/chat/services/ask_service.py:1)
- [backend/chat/services/session_service.py](/Users/td/code/finmodpro/finmodpro/backend/chat/services/session_service.py:1)
- [backend/llm/services/runtime_service.py](/Users/td/code/finmodpro/finmodpro/backend/llm/services/runtime_service.py:1)

### 3.5 风险抽取、审核与报告

已实现接口：

- `GET /api/risk/events`
- `POST /api/risk/events/<id>/review`
- `POST /api/risk/reports/company`
- `POST /api/risk/reports/time-range`
- `POST /api/risk/documents/<id>/extract`
- `POST /api/risk/documents/extract-batch`

已实现能力：

- 基于文档 chunk 的风险事件抽取
- 单文档抽取与批量抽取
- 风险事件列表查询
- 人工审核风险事件
- 按公司生成风险报告
- 按时间区间生成风险报告
- 报告中保留来源事件、文档和风险统计元数据

对应代码：

- [backend/risk/controllers/list_controller.py](/Users/td/code/finmodpro/finmodpro/backend/risk/controllers/list_controller.py:1)
- [backend/risk/controllers/review_controller.py](/Users/td/code/finmodpro/finmodpro/backend/risk/controllers/review_controller.py:1)
- [backend/risk/controllers/report_controller.py](/Users/td/code/finmodpro/finmodpro/backend/risk/controllers/report_controller.py:1)
- [backend/risk/controllers/extract_controller.py](/Users/td/code/finmodpro/finmodpro/backend/risk/controllers/extract_controller.py:1)
- [backend/risk/controllers/batch_extract_controller.py](/Users/td/code/finmodpro/finmodpro/backend/risk/controllers/batch_extract_controller.py:1)
- [backend/risk/services/extraction_service.py](/Users/td/code/finmodpro/finmodpro/backend/risk/services/extraction_service.py:1)
- [backend/risk/services/report_service.py](/Users/td/code/finmodpro/finmodpro/backend/risk/services/report_service.py:1)

### 3.6 模型配置与评测

已实现接口：

- `GET /api/ops/model-configs`
- `POST /api/ops/model-configs`
- `PATCH /api/ops/model-configs/<id>`
- `PATCH /api/ops/model-configs/<id>/activation`
- `POST /api/ops/model-configs/test-connection`
- `GET /api/ops/evaluations`
- `POST /api/ops/evaluations`

已实现能力：

- 模型配置增改查
- 模型启停
- 连接测试
- 评测记录查询
- 触发基础 smoke 评测

评测当前实现特点：

- 属于基础 smoke evaluation
- 使用内置样例计算 QA 准确率、抽取准确率和平均延迟
- 不是完整离线评测平台

对应代码：

- [backend/llm/controllers/model_config_controller.py](/Users/td/code/finmodpro/finmodpro/backend/llm/controllers/model_config_controller.py:1)
- [backend/llm/controllers/evaluation_controller.py](/Users/td/code/finmodpro/finmodpro/backend/llm/controllers/evaluation_controller.py:1)
- [backend/llm/services/evaluation_service.py](/Users/td/code/finmodpro/finmodpro/backend/llm/services/evaluation_service.py:1)

## 4. 当前可跑通的主链路

基于当前仓库，已经具备代码层面的主流程闭环：

1. 用户注册或登录
2. 获取 RBAC 权限并进入工作区/管理台
3. 上传知识文档
4. 触发文档入库
5. 基于知识库执行问答
6. 从文档中抽取风险事件
7. 审核风险事件
8. 生成公司或时间区间风险报告

仓库中已有相应演示脚本说明：

- [docs/demo-script.md](/Users/td/code/finmodpro/finmodpro/docs/demo-script.md:1)

## 5. 当前已知限制

以下内容不应被描述为“已经完整实现”：

- 独立历史会话页面前端未完成数据加载闭环
- `docx` 解析尚未实现
- 高级能力依赖外部模型与向量服务时，仍需要额外环境配置
- 认证体系仍是轻量 JWT access token 方案
- 评测能力目前是基础 smoke 评测，不是完整评测工作流

## 6. 结论

当前 `finmodpro` 已经不是“只有登录和静态页面”的演示仓库，而是具备以下真实能力的可运行系统：

- 认证与 RBAC
- 知识库上传、入库与状态跟踪
- 基于知识库的检索增强问答
- 风险事件抽取、审核与报告生成
- 管理台仪表盘、用户角色管理、模型配置和基础评测

但它仍处于“核心链路已形成，部分边角能力尚待补齐”的阶段，尤其是在独立历史页、`docx` 解析和部分依赖服务的落地配置方面。
