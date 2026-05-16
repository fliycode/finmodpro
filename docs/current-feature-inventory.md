# FinModPro 当前已实现功能清单

更新日期：2026-05-16

本文档基于当前仓库代码整理，目标是说明"已经实现并可在代码中验证"的能力，而不是产品规划。范围覆盖 `frontend/` 与 `backend/` 当前主干代码。

## 1. 项目当前形态

当前项目是一个前后端分离的金融知识与风险分析系统：

- 前端：Vue 3 + Vite，提供登录页、工作区和管理台。
- 后端：Django 5 + DRF，已挂载认证、RBAC、知识库、RAG、聊天、风险分析、模型配置、评测、运维监控和系统概览接口。
- LLM 网关：LiteLLM（端口 4000）+ Langfuse 可观测性
- 向量存储：Milvus（通过 LlamaIndex 抽象层）
- 嵌入模型：DashScope（通过 LlamaIndex 适配器）
- 生产部署：Docker Compose（10 个服务）

代码入口：

- 前端路由：`frontend/src/router/routes.js`
- 后端总路由：`backend/config/urls.py`

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

- `frontend/src/views/auth/AuthView.vue`
- `frontend/src/api/auth.js`

### 2.2 工作区

已实现页面：

- `/workspace/qa`
- `/workspace/knowledge`
- `/workspace/knowledge/documents/:id`
- `/workspace/history`
- `/workspace/risk`
- `/workspace/profile`

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
- 历史会话页面
  - 会话列表加载
  - 会话详情回看
  - 会话搜索/筛选
- 风险提取页面
  - 选择知识文档进行风险抽取
  - 结构化风险事件展示
  - 裁决丰富（adjudication）结果展示
  - 风险报告导出（xlsx 格式）
- 个人中心页面
  - 个人资料查看与编辑
  - 权限信息展示

对应代码：

- `frontend/src/views/workspace/WorkspaceQaView.vue`
- `frontend/src/components/FinancialQA.vue`
- `frontend/src/components/KnowledgeBase.vue`
- `frontend/src/views/workspace/WorkspaceRiskView.vue`
- `frontend/src/components/RiskSummary.vue`
- `frontend/src/views/workspace/WorkspaceHistoryView.vue`
- `frontend/src/views/workspace/WorkspaceProfileView.vue`

### 2.3 管理台

已实现页面：

- `/admin/overview`
- `/admin/users`
- `/admin/roles`
- `/admin/knowledge`
- `/admin/knowledge/documents/:id`
- `/admin/llm/models`
- `/admin/llm/logs`
- `/admin/llm/usage`
- `/admin/llm/knowledge`
- `/admin/monitoring`
- `/admin/notifications`
- `/admin/cleaning`
- `/admin/audit-logs`

已实现能力：

- 数据看板
  - 文档数量、待审风险、高风险数量、启用模型数、近 24h 问答量
  - 近 7 天问答/命中趋势
  - 风险等级分布
  - 文档处理状态分布
  - 最近活动与运行证据列表
- 用户管理
  - 用户列表
  - 角色组筛选
  - 编辑用户角色
- 角色管理
  - 角色列表
  - 成员归属管理
  - 权限矩阵展示
- 知识库管理（管理员视角）
  - 知识资产总览
  - 入库链路状态
  - 存储和向量资源指标
  - 文档详情查看
- 模型管理（Gateway Ops）
  - 模型总览：启停、基础信息、调用概况
  - 模型日志：调用记录、错误分布、链路细节
  - 用量统计：按模型和时间窗口追踪调用量、Token 与成本
  - 知识库解析与入库链路
- 系统监控
  - 系统资源状态
  - 服务健康检查
  - 指标时间序列展示
- 告警中心
  - 告警规则管理
  - 告警事件列表
  - 站内告警通知
  - 告警确认处理
- 数据清洗
  - 清洗规则管理
- 操作日志
  - 用户关键操作记录
  - 管理员操作记录
  - 日志搜索与筛选

对应代码：

- `frontend/src/components/OpsDashboard.vue`
- `frontend/src/components/AdminUsers.vue`
- `frontend/src/components/ModelConfig.vue`
- `frontend/src/components/LlmModelOverview.vue`
- `frontend/src/views/admin/AdminAuditLogsView.vue`
- `frontend/src/views/admin/AdminAlertNotificationsView.vue`
- `frontend/src/views/admin/AdminMonitoringView.vue`

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
- JWT access token 鉴权（HTTP-only cookie 存储 refresh token）
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
- 系统监控查看
- 告警管理
- 操作日志查看
- 角色管理

对应代码：

- `backend/authentication/controllers/auth_controller.py`
- `backend/rbac/services/rbac_service.py`

### 3.2 系统概览与审计

已实现接口：

- `GET /api/health`
- `GET /api/dashboard/stats`
- `GET /api/audit/logs`

已实现能力：

- 服务健康检查
- 管理台统计汇总
- 最近活动聚合
- 文档、风险、检索、评测等维度的数据汇总
- 操作日志记录与查询

对应代码：

- `backend/systemcheck/controllers/health_controller.py`
- `backend/systemcheck/services/dashboard_service.py`
- `backend/systemcheck/controllers/audit_controller.py`

### 3.3 知识库

已实现接口：

- `GET /api/knowledgebase/datasets`
- `POST /api/knowledgebase/datasets`
- `GET /api/knowledgebase/datasets/<id>`
- `PATCH /api/knowledgebase/datasets/<id>`
- `GET /api/knowledgebase/documents`
- `POST /api/knowledgebase/documents`
- `GET /api/knowledgebase/documents/<id>`
- `POST /api/knowledgebase/documents/<id>/ingest`
- `GET /api/knowledgebase/documents/<id>/chunks`
- `GET /api/knowledgebase/documents/<id>/sections`

已实现能力：

- 数据集管理
  - 创建数据集
  - 数据集列表查询
  - 数据集详情与更新
  - 文档归属到指定数据集
- 文档管理
  - 文档上传
  - 按用户权限控制文档可见性
  - 文档详情查询
  - 文档版本管理
  - 来源信息记录
- 摄取任务
  - 摄取任务入队
  - 文档解析
  - 文本切块
  - 向量写入
  - 入库状态与失败信息回传
- 文档分块
  - 分块列表查询
  - 段落级分块查询
- 数据清洗
  - 清洗规则管理
  - 清洗结果记录

当前支持的上传类型：

- `txt`
- `pdf`（依赖 `pypdf`）
- `docx`

对应代码：

- `backend/knowledgebase/controllers/document_controller.py`
- `backend/knowledgebase/controllers/ingest_controller.py`
- `backend/knowledgebase/services/document_service.py`
- `backend/knowledgebase/services/parser_service.py`
- `backend/knowledgebase/services/chunk_service.py`
- `backend/knowledgebase/services/vector_service.py`

### 3.4 RAG 与智能问答

已实现接口：

- `POST /api/rag/retrieval/query`
- `POST /api/chat/ask`
- `POST /api/chat/ask/stream`
- `GET /api/chat/sessions`
- `POST /api/chat/sessions`
- `GET /api/chat/sessions/<id>`

已实现能力：

- **LlamaIndex 统一检索架构**
  - LlamaIndex-over-Milvus 统一向量存储
  - LlamaIndex 嵌入适配器（DashScope + Redis 缓存）
  - LlamaIndex LLM 适配器
  - 混合检索：MySQL 全文 + 关键词回退 + RRF 融合
- 检索召回与重排
- 问答前先从知识库检索引用片段
- 普通问答接口
- SSE 流式问答接口
- 引用依据回传
- 无引用时给出 fallback 提示
- 问答检索日志记录
- 会话创建、历史查询、会话详情查看
- 记忆系统
  - MemoryItem 存储
  - 记忆证据关联
  - 记忆操作日志

当前模型运行时：

- chat provider：DeepSeek、Ollama、OpenAI 兼容（通过 LiteLLM）
- embedding provider：DashScope、Ollama
- LLM 网关：LiteLLM（端口 4000）
- 可观测性：Langfuse

对应代码：

- `backend/rag/services/llamaindex_store_service.py`
- `backend/rag/services/llamaindex_embedding_adapter.py`
- `backend/rag/services/llamaindex_llm_adapter.py`
- `backend/rag/services/retrieval_service.py`
- `backend/rag/services/rerank_service.py`
- `backend/chat/controllers/ask_controller.py`
- `backend/chat/controllers/session_controller.py`
- `backend/chat/services/ask_service.py`
- `backend/chat/services/session_service.py`
- `backend/chat/services/memory_service.py`
- `backend/llm/services/runtime_service.py`

### 3.5 风险抽取、审核与报告

已实现接口：

- `GET /api/risk/analytics/overview`
- `GET /api/risk/events`
- `POST /api/risk/events/<id>/review`
- `POST /api/risk/reports/company`
- `POST /api/risk/reports/<id>/export`
- `POST /api/risk/reports/time-range`
- `POST /api/risk/sentiment/analyze`
- `POST /api/risk/documents/<id>/extract`
- `POST /api/risk/documents/extract-batch`
- `GET /api/risk/tasks`
- `GET /api/risk/tasks/<id>`

已实现能力：

- **结构化风险抽取管道**
  - 基于文档 chunk 的风险事件抽取
  - 单文档抽取与批量抽取
  - JSON 结构化输出（DeepSeek 兼容）
  - 跨 chunk 去重
  - 中文字段翻译
- **裁决丰富（Adjudication）**
  - 自动裁决建议
  - 风险等级评估
  - 置信度评分
- **验证流程（Verification）**
  - 风险事件验证
  - 交叉引用验证
- **分析能力（Analytics）**
  - 风险概览统计
  - 风险类型分布
  - 风险等级分布
- 风险事件列表查询
- 人工审核风险事件
- 按公司生成风险报告
- 按时间区间生成风险报告
- 报告导出（xlsx 格式）
- 报告中保留来源事件、文档和风险统计元数据
- 任务管理
  - 抽取任务列表查询
  - 任务状态跟踪
- 情感分析
  - 文本情感倾向分析
  - 风险倾向识别

对应代码：

- `backend/risk/services/extraction_service.py`
- `backend/risk/services/adjudication_service.py`
- `backend/risk/services/verification_service.py`
- `backend/risk/services/analytics_service.py`
- `backend/risk/services/report_service.py`
- `backend/risk/services/task_service.py`
- `backend/risk/services/sentiment_service.py`
- `backend/risk/controllers/report_controller.py`
- `backend/risk/controllers/extract_controller.py`

### 3.6 模型配置与评测

已实现接口：

- `GET /api/ops/model-configs`
- `POST /api/ops/model-configs`
- `PATCH /api/ops/model-configs/<id>`
- `PATCH /api/ops/model-configs/<id>/activation`
- `POST /api/ops/model-configs/test-connection`
- `GET /api/ops/evaluations`
- `POST /api/ops/evaluations`
- `GET /api/llm/summary`
- `GET /api/llm/models`
- `GET /api/llm/models/<id>`
- `GET /api/llm/gateway/summary`
- `GET /api/llm/gateway/logs`
- `GET /api/llm/gateway/logs/summary`
- `GET /api/llm/gateway/traces/<trace_id>`
- `GET /api/llm/gateway/errors`
- `GET /api/llm/gateway/costs/summary`
- `GET /api/llm/gateway/costs/timeseries`
- `GET /api/llm/gateway/costs/models`

已实现能力：

- 模型配置增改查
- 模型启停
- 连接测试
- 评测记录查询
- 触发基础 smoke 评测
- **LLM 控制台**
  - 模型总览
  - 模型详情
  - 调用汇总
- **Gateway 可观测性**
  - 调用日志查询
  - 日志汇总统计
  - 链路追踪
  - 错误分布
- **用量与成本统计**
  - 成本汇总
  - 成本时间序列
  - 按模型成本分布
- **微调管理**
  - 微调运行服务器配置
  - 微调任务记录
  - 微调数据导出
  - 微调回调处理
  - 微调调度

评测当前实现特点：

- 属于基础 smoke evaluation
- 使用内置样例计算 QA 准确率、抽取准确率和平均延迟
- 不是完整离线评测平台

对应代码：

- `backend/llm/controllers/model_config_controller.py`
- `backend/llm/controllers/evaluation_controller.py`
- `backend/llm/services/evaluation_service.py`
- `backend/llm/services/console_query_service.py`
- `backend/llm/services/model_usage_query_service.py`
- `backend/llm/services/model_invocation_log_service.py`
- `backend/llm/services/fine_tune_service.py`
- `backend/llm/services/fine_tune_export_service.py`
- `backend/llm/services/fine_tune_runner_client.py`

### 3.7 运维监控与告警

已实现接口：

- `GET /api/ops/monitoring/status`
- `GET /api/ops/monitoring/metrics`
- `GET /api/ops/alerts/rules`
- `POST /api/ops/alerts/rules`
- `PATCH /api/ops/alerts/rules/<id>`
- `DELETE /api/ops/alerts/rules/<id>`
- `GET /api/ops/alerts/events`
- `POST /api/ops/alerts/events/<id>/acknowledge`

已实现能力：

- **系统监控**
  - 系统状态查询
  - 指标时间序列（CPU、内存、磁盘等）
  - 服务健康检查
- **告警管理**
  - 告警规则创建、查询、更新、删除
  - 告警事件列表
  - 告警确认处理
  - 告警引擎服务
- **指标收集**
  - 系统指标采集
  - 指标存储与查询

对应代码：

- `backend/ops/services/monitoring_query_service.py`
- `backend/ops/services/alert_engine_service.py`
- `backend/ops/services/metrics_collector_service.py`
- `backend/ops/models.py`（SystemMetric、AlertRule、AlertEvent）

## 4. 当前可跑通的主链路

基于当前仓库，已经具备代码层面的主流程闭环：

1. 用户注册或登录
2. 获取 RBAC 权限并进入工作区/管理台
3. 创建数据集并上传知识文档
4. 触发文档入库（LlamaIndex-over-Milvus）
5. 基于知识库执行问答（混合检索 + RRF 融合）
6. 从文档中抽取风险事件（结构化输出 + 裁决丰富）
7. 审核风险事件
8. 生成公司或时间区间风险报告
9. 导出风险报告（xlsx 格式）
10. 查看系统监控与告警
11. 查看 LLM 调用日志与成本统计

仓库中已有相应演示脚本说明：

- `docs/demo-script.md`

## 5. 当前已知限制

以下内容不应被描述为"已经完整实现"：

- `docx` 解析尚未实现
- 高级能力依赖外部模型与向量服务时，仍需要额外环境配置
- 评测能力目前是基础 smoke 评测，不是完整评测工作流
- 微调任务需要外部脚本执行，平台内仅管理记录

## 6. 结论

当前 `finmodpro` 已经不是"只有登录和静态页面"的演示仓库，而是具备以下真实能力的可运行系统：

- 认证与 RBAC
- 数据集与知识库管理
- LlamaIndex-over-Milvus 统一检索架构
- 基于知识库的检索增强问答（混合检索 + RRF 融合）
- 结构化风险事件抽取、裁决丰富、审核与报告生成
- 管理台仪表盘、用户角色管理、模型配置和基础评测
- LLM 网关可观测性（LiteLLM + Langfuse）
- 系统监控与告警管理
- 操作日志审计

项目已经从"核心链路已形成"进入"平台能力基本完整"的阶段，具备了金融风控大模型应用平台的核心功能骨架。
