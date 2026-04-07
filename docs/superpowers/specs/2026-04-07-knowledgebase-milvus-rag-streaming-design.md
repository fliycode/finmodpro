# FinModPro 知识库、Milvus RAG 与流式问答重构设计

## 目标
本次重构同时解决三类问题，并以“上传后的文档能真实进入 Milvus、被检索命中并服务问答”为验收基准：

- 知识库页面当前状态不可信，上传者、时间、任务状态和可用性展示不完整
- RAG 链路仍存在偏内存兜底或弱可观测路径，无法证明正式 Milvus 已参与检索
- 智能问答仍是整段返回，缺少流式输出体验

## 设计原则
- 生产 RAG 以正式 Milvus 为唯一可信向量检索后端，不再依赖内存 `_VECTOR_STORE` 作为正式路径
- 知识库页面展示真实任务状态，而不是前端猜测或兜底字符串
- 上传成功不等于可检索，必须明确区分“文件已保存”和“已入库可检索”
- 问答接口采用 `RAG 优先，未命中则模型 fallback`，并明确标识回答模式
- 流式问答只覆盖生成阶段，检索阶段仍先同步完成

## LangChain / Milvus 参考实现方向
本次实现参考 LangChain 当前官方文档中的 Milvus 用法：
- `langchain_milvus.Milvus` 作为向量库集成层
- 连接参数使用 `connection_args={"uri": ..., "token": ..., "db_name": ...}`
- 检索侧使用 vector store / retriever 的思路，而不是 controller 内部直接堆业务逻辑

但不会把现有业务完全改写成 LangChain chain 风格。业务边界仍保持在项目自己的 `knowledgebase` / `rag` / `chat` service 中，LangChain 与 Milvus 只作为适配层。

## 后端重构
### 文档摄取链路
上传后文档需要经过以下真实阶段：
1. 文件保存
2. 文本解析
3. 文本切块
4. embedding 生成
5. 写入 Milvus collection
6. 标记为可检索

`Document.status` 与 `IngestionTask.current_step` 必须严格对应这些阶段。只有 Milvus 写入成功后，文档才能显示为 `indexed`。

### Milvus 检索主路径
正式检索统一走 Milvus，不再让 `rag/services/vector_store_service.py` 承担生产查询职责。内存检索如需保留，仅用于测试替身或本地隔离测试。

`/api/rag/retrieval/query` 与 `/api/chat/ask` 共用同一条真实检索链路，返回统一 citation 结构。检索结果至少包含：
- `document_id`
- `document_title`
- `chunk_id`
- `page_label`
- `snippet`
- `score`
- `metadata`

### 问答模式
问答服务统一支持两种回答模式：
- `cited`: 检索命中知识库引用后生成答案
- `fallback`: 未命中引用时，直接使用模型基于用户问题生成普通回答

响应中增加：
- `answer_mode`
- `answer_notice`

其中 `fallback` 必须明确提示“当前回答未命中知识库引用，仅基于通用模型能力生成”。

### 流式接口
保留现有 `/api/chat/ask` 作为兼容非流式接口，同时新增流式接口，例如 `/api/chat/ask/stream`。

流式接口行为：
- 先完成检索，确认 citations 与 answer mode
- 再以 SSE 或兼容浏览器流读取的形式持续返回 token
- 首包返回 `citations`、`answer_mode`、`answer_notice`
- 后续分片返回模型文本增量
- 结束时返回完成事件与总耗时

## 知识库页面重构
知识库页需要从“文档浏览”升级为“文档可用性工作台”，至少真实展示：
- 上传者
- 上传时间（本地化时间格式）
- 最近任务状态
- 处理步骤与错误信息
- chunk 数
- vector 数
- 是否已可用于问答
- 文档文本预览 / 解析结果

上传动作必须明确反馈：
- 文件已上传
- 摄取任务已启动
- 正在解析 / 切块 / 向量化
- 已入库可检索
- 失败原因

不再允许主界面出现：
- 上传者固定显示 `未知`
- 原始 ISO 时间串直接裸露
- 仅显示“已上传”却无法判断是否可检索

## 前端问答页重构
智能问答页默认走流式接口：
- assistant 消息边接收边渲染
- 命中知识库时展示 citations
- fallback 模式展示提示条
- 流式中断、接口错误和权限错误要有明确状态提示

保留非流式兼容能力，作为调试或降级路径。

## 测试要求
- 文档上传、摄取、Milvus 写入成功后，`/api/rag/retrieval/query` 可命中结果
- `Document.status` 与 `IngestionTask` 状态流转正确
- 知识库 API 返回上传者、时间、chunk/vector 数和任务状态
- `/api/chat/ask` 在 `cited` / `fallback` 两种模式下返回正确结构
- `/api/chat/ask/stream` 能返回首包元信息和后续文本分片
- 前端知识库页正确显示本地化时间与真实上传者
- 前端问答页支持流式渲染与 fallback 提示

## 非目标
- 普通用户多租户隔离
- 复杂 reranker 编排
- 文档权限体系重做
- 全量改写为 LangChain chain/agent 架构
- 流式文档摄取任务监控

## 验收标准
- 上传文档后，知识库页面能真实显示上传者、时间、任务进度和入库结果
- 文档入库成功后，问答与检索都能通过 Milvus 命中
- 没命中知识库时，问答仍可回答，但会明确标记为 fallback
- 智能问答页支持流式输出，不再只能等待整段返回
- 生产路径中不再依赖内存 `_VECTOR_STORE` 作为正式 RAG 后端
