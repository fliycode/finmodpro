# FinModPro 数据库设计

本文档基于 MySQL 数据库实际 schema 整理。MySQL 保存 FinModPro 业务数据，Milvus 保存向量索引。

## 1. 数据存储划分

| 存储 | 作用 |
|---|---|
| MySQL | 用户、权限、知识库文档、chunk、问答会话、风险事件、模型配置、审计日志、运维指标 |
| Milvus | 文档 chunk、section chunk 等向量索引 |
| Redis | 缓存、Celery broker、Celery result backend |
| 文件存储 | 上传原始文件、媒体文件、导出文件 |

## 2. 论文第四章可直接引用的核心表设计

如果本文档用于毕业论文第四章"数据库表设计"，推荐不要把所有表逐张展开，而是优先介绍最能体现系统业务闭环的核心表。建议正文重点展示以下 8 张表：

1. 用户表 `auth_user`
2. 文档表 `knowledgebase_document`
3. 入库任务表 `knowledgebase_ingestiontask`
4. 文档分块表 `knowledgebase_documentchunk`
5. 会话表 `chat_chatsession`
6. 消息表 `chat_chatmessage`
7. 风险事件表 `risk_riskevent`
8. 模型配置表 `llm_modelconfig`

字段设计建议统一使用下面这 6 列格式：

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|

### 2.1 用户表 `auth_user`

该表为 Django 内置认证表，用于保存系统登录用户的基础身份信息，是权限控制、文档归属、会话归属和审计归属的上游主表。论文正文中可作为"平台用户主表"介绍，不必展开到 Django 所有内置字段。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | int | - | 否 | 主键 | 用户唯一标识 |
| `username` | varchar | 150 | 否 | 唯一 | 登录用户名 |
| `password` | varchar | 128 | 否 | - | 密码哈希 |
| `email` | varchar | 254 | 否 | - | 用户邮箱 |
| `is_active` | tinyint(1) | - | 否 | 默认 `true` | 账户是否启用 |
| `is_staff` | tinyint(1) | - | 否 | 默认 `false` | 是否具有后台权限 |
| `date_joined` | datetime(6) | - | 否 | - | 注册时间 |

### 2.2 文档表 `knowledgebase_document`

文档表是知识库模块的核心主表，用于记录上传文件、文档归属、解析状态和文本结果。系统后续的分块、向量化、风险抽取和图谱同步都以该表为起点。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 文档唯一标识 |
| `title` | varchar | 255 | 否 | - | 文档标题 |
| `file` | varchar | 100 | 否 | - | 原始文件存储路径 |
| `file_size` | bigint unsigned | - | 否 | 默认 `0` | 文件大小（字节） |
| `file_hash` | varchar | 64 | 否 | 索引 | 文件 SHA-256 哈希，用于去重 |
| `filename` | varchar | 255 | 否 | - | 原始文件名 |
| `doc_type` | varchar | 32 | 否 | - | 文档类型，如 `pdf/txt/docx` |
| `uploaded_by_id` | int | - | 是 | FK | 上传人 |
| `owner_id` | int | - | 是 | FK | 文档归属人 |
| `dataset_id` | bigint | - | 是 | FK | 所属数据集 |
| `visibility` | varchar | 32 | 否 | 默认值 | 可见范围，`private/internal/public` |
| `status` | varchar | 32 | 否 | 默认值 | 处理状态，`uploaded/parsed/chunked/indexed/failed` |
| `source_date` | date | - | 是 | - | 文档来源日期 |
| `parsed_text` | longtext | - | 否 | - | 解析后的正文文本 |
| `error_message` | longtext | - | 否 | - | 失败信息 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |
| `updated_at` | datetime(6) | - | 否 | 自动更新 | 更新时间 |

### 2.3 入库任务表 `knowledgebase_ingestiontask`

入库任务表用于记录文档从解析、切块、向量索引到图谱同步的完整过程状态，是知识库链路可观测性的核心表。在论文中，这张表非常适合体现"系统具备异步任务与状态跟踪能力"。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 任务唯一标识 |
| `document_id` | bigint | - | 否 | FK | 目标文档 |
| `celery_task_id` | varchar | 255 | 否 | 索引 | Celery 任务 ID |
| `status` | varchar | 32 | 否 | 默认值 | 任务状态，`queued/running/succeeded/failed` |
| `current_step` | varchar | 32 | 否 | 默认值 | 当前步骤，含 `parsing/cleaning/chunking/indexing` |
| `strategy` | varchar | 32 | 否 | 默认值 | 入库策略，`flat/hierarchical` |
| `total_section_count` | int unsigned | - | 否 | 默认 `0` | section 总数 |
| `indexed_section_count` | int unsigned | - | 否 | 默认 `0` | 已索引数量 |
| `failed_section_count` | int unsigned | - | 否 | 默认 `0` | 失败数量 |
| `graph_sync_status` | varchar | 32 | 否 | 默认值 | 图谱同步状态 |
| `graph_document_id` | varchar | 255 | 否 | 索引 | 图谱文档 ID |
| `graph_track_id` | varchar | 255 | 否 | 索引 | 图谱追踪 ID |
| `graph_sync_error_message` | longtext | - | 否 | - | 图谱同步失败原因 |
| `graph_sync_started_at` | datetime(6) | - | 是 | - | 图谱同步开始时间 |
| `graph_sync_finished_at` | datetime(6) | - | 是 | - | 图谱同步结束时间 |
| `error_message` | longtext | - | 否 | - | 任务失败原因 |
| `started_at` | datetime(6) | - | 是 | - | 开始时间 |
| `finished_at` | datetime(6) | - | 是 | - | 结束时间 |
| `retry_count` | int unsigned | - | 否 | 默认 `0` | 重试次数 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |
| `updated_at` | datetime(6) | - | 否 | 自动更新 | 更新时间 |

### 2.4 文档分块表 `knowledgebase_documentchunk`

文档分块表保存知识库检索的最小文本单元，是 RAG 检索、引用回传和风险事件证据定位的主要数据来源。论文中可以把它作为"知识库语义检索核心表"展开。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | chunk 唯一标识 |
| `document_id` | bigint | - | 否 | FK | 所属文档 |
| `section_chunk_id` | bigint | - | 是 | FK | 所属父 section |
| `chunk_index` | int unsigned | - | 否 | 联合唯一 | chunk 序号 |
| `content` | longtext | - | 否 | - | chunk 正文 |
| `search_text` | longtext | - | 否 | 全文索引 | 检索优化文本 |
| `vector_id` | varchar | 64 | 否 | 索引 | Milvus 向量 ID |
| `metadata` | json | - | 否 | - | 页码、标题、数据集等元数据 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |

约束说明：

- `document_id + chunk_index` 联合唯一，确保同一文档内的 chunk 序号不重复。

### 2.5 会话表 `chat_chatsession`

会话表用于保存用户与系统交互的会话级信息，包括标题、滚动摘要、消息数量和上下文过滤条件。该表是"智能问答模块"数据库设计中的核心表。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 会话唯一标识 |
| `user_id` | int | - | 否 | FK | 所属用户 |
| `title` | varchar | 255 | 否 | 默认值 | 会话标题 |
| `title_status` | varchar | 16 | 否 | 默认值 | 标题状态，`pending/ready/failed` |
| `title_source` | varchar | 32 | 否 | 默认值 | 标题来源，`ai/manual/system` |
| `rolling_summary` | longtext | - | 否 | 默认空串 | 滚动摘要 |
| `summary_updated_through_message_id` | bigint unsigned | - | 是 | - | 摘要覆盖到的消息 ID |
| `message_count` | int unsigned | - | 否 | 默认 `0` | 消息总数 |
| `last_message_at` | datetime(6) | - | 是 | - | 最后活跃时间 |
| `context_filters` | json | - | 否 | - | 会话级过滤条件 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |
| `updated_at` | datetime(6) | - | 否 | 自动更新 | 更新时间 |

### 2.6 消息表 `chat_chatmessage`

消息表用于保存用户消息、助手回复和系统消息，同时记录引用来源和模型元数据。在论文中，这张表可以体现系统"回答可追溯"的设计特征。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 消息唯一标识 |
| `session_id` | bigint | - | 否 | FK | 所属会话 |
| `sequence` | int unsigned | - | 是 | 联合唯一 | 会话内序号，由系统自动补齐 |
| `role` | varchar | 32 | 否 | - | 角色，`user/assistant/system` |
| `message_type` | varchar | 32 | 否 | 默认值 | 消息类型 |
| `status` | varchar | 16 | 否 | 默认值 | 消息状态，`pending/complete/failed` |
| `citations_json` | json | - | 否 | 默认空数组 | 引用来源 |
| `model_metadata_json` | json | - | 否 | 默认空对象 | 模型调用元数据 |
| `client_message_id` | varchar | 64 | 否 | 默认空串 | 前端消息 ID |
| `content` | longtext | - | 否 | - | 消息正文 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |
| `updated_at` | datetime(6) | - | 否 | 自动更新 | 更新时间 |

约束说明：

- `session_id + sequence` 联合唯一，用于保证同一会话中的消息顺序稳定。

### 2.7 风险事件表 `risk_riskevent`

风险事件表保存从文档中抽取出的风险信息，是风险分析模块的核心业务表。它连接知识库文档与风险报告，支持审核流和风险证据追踪。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 风险事件唯一标识 |
| `company_name` | varchar | 255 | 否 | 索引 | 涉及公司名称 |
| `risk_type` | varchar | 128 | 否 | 索引 | 风险类型 |
| `risk_level` | varchar | 32 | 否 | 索引/默认值 | 风险等级 |
| `event_time` | datetime(6) | - | 是 | 索引 | 风险事件时间 |
| `summary` | longtext | - | 否 | - | 风险摘要 |
| `evidence_text` | longtext | - | 否 | - | 证据文本 |
| `confidence_score` | decimal | 4,3 | 否 | 取值 0~1 | 抽取置信度 |
| `review_status` | varchar | 32 | 否 | 索引/默认值 | 审核状态 |
| `document_id` | bigint | - | 是 | FK | 来源文档 |
| `chunk_id` | bigint | - | 是 | FK | 来源 chunk |
| `metadata` | json | - | 否 | - | 补充元数据 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |
| `updated_at` | datetime(6) | - | 否 | 自动更新 | 更新时间 |

### 2.8 模型配置表 `llm_modelconfig`

模型配置表用于保存 chat、embedding 和 rerank 三类模型的接入配置，是模型中台模块的主表。在论文中，这张表可以体现系统对模型能力解耦和统一管理的设计思想。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 模型配置唯一标识 |
| `name` | varchar | 255 | 否 | 联合唯一 | 配置名称 |
| `capability` | varchar | 32 | 否 | 联合唯一/索引 | 能力类型，`chat/embedding/rerank` |
| `provider` | varchar | 32 | 否 | - | 提供方，如 `deepseek/dashscope/ollama/openai_compatible` |
| `model_name` | varchar | 255 | 否 | - | 上游模型名称 |
| `parameter_scale` | varchar | 64 | 否 | - | 参数规模 |
| `endpoint` | varchar | 500 | 否 | - | 模型服务地址 |
| `description` | longtext | - | 否 | - | 配置描述 |
| `options` | json | - | 否 | - | 模型参数配置 |
| `input_price_per_million` | decimal | 12,6 | 否 | 默认 `0` | 每百万 token 输入价格 |
| `output_price_per_million` | decimal | 12,6 | 否 | 默认 `0` | 每百万 token 输出价格 |
| `request_price` | decimal | 12,6 | 否 | 默认 `0` | 每次请求价格 |
| `price_currency` | varchar | 8 | 否 | 默认 `USD` | 价格货币单位 |
| `pricing_notes` | longtext | - | 否 | - | 定价备注 |
| `is_active` | tinyint(1) | - | 否 | 默认 `false` | 是否启用 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |
| `updated_at` | datetime(6) | - | 否 | 自动更新 | 更新时间 |

约束说明：

- `capability + name` 联合唯一。
- 同一能力类型下仅允许一个配置处于启用状态，其余配置在保存时会被自动取消启用。

### 2.9 审计表 `systemcheck_auditrecord`

审计表用于记录后台关键操作行为，是系统运维与治理可追踪性的基础表。论文中可将其作为"系统可靠性与安全性设计"的支撑表。

| 字段名称 | 数据类型 | 长度 | 允许空值 | 键/约束 | 字段说明 |
|---|---|---|---|---|---|
| `id` | bigint | - | 否 | 主键 | 审计记录唯一标识 |
| `actor_id` | int | - | 是 | FK | 操作人 |
| `action` | varchar | 128 | 否 | 索引 | 操作类型 |
| `target_type` | varchar | 64 | 否 | 索引 | 目标类型 |
| `target_id` | varchar | 64 | 否 | 索引 | 目标 ID |
| `status` | varchar | 32 | 否 | 索引 | 操作结果 |
| `detail_payload` | json | - | 否 | - | 操作详情 |
| `created_at` | datetime(6) | - | 否 | 自动生成 | 创建时间 |

### 2.10 论文写作建议

如果学校要求数据库表设计"每张表一个小节 + 一个表格"，建议在正文中优先保留 2.1 到 2.9 这几张核心表，其余表可以放入附录或作为"补充业务表设计"简要说明。这样既能体现系统完整性，也能避免第四章因为表过多而失去重点。

## 3. 用户与权限表

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
- 管理端通过用户角色和权限判断是否允许访问后台、知识库、模型中台和运维管理入口。

## 4. 知识库表

### `knowledgebase_dataset`

数据集表，用于对文档进行分组管理。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `name` | varchar | 255 | 数据集名称，唯一 |
| `description` | longtext | - | 数据集描述 |
| `owner_id` | int | - | FK -> `auth_user`，数据集负责人 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `knowledgebase_document`

文档主表，保存上传文件、解析状态和文档归属。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `title` | varchar | 255 | 文档标题 |
| `file` | varchar | 100 | 原始文件路径 |
| `file_size` | bigint unsigned | - | 文件大小（字节） |
| `file_hash` | varchar | 64 | 文件 SHA-256 哈希，索引 |
| `filename` | varchar | 255 | 原始文件名 |
| `doc_type` | varchar | 32 | 文档类型，如 `txt/pdf/docx` |
| `uploaded_by_id` | int | - | FK -> `auth_user`，上传人 |
| `owner_id` | int | - | FK -> `auth_user`，所有人 |
| `dataset_id` | bigint | - | FK -> `knowledgebase_dataset`，所属数据集 |
| `visibility` | varchar | 32 | `private/internal/public` |
| `status` | varchar | 32 | `uploaded/parsed/chunked/indexed/failed` |
| `source_date` | date | - | 文档来源日期 |
| `parsed_text` | longtext | - | 解析后的正文 |
| `error_message` | longtext | - | 处理失败原因 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `knowledgebase_documentversion`

文档版本表，用于跟踪同一文档的不同版本。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `root_document_id` | bigint | - | FK -> `knowledgebase_document`，根文档 |
| `document_id` | bigint | - | OneToOne -> `knowledgebase_document`，当前版本对应文档 |
| `version_number` | int unsigned | - | 版本号 |
| `is_current` | tinyint(1) | - | 是否当前版本 |
| `source_type` | varchar | 64 | 来源类型 |
| `source_label` | varchar | 255 | 来源标签 |
| `source_metadata` | json | - | 解析和来源元数据 |
| `processing_notes` | longtext | - | 处理说明 |
| `created_at` | datetime(6) | - | 创建时间 |

约束：

- `root_document_id + version_number` 唯一。

### `knowledgebase_ingestiontask`

文档入库任务表，记录解析、切块、索引流程状态。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `document_id` | bigint | - | FK -> `knowledgebase_document`，目标文档 |
| `celery_task_id` | varchar | 255 | Celery 任务 ID，索引 |
| `status` | varchar | 32 | `queued/running/succeeded/failed` |
| `current_step` | varchar | 32 | `queued/parsing/chunking/indexing/completed/failed` |
| `strategy` | varchar | 32 | `flat/hierarchical` |
| `total_section_count` | int unsigned | - | section 总数 |
| `indexed_section_count` | int unsigned | - | 已索引 section 数 |
| `failed_section_count` | int unsigned | - | 失败 section 数 |
| `graph_sync_status` | varchar | 32 | 图谱同步状态 |
| `graph_document_id` | varchar | 255 | 图谱文档 ID，索引 |
| `graph_track_id` | varchar | 255 | 图谱追踪 ID，索引 |
| `graph_sync_error_message` | longtext | - | 图谱同步失败原因 |
| `graph_sync_started_at` | datetime(6) | - | 图谱同步开始时间 |
| `graph_sync_finished_at` | datetime(6) | - | 图谱同步结束时间 |
| `error_message` | longtext | - | 失败原因 |
| `started_at` | datetime(6) | - | 开始时间 |
| `finished_at` | datetime(6) | - | 结束时间 |
| `retry_count` | int unsigned | - | 重试次数 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `knowledgebase_documentsectionchunk`

分层 chunk 的父级 section 表，适合大型文档。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `document_id` | bigint | - | FK -> `knowledgebase_document`，所属文档 |
| `section_index` | int unsigned | - | section 序号 |
| `section_label` | varchar | 255 | section 标签 |
| `section_path` | varchar | 512 | section 路径 |
| `content` | longtext | - | section 内容 |
| `search_text` | longtext | - | 检索优化文本，全文索引 |
| `vector_id` | varchar | 64 | Milvus 向量 ID，索引 |
| `is_indexed` | tinyint(1) | - | 是否已索引 |
| `metadata` | json | - | 文档、页码、版本等元数据 |
| `start_offset` | int unsigned | - | 原文起始位置 |
| `end_offset` | int unsigned | - | 原文结束位置 |
| `created_at` | datetime(6) | - | 创建时间 |

约束：

- `document_id + section_index` 唯一。

### `knowledgebase_documentchunk`

文档子 chunk 表，保存可用于引用和上下文拼接的文本片段。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `document_id` | bigint | - | FK -> `knowledgebase_document`，所属文档 |
| `section_chunk_id` | bigint | - | FK -> `knowledgebase_documentsectionchunk`，所属父 section |
| `chunk_index` | int unsigned | - | chunk 序号 |
| `content` | longtext | - | chunk 内容 |
| `search_text` | longtext | - | 检索优化文本，全文索引 |
| `vector_id` | varchar | 64 | Milvus 向量 ID，索引 |
| `metadata` | json | - | 页码、标题、版本、数据集等元数据 |
| `created_at` | datetime(6) | - | 创建时间 |

约束：

- `document_id + chunk_index` 唯一。

### `knowledgebase_cleaningrule`

文档清洗规则表，用于配置文档入库前的清洗策略。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `name` | varchar | 255 | 规则名称，唯一 |
| `rule_type` | varchar | 64 | 规则类型，索引 |
| `config` | json | - | 规则配置参数 |
| `enabled` | tinyint(1) | - | 是否启用 |
| `priority` | int unsigned | - | 优先级 |
| `created_by_id` | int | - | FK -> `auth_user`，创建人 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `knowledgebase_documentcleaningresult`

文档清洗结果表，记录清洗过程的质量指标。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `document_id` | bigint | - | FK -> `knowledgebase_document`，目标文档 |
| `rules_applied` | json | - | 应用的清洗规则 |
| `issues_found` | json | - | 发现的问题 |
| `quality_score` | double | - | 清洗后质量评分 |
| `quality_signals` | json | - | 质量信号详情 |
| `original_length` | int unsigned | - | 原始文本长度 |
| `cleaned_length` | int unsigned | - | 清洗后文本长度 |
| `dedup_count` | int unsigned | - | 去重数量 |
| `cleaned_at` | datetime(6) | - | 清洗完成时间 |

## 5. RAG 与问答表

### `rag_retrievallog`

检索日志表，用于记录 RAG 查询和结果数量。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `query` | longtext | - | 查询内容 |
| `top_k` | int unsigned | - | 召回数量 |
| `filters` | json | - | 检索过滤条件 |
| `result_count` | int unsigned | - | 返回结果数 |
| `source` | varchar | 32 | `retrieval_api/chat_ask` |
| `metadata` | json | - | 检索元数据 |
| `duration_ms` | int unsigned | - | 耗时（毫秒） |
| `created_at` | datetime(6) | - | 创建时间 |

### `chat_chatsession`

聊天会话表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `user_id` | int | - | FK -> `auth_user`，会话用户 |
| `title` | varchar | 255 | 会话标题 |
| `title_status` | varchar | 16 | `pending/ready/failed` |
| `title_source` | varchar | 32 | `ai/manual/legacy/system` |
| `rolling_summary` | longtext | - | 滚动摘要 |
| `summary_updated_through_message_id` | bigint unsigned | - | 摘要覆盖到的消息 ID |
| `message_count` | int unsigned | - | 消息数量 |
| `last_message_at` | datetime(6) | - | 最后一条消息时间 |
| `context_filters` | json | - | 会话级知识库过滤条件 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `chat_chatmessage`

聊天消息表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `session_id` | bigint | - | FK -> `chat_chatsession`，所属会话 |
| `sequence` | int unsigned | - | 会话内消息序号 |
| `role` | varchar | 32 | `user/assistant/system` |
| `message_type` | varchar | 32 | 消息类型，目前为 `text` |
| `status` | varchar | 16 | `pending/complete/failed` |
| `citations_json` | json | - | 引用来源 |
| `model_metadata_json` | json | - | 模型调用元数据 |
| `client_message_id` | varchar | 64 | 前端消息 ID |
| `content` | longtext | - | 消息内容 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

约束：

- `session_id + sequence` 唯一。

### `chat_memoryitem`

长期记忆条目表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `user_id` | int | - | FK -> `auth_user`，所属用户 |
| `scope_type` | varchar | 32 | `user_global/project/dataset` |
| `scope_key` | varchar | 255 | 作用域标识 |
| `memory_type` | varchar | 32 | `user_preference/project_background/confirmed_fact/work_rule` |
| `title` | varchar | 255 | 记忆标题 |
| `content` | longtext | - | 记忆内容 |
| `confidence_score` | decimal | 4,2 | 置信度 |
| `source_kind` | varchar | 16 | `auto/manual` |
| `status` | varchar | 16 | `active/archived/deleted` |
| `pinned` | tinyint(1) | - | 是否置顶 |
| `fingerprint` | varchar | 255 | 去重指纹 |
| `embedding` | json | - | 嵌入向量 |
| `last_verified_at` | datetime(6) | - | 最近确认时间 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `chat_memoryevidence`

记忆证据表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `memory_item_id` | bigint | - | FK -> `chat_memoryitem`，对应记忆 |
| `session_id` | bigint | - | FK -> `chat_chatsession`，来源会话 |
| `message_id` | bigint | - | FK -> `chat_chatmessage`，来源消息 |
| `evidence_excerpt` | longtext | - | 证据片段 |
| `extractor_version` | varchar | 64 | 抽取器版本 |
| `confirmation_status` | varchar | 16 | `pending/confirmed/rejected` |
| `created_at` | datetime(6) | - | 创建时间 |

约束：

- `session_id` 或 `message_id` 至少存在一个。

### `chat_memoryactionlog`

记忆操作日志表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `memory_item_id` | bigint | - | FK -> `chat_memoryitem`，记忆条目 |
| `actor_user_id` | int | - | FK -> `auth_user`，操作人 |
| `action` | varchar | 32 | `view/delete/pin/unpin/manual_add/manual_edit` |
| `details_json` | json | - | 操作详情 |
| `created_at` | datetime(6) | - | 创建时间 |

## 6. 风险分析表

### `risk_riskevent`

风险事件表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `company_name` | varchar | 255 | 公司名称，索引 |
| `risk_type` | varchar | 128 | 风险类型，索引 |
| `risk_level` | varchar | 32 | `low/medium/high/critical`，索引 |
| `event_time` | datetime(6) | - | 事件时间，索引 |
| `summary` | longtext | - | 风险摘要 |
| `evidence_text` | longtext | - | 证据文本 |
| `confidence_score` | decimal | 4,3 | 抽取置信度，0 到 1 |
| `review_status` | varchar | 32 | `pending/approved/rejected`，索引 |
| `document_id` | bigint | - | FK -> `knowledgebase_document`，来源文档 |
| `chunk_id` | bigint | - | FK -> `knowledgebase_documentchunk`，来源 chunk |
| `metadata` | json | - | 补充元数据 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `risk_riskextractiontask`

风险抽取任务表，记录异步抽取任务的执行状态。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | char | 32 | 主键（UUID） |
| `document_id` | bigint | - | FK -> `knowledgebase_document`，目标文档 |
| `celery_task_id` | varchar | 255 | Celery 任务 ID，索引 |
| `status` | varchar | 32 | 任务状态 |
| `current_step` | varchar | 32 | 当前步骤 |
| `progress` | smallint unsigned | - | 进度百分比 |
| `created_count` | int unsigned | - | 已创建风险事件数 |
| `message` | longtext | - | 进度消息 |
| `error_message` | longtext | - | 错误信息 |
| `result_payload` | json | - | 结果数据 |
| `started_at` | datetime(6) | - | 开始时间 |
| `finished_at` | datetime(6) | - | 结束时间 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `risk_riskreport`

风险报告表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `scope_type` | varchar | 32 | `company/time_range`，索引 |
| `title` | varchar | 255 | 报告标题 |
| `company_name` | varchar | 255 | 公司名称，索引 |
| `period_start` | date | - | 起始日期，索引 |
| `period_end` | date | - | 结束日期，索引 |
| `summary` | longtext | - | 报告摘要 |
| `content` | longtext | - | 报告正文 |
| `source_metadata` | json | - | 来源事件和生成参数 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

## 7. LLM 中台表

### `llm_modelconfig`

模型配置表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `name` | varchar | 255 | 配置名称 |
| `capability` | varchar | 32 | `chat/embedding/rerank`，索引 |
| `provider` | varchar | 32 | `ollama/deepseek/dashscope/openai_compatible` |
| `model_name` | varchar | 255 | 上游模型名 |
| `parameter_scale` | varchar | 64 | 参数规模 |
| `endpoint` | varchar | 500 | 模型 API 地址 |
| `description` | longtext | - | 配置描述 |
| `options` | json | - | 模型参数 |
| `input_price_per_million` | decimal | 12,6 | 每百万 token 输入价格 |
| `output_price_per_million` | decimal | 12,6 | 每百万 token 输出价格 |
| `request_price` | decimal | 12,6 | 每次请求价格 |
| `price_currency` | varchar | 8 | 价格货币单位，默认 `USD` |
| `pricing_notes` | longtext | - | 定价备注 |
| `is_active` | tinyint(1) | - | 是否当前启用 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

约束：

- `capability + name` 唯一。
- 同一 capability 下启用一个配置时，其它配置会自动取消启用。

### `llm_evalrecord`

模型评测记录表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `model_config_id` | bigint | - | FK -> `llm_modelconfig`，关联模型 |
| `evaluation_mode` | varchar | 32 | `baseline/rag/fine_tuned`，索引 |
| `target_name` | varchar | 255 | 评测目标，索引 |
| `task_type` | varchar | 64 | `qa/risk_extraction/report`，索引 |
| `qa_accuracy` | decimal | 5,4 | 问答准确率 |
| `extraction_accuracy` | decimal | 5,4 | 抽取准确率 |
| `precision` | decimal | 5,4 | 精确率 |
| `recall` | decimal | 5,4 | 召回率 |
| `f1_score` | decimal | 5,4 | F1 |
| `average_latency_ms` | decimal | 10,2 | 平均延迟（毫秒） |
| `version` | varchar | 128 | 评测版本 |
| `dataset_name` | varchar | 255 | 数据集名称，索引 |
| `dataset_version` | varchar | 128 | 数据集版本 |
| `run_notes` | longtext | - | 运行备注 |
| `status` | varchar | 32 | `pending/running/succeeded/failed`，索引 |
| `metadata` | json | - | 评测元数据 |
| `created_at` | datetime(6) | - | 创建时间 |

### `llm_finetunerunnerserver`

微调执行服务器表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `name` | varchar | 255 | 服务名称，唯一 |
| `base_url` | varchar | 500 | 服务地址 |
| `auth_token` | varchar | 255 | 鉴权 Token |
| `default_work_dir` | varchar | 500 | 默认工作目录 |
| `is_enabled` | tinyint(1) | - | 是否启用 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `llm_finetunerun`

微调任务表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `base_model_id` | bigint | - | FK -> `llm_modelconfig`，基座模型 |
| `registered_model_config_id` | bigint | - | FK -> `llm_modelconfig`，微调后注册模型 |
| `runner_server_id` | bigint | - | FK -> `llm_finetunerunnerserver`，执行服务 |
| `run_key` | varchar | 64 | 内部任务标识，索引 |
| `external_job_id` | varchar | 255 | 外部任务 ID，索引 |
| `runner_name` | varchar | 128 | 执行器名称 |
| `dataset_name` | varchar | 255 | 训练数据集 |
| `dataset_version` | varchar | 128 | 数据集版本 |
| `strategy` | varchar | 64 | 微调策略，如 `lora` |
| `status` | varchar | 32 | `pending/running/succeeded/failed`，索引 |
| `artifact_path` | varchar | 500 | 训练产物路径 |
| `export_path` | varchar | 500 | 导出路径 |
| `deployment_endpoint` | varchar | 500 | 部署地址 |
| `deployment_model_name` | varchar | 255 | 部署模型名 |
| `callback_token_hash` | varchar | 128 | 回调 Token 哈希 |
| `callback_token_value` | varchar | 255 | 回调 Token 明文 |
| `dataset_manifest` | json | - | 数据集清单 |
| `training_config` | json | - | 训练配置 |
| `artifact_manifest` | json | - | 产物清单 |
| `metrics` | json | - | 训练指标 |
| `queued_at` | datetime(6) | - | 排队时间，索引 |
| `started_at` | datetime(6) | - | 开始时间 |
| `finished_at` | datetime(6) | - | 结束时间 |
| `last_heartbeat_at` | datetime(6) | - | 最近心跳 |
| `failure_reason` | longtext | - | 失败原因 |
| `notes` | longtext | - | 备注 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `llm_modelinvocationlog`

模型调用日志表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `model_config_id` | bigint | - | FK -> `llm_modelconfig`，模型配置 |
| `capability` | varchar | 32 | `chat/embedding/rerank` |
| `provider` | varchar | 32 | provider，索引 |
| `alias` | varchar | 255 | 模型别名 |
| `upstream_model` | varchar | 255 | 实际上游模型 |
| `stage` | varchar | 32 | `routing/fallback/direct` |
| `status` | varchar | 32 | `success/failed` |
| `latency_ms` | int unsigned | - | 延迟（毫秒） |
| `request_tokens` | int unsigned | - | 请求 tokens |
| `response_tokens` | int unsigned | - | 响应 tokens |
| `total_tokens` | int unsigned | - | 总 tokens |
| `token_source` | varchar | 32 | token 统计来源 |
| `raw_usage` | json | - | 原始用量数据 |
| `provider_request_id` | varchar | 128 | 提供商请求 ID |
| `input_unit_price_snapshot` | decimal | 12,6 | 输入单价快照 |
| `output_unit_price_snapshot` | decimal | 12,6 | 输出单价快照 |
| `request_price_snapshot` | decimal | 12,6 | 请求单价快照 |
| `input_cost` | decimal | 18,8 | 输入成本 |
| `output_cost` | decimal | 18,8 | 输出成本 |
| `total_cost` | decimal | 18,8 | 总成本 |
| `error_code` | varchar | 64 | 错误码 |
| `error_message` | longtext | - | 错误信息 |
| `trace_id` | varchar | 128 | 链路追踪 ID，索引 |
| `request_id` | varchar | 128 | 请求 ID，索引 |
| `created_at` | datetime(6) | - | 创建时间，索引 |

索引：

- `provider + created_at`
- `model_config + created_at`
- `trace_id + created_at`
- `request_id + created_at`

## 8. 运维审计表

### `systemcheck_auditrecord`

系统审计记录表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `actor_id` | int | - | FK -> `auth_user`，操作人 |
| `action` | varchar | 128 | 操作类型，索引 |
| `target_type` | varchar | 64 | 目标类型，索引 |
| `target_id` | varchar | 64 | 目标 ID，索引 |
| `status` | varchar | 32 | `succeeded/failed/retried/skipped`，索引 |
| `detail_payload` | json | - | 操作详情 |
| `created_at` | datetime(6) | - | 创建时间 |

## 9. 系统运维指标与告警表

### `ops_systemmetric`

系统指标表，用于存储采集到的运行时指标。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `metric_name` | varchar | 128 | 指标名称，索引 |
| `value` | double | - | 指标值 |
| `unit` | varchar | 32 | 单位 |
| `tags` | json | - | 标签 |
| `collected_at` | datetime(6) | - | 采集时间，索引 |
| `created_at` | datetime(6) | - | 创建时间 |

### `ops_alertrule`

告警规则表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `name` | varchar | 255 | 规则名称，唯一 |
| `metric_name` | varchar | 128 | 监控指标名，索引 |
| `condition` | varchar | 8 | 条件运算符 |
| `threshold` | double | - | 阈值 |
| `severity` | varchar | 16 | 严重级别 |
| `enabled` | tinyint(1) | - | 是否启用 |
| `notification_channels` | json | - | 通知渠道配置 |
| `description` | longtext | - | 规则描述 |
| `created_by_id` | int | - | FK -> `auth_user`，创建人 |
| `created_at` | datetime(6) | - | 创建时间 |
| `updated_at` | datetime(6) | - | 更新时间 |

### `ops_alertevent`

告警事件表。

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `id` | bigint | - | 主键 |
| `rule_id` | bigint | - | FK -> `ops_alertrule`，关联规则 |
| `status` | varchar | 16 | 事件状态 |
| `triggered_value` | double | - | 触发值 |
| `triggered_at` | datetime(6) | - | 触发时间 |
| `resolved_at` | datetime(6) | - | 解决时间 |
| `acknowledged_by_id` | int | - | FK -> `auth_user`，确认人 |
| `created_at` | datetime(6) | - | 创建时间 |

## 10. 核心关系概览

```text
auth_user
  ├─ knowledgebase_dataset.owner
  ├─ knowledgebase_document.uploaded_by / owner
  ├─ knowledgebase_cleaningrule.created_by
  ├─ chat_chatsession.user
  ├─ chat_memoryitem.user
  ├─ chat_memoryactionlog.actor_user
  ├─ ops_alertrule.created_by
  ├─ ops_alertevent.acknowledged_by
  └─ systemcheck_auditrecord.actor

knowledgebase_dataset
  └─ knowledgebase_document
      ├─ knowledgebase_documentversion
      ├─ knowledgebase_ingestiontask
      ├─ knowledgebase_documentcleaningresult
      ├─ knowledgebase_documentsectionchunk
      │   └─ knowledgebase_documentchunk
      ├─ risk_riskevent
      ├─ risk_riskextractiontask
      └─ Milvus vector indexes

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

ops_alertrule
  └─ ops_alertevent

systemcheck_auditrecord
```
