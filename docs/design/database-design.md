# FinModPro 数据库设计

本文档按当前 Django 模型与完整接入 LightRAG 后的系统形态整理。MySQL 保存 FinModPro 业务数据，Milvus 保存向量索引，Neo4j 保存 LightRAG 生成的实体关系图谱。

## 1. 数据存储划分

| 存储 | 作用 |
|---|---|
| MySQL | 用户、权限、知识库文档、chunk、问答会话、风险事件、模型配置、审计日志 |
| Milvus | 文档 chunk、section chunk、实体、关系等向量索引 |
| Neo4j | LightRAG 生成的实体节点、关系边、图谱查询数据 |
| Redis | 缓存、Celery broker、Celery result backend |
| 文件存储 | 上传原始文件、媒体文件、导出文件 |

## 2. 用户与权限表

系统使用 Django 内置认证表。

| 表名 | 说明 |
|---|---|
| `auth_user` | 用户账号、密码哈希、邮箱、启用状态、管理员状态 |
| `auth_group` | 角色/用户组 |
| `auth_permission` | 权限点 |
| `auth_user_groups` | 用户与角色多对多关系 |
| `auth_group_permissions` | 角色与权限多对多关系 |
| `auth_user_user_permissions` | 用户直接权限 |

主要关系：

- 一个用户可以属于多个角色。
- 一个角色可以绑定多个权限。
- 管理端通过用户角色和权限判断是否允许访问后台、知识库、模型中台和 LightRAG 管理入口。

## 3. 知识库表

### `knowledgebase_dataset`

数据集表，用于对文档进行分组管理。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `name` | CharField | 数据集名称，唯一 |
| `description` | TextField | 数据集描述 |
| `owner_id` | FK -> `auth_user` | 数据集负责人 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `knowledgebase_document`

文档主表，保存上传文件、解析状态和文档归属。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `title` | CharField | 文档标题 |
| `file` | FileField | 原始文件路径 |
| `filename` | CharField | 原始文件名 |
| `doc_type` | CharField | 文档类型，如 `txt/pdf/docx` |
| `uploaded_by_id` | FK -> `auth_user` | 上传人 |
| `owner_id` | FK -> `auth_user` | 所有人 |
| `dataset_id` | FK -> `knowledgebase_dataset` | 所属数据集 |
| `visibility` | CharField | `private/internal/public` |
| `status` | CharField | `uploaded/parsed/chunked/indexed/failed` |
| `source_date` | DateField | 文档来源日期 |
| `parsed_text` | TextField | 解析后的正文 |
| `error_message` | TextField | 处理失败原因 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `knowledgebase_documentversion`

文档版本表，用于跟踪同一文档的不同版本。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `root_document_id` | FK -> `knowledgebase_document` | 根文档 |
| `document_id` | OneToOne -> `knowledgebase_document` | 当前版本对应文档 |
| `version_number` | PositiveIntegerField | 版本号 |
| `is_current` | BooleanField | 是否当前版本 |
| `source_type` | CharField | 来源类型 |
| `source_label` | CharField | 来源标签 |
| `source_metadata` | JSONField | 解析和来源元数据 |
| `processing_notes` | TextField | 处理说明 |
| `created_at` | DateTimeField | 创建时间 |

约束：

- `root_document_id + version_number` 唯一。

### `knowledgebase_ingestiontask`

文档入库任务表，记录解析、切块、索引流程状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `document_id` | FK -> `knowledgebase_document` | 目标文档 |
| `celery_task_id` | CharField | Celery 任务 ID |
| `status` | CharField | `queued/running/succeeded/failed` |
| `current_step` | CharField | `queued/parsing/chunking/indexing/completed/failed` |
| `strategy` | CharField | `flat/hierarchical` |
| `total_section_count` | PositiveIntegerField | section 总数 |
| `indexed_section_count` | PositiveIntegerField | 已索引 section 数 |
| `failed_section_count` | PositiveIntegerField | 失败 section 数 |
| `error_message` | TextField | 失败原因 |
| `started_at` | DateTimeField | 开始时间 |
| `finished_at` | DateTimeField | 结束时间 |
| `retry_count` | PositiveIntegerField | 重试次数 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `knowledgebase_documentsectionchunk`

分层 chunk 的父级 section 表，适合大型文档。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `document_id` | FK -> `knowledgebase_document` | 所属文档 |
| `section_index` | PositiveIntegerField | section 序号 |
| `section_label` | CharField | section 标签 |
| `section_path` | CharField | section 路径 |
| `content` | TextField | section 内容 |
| `vector_id` | CharField | Milvus 向量 ID |
| `is_indexed` | BooleanField | 是否已索引 |
| `metadata` | JSONField | 文档、页码、版本等元数据 |
| `start_offset` | PositiveIntegerField | 原文起始位置 |
| `end_offset` | PositiveIntegerField | 原文结束位置 |
| `created_at` | DateTimeField | 创建时间 |

约束：

- `document_id + section_index` 唯一。

### `knowledgebase_documentchunk`

文档子 chunk 表，保存可用于引用和上下文拼接的文本片段。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `document_id` | FK -> `knowledgebase_document` | 所属文档 |
| `section_chunk_id` | FK -> `knowledgebase_documentsectionchunk` | 所属父 section |
| `chunk_index` | PositiveIntegerField | chunk 序号 |
| `content` | TextField | chunk 内容 |
| `vector_id` | CharField | Milvus 向量 ID |
| `metadata` | JSONField | 页码、标题、版本、数据集等元数据 |
| `created_at` | DateTimeField | 创建时间 |

约束：

- `document_id + chunk_index` 唯一。

## 4. RAG 与问答表

### `rag_retrievallog`

检索日志表，用于记录 RAG 查询和结果数量。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `query` | TextField | 查询内容 |
| `top_k` | PositiveIntegerField | 召回数量 |
| `filters` | JSONField | 检索过滤条件 |
| `result_count` | PositiveIntegerField | 返回结果数 |
| `source` | CharField | `retrieval_api/chat_ask` |
| `metadata` | JSONField | 检索元数据 |
| `duration_ms` | PositiveIntegerField | 耗时 |
| `created_at` | DateTimeField | 创建时间 |

### `chat_chatsession`

聊天会话表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `user_id` | FK -> `auth_user` | 会话用户 |
| `title` | CharField | 会话标题 |
| `title_status` | CharField | `pending/ready/failed` |
| `title_source` | CharField | `ai/manual/legacy/system` |
| `rolling_summary` | TextField | 滚动摘要 |
| `summary_updated_through_message_id` | PositiveBigIntegerField | 摘要覆盖到的消息 ID |
| `message_count` | PositiveIntegerField | 消息数量 |
| `last_message_at` | DateTimeField | 最后一条消息时间 |
| `context_filters` | JSONField | 会话级知识库过滤条件 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `chat_chatmessage`

聊天消息表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `session_id` | FK -> `chat_chatsession` | 所属会话 |
| `sequence` | PositiveIntegerField | 会话内消息序号 |
| `role` | CharField | `user/assistant/system` |
| `message_type` | CharField | 消息类型，目前为 `text` |
| `status` | CharField | `pending/complete/failed` |
| `citations_json` | JSONField | 引用来源 |
| `model_metadata_json` | JSONField | 模型调用元数据 |
| `client_message_id` | CharField | 前端消息 ID |
| `content` | TextField | 消息内容 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

约束：

- `session_id + sequence` 唯一。

### `chat_memoryitem`

长期记忆条目表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `user_id` | FK -> `auth_user` | 所属用户 |
| `scope_type` | CharField | `user_global/project/dataset` |
| `scope_key` | CharField | 作用域标识 |
| `memory_type` | CharField | `user_preference/project_background/confirmed_fact/work_rule` |
| `title` | CharField | 记忆标题 |
| `content` | TextField | 记忆内容 |
| `confidence_score` | DecimalField | 置信度 |
| `source_kind` | CharField | `auto/manual` |
| `status` | CharField | `active/archived/deleted` |
| `pinned` | BooleanField | 是否置顶 |
| `fingerprint` | CharField | 去重指纹 |
| `last_verified_at` | DateTimeField | 最近确认时间 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `chat_memoryevidence`

记忆证据表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `memory_item_id` | FK -> `chat_memoryitem` | 对应记忆 |
| `session_id` | FK -> `chat_chatsession` | 来源会话 |
| `message_id` | FK -> `chat_chatmessage` | 来源消息 |
| `evidence_excerpt` | TextField | 证据片段 |
| `extractor_version` | CharField | 抽取器版本 |
| `confirmation_status` | CharField | `pending/confirmed/rejected` |
| `created_at` | DateTimeField | 创建时间 |

约束：

- `session_id` 或 `message_id` 至少存在一个。

### `chat_memoryactionlog`

记忆操作日志表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `memory_item_id` | FK -> `chat_memoryitem` | 记忆条目 |
| `actor_user_id` | FK -> `auth_user` | 操作人 |
| `action` | CharField | `view/delete/pin/unpin/manual_add/manual_edit` |
| `details_json` | JSONField | 操作详情 |
| `created_at` | DateTimeField | 创建时间 |

## 5. 风险分析表

### `risk_riskevent`

风险事件表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `company_name` | CharField | 公司名称 |
| `risk_type` | CharField | 风险类型 |
| `risk_level` | CharField | `low/medium/high/critical` |
| `event_time` | DateTimeField | 事件时间 |
| `summary` | TextField | 风险摘要 |
| `evidence_text` | TextField | 证据文本 |
| `confidence_score` | DecimalField | 抽取置信度，0 到 1 |
| `review_status` | CharField | `pending/approved/rejected` |
| `document_id` | FK -> `knowledgebase_document` | 来源文档 |
| `chunk_id` | FK -> `knowledgebase_documentchunk` | 来源 chunk |
| `metadata` | JSONField | 补充元数据 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `risk_riskreport`

风险报告表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `scope_type` | CharField | `company/time_range` |
| `title` | CharField | 报告标题 |
| `company_name` | CharField | 公司名称 |
| `period_start` | DateField | 起始日期 |
| `period_end` | DateField | 结束日期 |
| `summary` | TextField | 报告摘要 |
| `content` | TextField | 报告正文 |
| `source_metadata` | JSONField | 来源事件和生成参数 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

## 6. LLM 中台表

### `llm_modelconfig`

模型配置表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `name` | CharField | 配置名称 |
| `capability` | CharField | `chat/embedding/rerank` |
| `provider` | CharField | `ollama/deepseek/litellm/dashscope` |
| `model_name` | CharField | 上游模型名 |
| `endpoint` | URLField | 模型 API 地址 |
| `options` | JSONField | 模型参数 |
| `is_active` | BooleanField | 是否当前启用 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

约束：

- `capability + name` 唯一。
- 同一 capability 下启用一个配置时，其它配置会自动取消启用。

### `llm_evalrecord`

模型评测记录表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `model_config_id` | FK -> `llm_modelconfig` | 关联模型 |
| `evaluation_mode` | CharField | `baseline/rag/fine_tuned` |
| `target_name` | CharField | 评测目标 |
| `task_type` | CharField | `qa/risk_extraction/report` |
| `qa_accuracy` | DecimalField | 问答准确率 |
| `extraction_accuracy` | DecimalField | 抽取准确率 |
| `precision` | DecimalField | 精确率 |
| `recall` | DecimalField | 召回率 |
| `f1_score` | DecimalField | F1 |
| `average_latency_ms` | DecimalField | 平均延迟 |
| `version` | CharField | 评测版本 |
| `dataset_name` | CharField | 数据集名称 |
| `dataset_version` | CharField | 数据集版本 |
| `run_notes` | TextField | 运行备注 |
| `status` | CharField | `pending/running/succeeded/failed` |
| `metadata` | JSONField | 评测元数据 |
| `created_at` | DateTimeField | 创建时间 |

### `llm_finetunerunnerserver`

微调执行服务器表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `name` | CharField | 服务名称，唯一 |
| `base_url` | URLField | 服务地址 |
| `auth_token` | CharField | 鉴权 Token |
| `default_work_dir` | CharField | 默认工作目录 |
| `is_enabled` | BooleanField | 是否启用 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `llm_finetunerun`

微调任务表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `base_model_id` | FK -> `llm_modelconfig` | 基座模型 |
| `registered_model_config_id` | FK -> `llm_modelconfig` | 微调后注册模型 |
| `runner_server_id` | FK -> `llm_finetunerunnerserver` | 执行服务 |
| `run_key` | CharField | 内部任务标识 |
| `external_job_id` | CharField | 外部任务 ID |
| `runner_name` | CharField | 执行器名称 |
| `dataset_name` | CharField | 训练数据集 |
| `dataset_version` | CharField | 数据集版本 |
| `strategy` | CharField | 微调策略，如 `lora` |
| `status` | CharField | `pending/running/succeeded/failed` |
| `artifact_path` | CharField | 训练产物路径 |
| `export_path` | CharField | 导出路径 |
| `deployment_endpoint` | CharField | 部署地址 |
| `deployment_model_name` | CharField | 部署模型名 |
| `callback_token_hash` | CharField | 回调 Token 哈希 |
| `callback_token_value` | CharField | 回调 Token 明文 |
| `dataset_manifest` | JSONField | 数据集清单 |
| `training_config` | JSONField | 训练配置 |
| `artifact_manifest` | JSONField | 产物清单 |
| `metrics` | JSONField | 训练指标 |
| `queued_at` | DateTimeField | 排队时间 |
| `started_at` | DateTimeField | 开始时间 |
| `finished_at` | DateTimeField | 结束时间 |
| `last_heartbeat_at` | DateTimeField | 最近心跳 |
| `failure_reason` | TextField | 失败原因 |
| `notes` | TextField | 备注 |
| `created_at` | DateTimeField | 创建时间 |
| `updated_at` | DateTimeField | 更新时间 |

### `llm_litellmsyncevent`

LiteLLM 配置同步事件表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `status` | CharField | `success/failed` |
| `triggered_by_id` | FK -> `auth_user` | 触发人 |
| `message` | TextField | 同步信息 |
| `checksum` | CharField | 配置校验值 |
| `created_at` | DateTimeField | 创建时间 |

### `llm_modelinvocationlog`

模型调用日志表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `model_config_id` | FK -> `llm_modelconfig` | 模型配置 |
| `capability` | CharField | `chat/embedding/rerank` |
| `provider` | CharField | provider |
| `alias` | CharField | 模型别名 |
| `upstream_model` | CharField | 实际上游模型 |
| `stage` | CharField | `routing/fallback/direct` |
| `status` | CharField | `success/failed` |
| `latency_ms` | PositiveIntegerField | 延迟 |
| `request_tokens` | PositiveIntegerField | 请求 tokens |
| `response_tokens` | PositiveIntegerField | 响应 tokens |
| `error_code` | CharField | 错误码 |
| `error_message` | TextField | 错误信息 |
| `trace_id` | CharField | 链路追踪 ID |
| `request_id` | CharField | 请求 ID |
| `created_at` | DateTimeField | 创建时间 |

索引：

- `provider + created_at`
- `model_config + created_at`
- `trace_id + created_at`
- `request_id + created_at`

## 7. 运维审计表

### `systemcheck_auditrecord`

系统审计记录表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigAutoField | 主键 |
| `actor_id` | FK -> `auth_user` | 操作人 |
| `action` | CharField | 操作类型 |
| `target_type` | CharField | 目标类型 |
| `target_id` | CharField | 目标 ID |
| `status` | CharField | `succeeded/failed/retried/skipped` |
| `detail_payload` | JSONField | 操作详情 |
| `created_at` | DateTimeField | 创建时间 |

## 8. LightRAG / Neo4j 图谱设计

LightRAG 图谱数据不进入 Django ORM 表，而是由 LightRAG 自身维护 KV、Vector、Graph、Doc Status 四类存储。

### 图节点

常见节点类型：

- `Document`：文档
- `Chunk`：文本片段
- `Entity`：公司、人物、机构、指标、项目、风险事件等实体
- `Concept`：业务概念、风险类别、财务指标类别

常见属性：

- `id`
- `name`
- `type`
- `description`
- `source_document_id`
- `source_chunk_id`
- `dataset_id`
- `created_at`
- `updated_at`

### 图关系

常见关系类型：

- `MENTIONS`：文档或 chunk 提及实体
- `RELATED_TO`：实体之间存在一般关系
- `OWNS`：股权或所有权关系
- `GUARANTEES`：担保关系
- `HAS_RISK`：主体存在风险事件
- `LOCATED_IN`：地域关系
- `DERIVED_FROM`：图节点来源于某个文档或 chunk

常见属性：

- `weight`
- `confidence`
- `evidence`
- `source_document_id`
- `source_chunk_id`
- `created_at`

### 与业务表的映射

| 图谱字段 | 业务来源 |
|---|---|
| `source_document_id` | `knowledgebase_document.id` |
| `source_chunk_id` | `knowledgebase_documentchunk.id` 或 `knowledgebase_documentsectionchunk.id` |
| `dataset_id` | `knowledgebase_dataset.id` |
| `document_title` | `knowledgebase_document.title` |
| `page_label` | chunk metadata |

这种设计让 FinModPro 可以在 MySQL 中保持清晰业务边界，在 Neo4j 中执行图谱探索和多跳关系查询，在 Milvus 中执行语义向量召回。

## 9. 核心关系概览

```text
auth_user
  ├─ knowledgebase_dataset.owner
  ├─ knowledgebase_document.uploaded_by / owner
  ├─ chat_chatsession.user
  ├─ chat_memoryitem.user
  ├─ chat_memoryactionlog.actor_user
  ├─ llm_litellmsyncevent.triggered_by
  └─ systemcheck_auditrecord.actor

knowledgebase_dataset
  └─ knowledgebase_document
      ├─ knowledgebase_documentversion
      ├─ knowledgebase_ingestiontask
      ├─ knowledgebase_documentsectionchunk
      │   └─ knowledgebase_documentchunk
      ├─ risk_riskevent
      └─ Milvus / LightRAG / Neo4j indexes

chat_chatsession
  ├─ chat_chatmessage
  └─ chat_memoryevidence

chat_memoryitem
  ├─ chat_memoryevidence
  └─ chat_memoryactionlog

llm_modelconfig
  ├─ llm_evalrecord
  ├─ llm_finetunerun.base_model
  ├─ llm_finetunerun.registered_model_config
  └─ llm_modelinvocationlog
```
