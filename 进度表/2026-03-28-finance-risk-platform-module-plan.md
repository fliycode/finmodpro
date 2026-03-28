# 金融风控大模型平台按模块开发计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Django + Vue 登录骨架上，按模块完成金融风控领域大模型平台 MVP，形成“知识库入库 -> RAG 问答 -> 风险抽取 -> 风险报告”的可演示闭环。

**Architecture:** 平台采用前后端分离。后端使用 Django + DRF 提供业务 API，Celery + Redis 处理异步入库与抽取任务，`llm` 适配层隔离 LangChain、Ollama 与 Milvus。前端使用 Vue 3 + Router + Pinia，按“知识库 / 问答 / 风险 / 报告 / 模型配置”模块组织页面。

**Tech Stack:** Django, Django REST Framework, MySQL, Redis, Celery, Vue 3, Vue Router, Pinia, Axios, LangChain, Ollama, pymilvus, pytest, vitest

---

## 总体说明

- 当前项目已存在基础登录框架，本计划默认复用，不重写登录主流程。
- 本计划按 **模块** 拆分，而不是按周拆分。你可以按模块推进，也可以按模块合并成周计划。
- LoRA 微调与系统评测不作为 MVP 阻塞项，放在最后一个增强模块。
- 每个模块都要求形成 **可运行、可截图、可验收** 的中间成果。

## 推荐实施顺序

1. 模块 A：项目基线与公共能力
2. 模块 B：用户与权限
3. 模块 C：知识库与文档管理
4. 模块 D：文档入库异步链路
5. 模块 E：模型接入与 LLM 适配层
6. 模块 F：智能问答与 RAG
7. 模块 G：风险抽取与审核
8. 模块 H：风险报告与仪表盘
9. 模块 I：模型配置与基础评测
10. 模块 J：联调、部署、演示与论文材料

---

## 模块 A：项目基线与公共能力

**目标：** 把后端 app 骨架、前端主布局、统一响应格式、健康检查、基础环境配置跑通。

**后端文件：**
- Create: `backend/apps/common/views.py`
- Create: `backend/apps/common/response.py`
- Create: `backend/apps/common/exceptions.py`
- Modify: `backend/config/settings/base.py`
- Modify: `backend/config/urls.py`
- Create: `backend/config/celery.py`
- Create: `backend/tests/apps/common/test_health_api.py`

**前端文件：**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/layouts/AppLayout.vue`
- Create: `frontend/src/views/DashboardView.vue`
- Create: `frontend/src/utils/request.ts`

**Checklist：**
- [ ] 整理现有登录框架与目录，确认哪些文件复用、哪些新增。
- [ ] 配置 Django 基础 settings：DRF、JWT、MySQL、Redis、媒体文件目录。
- [ ] 新增 `/api/health/` 健康检查接口。
- [ ] 统一后端响应结构：`{code, message, data}`。
- [ ] 配置 Axios 实例与 token 拦截器。
- [ ] 搭建前端主布局：左侧菜单 + 顶部栏 + 内容区。
- [ ] 新建首页仪表盘占位页。
- [ ] 编写健康检查测试与前端路由烟雾检查。

**验收标准：**
- 登录后可以进入主布局。
- `GET /api/health/` 返回 200。
- 前后端可本地同时启动。

---

## 模块 B：用户与权限

**目标：** 在现有登录基础上补齐“当前用户信息、角色识别、页面访问控制、接口访问控制”。

**后端文件：**
- Modify: `backend/apps/accounts/models.py`
- Modify: `backend/apps/accounts/views.py`
- Create: `backend/apps/accounts/serializers.py`
- Create: `backend/apps/accounts/permissions.py`
- Create: `backend/tests/apps/accounts/test_auth_api.py`

**前端文件：**
- Create: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/api/auth.ts`

**Checklist：**
- [ ] 在用户表中补齐 `real_name`、`role`、`status` 字段。
- [ ] 新增 `/api/users/me` 接口返回当前登录用户信息。
- [ ] 实现管理员与分析师两类角色。
- [ ] 增加前端路由守卫：未登录跳登录页，无权限跳 403 或首页。
- [ ] 在菜单中按角色隐藏不需要的入口。
- [ ] 编写登录态持久化与退出逻辑。
- [ ] 编写权限相关单元测试。

**验收标准：**
- 页面可根据角色显示不同菜单。
- 未授权用户无法访问受保护接口。
- 刷新页面后登录态不丢失。

---

## 模块 C：知识库与文档管理

**目标：** 完成知识库、文档元数据、上传与状态展示的业务闭环。

**后端文件：**
- Create: `backend/apps/kb/models.py`
- Create: `backend/apps/kb/serializers.py`
- Create: `backend/apps/kb/views.py`
- Create: `backend/apps/kb/urls.py`
- Create: `backend/tests/apps/kb/test_kb_api.py`
- Create: `backend/tests/apps/kb/test_document_api.py`

**前端文件：**
- Create: `frontend/src/api/kb.ts`
- Create: `frontend/src/views/kb/KnowledgeBaseListView.vue`
- Create: `frontend/src/views/kb/DocumentDetailView.vue`
- Create: `frontend/src/components/kb/UploadDialog.vue`
- Create: `frontend/src/stores/kb.ts`

**Checklist：**
- [ ] 新建 `knowledge_base` 表。
- [ ] 新建 `document` 表。
- [ ] 实现知识库列表、详情、新建、删除接口。
- [ ] 实现文档上传接口，支持 PDF/TXT。
- [ ] 保存文档基础信息：公司名、报告期、文件路径、解析状态。
- [ ] 在前端实现知识库列表页。
- [ ] 在前端实现文档上传弹窗与文档详情页。
- [ ] 显示文档当前状态：pending / parsing / parsed / failed。
- [ ] 编写知识库与上传接口测试。

**验收标准：**
- 能创建知识库。
- 能上传 PDF 并看到文档详情页。
- 文档状态能在页面上显示。

---

## 模块 D：文档入库异步链路

**目标：** 完成“解析 -> 切块 -> 向量化 -> 向量入库 -> 任务状态更新”的异步处理闭环。

**后端文件：**
- Create: `backend/apps/kb/tasks.py`
- Create: `backend/apps/kb/services/parser_service.py`
- Create: `backend/apps/kb/services/chunk_service.py`
- Create: `backend/apps/kb/services/vector_service.py`
- Modify: `backend/apps/kb/models.py`
- Create: `backend/tests/apps/kb/test_ingestion_pipeline.py`

**Checklist：**
- [ ] 新建 `document_chunk` 表。
- [ ] 新建 `ingestion_task` 表。
- [ ] 配置 Celery 与 Redis。
- [ ] 实现 PDF 文本解析服务。
- [ ] 实现固定长度 + overlap 的切块逻辑。
- [ ] 实现 embedding 生成逻辑。
- [ ] 实现 Milvus collection 初始化与向量写入。
- [ ] 建立 `document_chunk.vector_id` 与 Milvus 主键映射。
- [ ] 实现任务进度更新与失败原因记录。
- [ ] 在文档详情页增加任务状态轮询。
- [ ] 编写入库链路测试（至少覆盖成功与失败两类）。

**验收标准：**
- 文档上传后可触发异步任务。
- 文档状态能从 `pending` 走到 `parsed` 或 `failed`。
- 数据库中能看到 chunk 记录，Milvus 中能查到向量。

---

## 模块 E：模型接入与 LLM 适配层

**目标：** 建立统一的本地模型接入方式，隔离后续模型替换与参数调整。

**后端文件：**
- Create: `backend/apps/llm/models.py`
- Create: `backend/apps/llm/providers/base.py`
- Create: `backend/apps/llm/providers/ollama_provider.py`
- Create: `backend/apps/llm/services/model_provider.py`
- Create: `backend/apps/llm/prompts/qa_prompt.py`
- Create: `backend/apps/llm/prompts/extraction_prompt.py`
- Create: `backend/apps/llm/prompts/report_prompt.py`
- Create: `backend/tests/apps/llm/test_provider_api.py`

**Checklist：**
- [ ] 新建 `model_config` 表。
- [ ] 抽象 `chat` 与 `embedding` 两类 provider 接口。
- [ ] 接入 Ollama chat 模型。
- [ ] 接入 Ollama embedding 模型。
- [ ] 支持从数据库读取当前启用模型配置。
- [ ] 统一模型调用超时、异常和日志输出。
- [ ] 把 Prompt 模板从业务代码中抽离到 `prompts/`。
- [ ] 编写 provider 可用性测试与错误处理测试。

**验收标准：**
- 后端可通过统一接口调用本地聊天模型与 embedding 模型。
- 替换模型名或 endpoint 时不需要改业务接口。

---

## 模块 F：智能问答与 RAG

**目标：** 完成会话管理、检索增强问答、来源回显与检索日志记录。

**后端文件：**
- Create: `backend/apps/chat/models.py`
- Create: `backend/apps/chat/views.py`
- Create: `backend/apps/chat/serializers.py`
- Create: `backend/apps/chat/services/retrieval_service.py`
- Create: `backend/apps/chat/services/qa_service.py`
- Create: `backend/apps/llm/chains/qa_chain.py`
- Create: `backend/tests/apps/chat/test_chat_api.py`

**前端文件：**
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/views/chat/ChatView.vue`
- Create: `frontend/src/components/chat/SourceCard.vue`
- Create: `frontend/src/stores/chat.ts`

**Checklist：**
- [ ] 新建 `chat_session`、`chat_message`、`retrieval_log` 表。
- [ ] 实现会话创建、消息查询、发送消息接口。
- [ ] 实现 query 预处理与检索封装。
- [ ] 先做向量检索，再扩展成关键词 + 向量混合检索。
- [ ] 实现基于 Top-K 片段的 2-step RAG 问答链。
- [ ] 返回答案、来源文档、页码、命中片段、耗时。
- [ ] 在数据库记录检索结果与分数。
- [ ] 前端实现聊天页面与来源侧栏。
- [ ] 在来源卡片上显示文档名、页码、片段摘要。
- [ ] 编写问答接口测试与前端页面联调测试。

**验收标准：**
- 用户可以选择知识库发起提问。
- 页面返回答案和证据来源，而不是纯文本回复。
- 数据库能查到会话消息和检索日志。

---

## 模块 G：风险抽取与审核

**目标：** 把模型输出从“自由文本”改成结构化风险事件，并提供人工审核流转。

**后端文件：**
- Create: `backend/apps/risk/models.py`
- Create: `backend/apps/risk/views.py`
- Create: `backend/apps/risk/serializers.py`
- Create: `backend/apps/risk/tasks.py`
- Create: `backend/apps/risk/services/extraction_service.py`
- Create: `backend/apps/llm/schemas/risk_event_schema.py`
- Create: `backend/apps/llm/chains/extract_chain.py`
- Create: `backend/tests/apps/risk/test_risk_api.py`

**前端文件：**
- Create: `frontend/src/api/risk.ts`
- Create: `frontend/src/views/risk/RiskEventListView.vue`
- Create: `frontend/src/components/risk/RiskReviewTable.vue`

**Checklist：**
- [ ] 新建 `risk_event` 表。
- [ ] 定义风险事件结构：公司名、风险类型、风险等级、事件时间、摘要、证据文本、置信度、审核状态。
- [ ] 实现批量抽取任务入口。
- [ ] 使用结构化输出 schema 约束模型返回 JSON。
- [ ] 将抽取结果落库，并保存 `document_id`、`chunk_id` 映射。
- [ ] 实现风险事件列表筛选接口。
- [ ] 实现审核接口：approved / rejected。
- [ ] 前端实现事件表格、筛选项、审核操作。
- [ ] 编写抽取任务与审核接口测试。

**验收标准：**
- 可以从指定文档触发抽取。
- 页面中能看到结构化风险事件，而不是一大段自然语言。
- 审核结果会持久化到数据库。

---

## 模块 H：风险报告与仪表盘

**目标：** 基于已审核风险事件生成风险摘要与报告页面，而不是直接对整篇文档做长文本总结。

**后端文件：**
- Create: `backend/apps/report/models.py`
- Create: `backend/apps/report/views.py`
- Create: `backend/apps/report/serializers.py`
- Create: `backend/apps/report/tasks.py`
- Create: `backend/apps/report/services/report_service.py`
- Create: `backend/apps/llm/chains/report_chain.py`
- Create: `backend/tests/apps/report/test_report_api.py`

**前端文件：**
- Create: `frontend/src/api/report.ts`
- Create: `frontend/src/views/report/ReportView.vue`
- Create: `frontend/src/components/report/ReportSummaryCard.vue`
- Modify: `frontend/src/views/DashboardView.vue`

**Checklist：**
- [ ] 新建 `risk_report` 表。
- [ ] 实现按公司与按时间区间生成报告接口。
- [ ] 按风险事件聚合统计风险类型分布。
- [ ] 调用报告生成链输出摘要。
- [ ] 保存报告内容与来源列表。
- [ ] 前端实现报告页。
- [ ] 在首页仪表盘增加风险事件数、待审核数、最近报告等卡片。
- [ ] 编写报告生成接口测试。

**验收标准：**
- 可以基于风险事件生成报告。
- 首页能看到基础统计指标。
- 报告页面包含摘要、来源与风险类别分布。

---

## 模块 I：模型配置与基础评测

**目标：** 给平台补齐“模型切换、Prompt 参数、简单评测结果展示”，为后续微调实验留接口。

**后端文件：**
- Modify: `backend/apps/llm/models.py`
- Create: `backend/apps/eval/models.py`
- Create: `backend/apps/eval/views.py`
- Create: `backend/apps/eval/serializers.py`
- Create: `backend/apps/eval/services/evaluator.py`
- Create: `backend/tests/apps/eval/test_eval_api.py`

**前端文件：**
- Create: `frontend/src/api/model.ts`
- Create: `frontend/src/views/model/ModelConfigView.vue`

**Checklist：**
- [ ] 新建 `eval_record` 表。
- [ ] 实现模型配置列表、启停、参数更新接口。
- [ ] 实现 Prompt 模板查看/编辑接口。
- [ ] 支持触发基础评测任务（问答正确性、抽取正确率、平均耗时）。
- [ ] 在页面展示至少 1 组评测结果。
- [ ] 为 LoRA 微调前后对比预留 `remark` 或版本字段。
- [ ] 编写模型配置与评测接口测试。

**验收标准：**
- 页面可切换当前启用模型。
- 可查看一组评测结果。
- 后续接微调模型时只需要新增配置，不需要改业务流程。

---

## 模块 J：联调、部署、演示与论文材料

**目标：** 让系统具备稳定演示能力，并沉淀答辩可直接使用的截图、流程、指标与说明文档。

**文件：**
- Create: `README.md`
- Create: `backend/.env.example`
- Create: `frontend/.env.example`
- Create: `docs/demo-script.md`
- Create: `docs/deploy-local.md`
- Create: `docs/test-report.md`

**Checklist：**
- [ ] 编写本地启动文档：MySQL、Redis、Milvus、Ollama、Django、Vue。
- [ ] 整理 `.env.example`。
- [ ] 完成前后端联调并修复主要报错。
- [ ] 准备 1 套稳定演示数据。
- [ ] 录制或整理完整演示路径：登录 -> 上传文档 -> 问答 -> 抽取 -> 审核 -> 报告。
- [ ] 输出测试报告：接口测试、页面联调、问题清单。
- [ ] 截图论文中要用的页面与关键流程图。

**验收标准：**
- 新机器能按文档启动。
- 平台具备可复现的演示流程。
- 论文所需界面截图与指标表已经准备好。

---

## 建议里程碑映射

### P0（必须先做）
- 模块 A：项目基线与公共能力
- 模块 B：用户与权限
- 模块 C：知识库与文档管理
- 模块 D：文档入库异步链路
- 模块 E：模型接入与 LLM 适配层
- 模块 F：智能问答与 RAG

### P1（答辩亮点）
- 模块 G：风险抽取与审核
- 模块 H：风险报告与仪表盘

### P2（增强项）
- 模块 I：模型配置与基础评测
- 模块 J：联调、部署、演示与论文材料

## 建议每次提交的 commit 粒度

- `feat(common): add health api and unified response`
- `feat(accounts): add me api and role guard`
- `feat(kb): add knowledge base and document upload`
- `feat(kb): add ingestion pipeline with celery`
- `feat(llm): add ollama chat and embedding provider`
- `feat(chat): add rag chat with source tracking`
- `feat(risk): add structured risk extraction and review`
- `feat(report): add report generation and dashboard cards`
- `feat(eval): add model config and evaluation records`
- `docs: add demo script and local deployment guide`

## 自查结果

### 1. 规格覆盖检查
- 平台骨架：模块 A、B 覆盖。
- 知识库与文档：模块 C、D 覆盖。
- 问答链路：模块 E、F 覆盖。
- 风险抽取与审核：模块 G 覆盖。
- 风险报告：模块 H 覆盖。
- 模型配置与评测：模块 I 覆盖。
- 演示、部署、论文材料：模块 J 覆盖。

### 2. 占位符检查
- 已避免 TODO / TBD / “后续实现” 这类占位符。
- 评测与 LoRA 被明确归到增强模块，不阻塞 MVP。

### 3. 一致性检查
- 所有业务链路均基于统一的 `knowledge_base -> document -> chunk -> llm/risk/report` 数据流。
- 所有模块遵循统一的目录与命名方式。

