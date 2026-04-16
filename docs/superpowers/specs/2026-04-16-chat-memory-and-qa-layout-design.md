# FinModPro 对话记忆与问答页重构设计

## 目标
本次设计同时解决用户端智能问答的两类问题：

- 对话数据问题：当前历史会话标题不是模型生成，且现有实现缺少真正的“工作记忆”和“长期记忆”分层，导致会话连续性和跨会话记忆能力都不稳定。
- 页面结构问题：当前问答页仍然偏工作台卡片式布局，对话主画布不够大，不像 ChatGPT 那样把注意力集中在消息流与输入动作上。

本次设计目标是把 FinModPro 的问答能力重构成“可持续对话工作区”：

1. 原始消息完整保存，历史记录可追溯。
2. 会话标题由模型根据首轮稳定意图生成。
3. 短期会话记忆与跨会话长期记忆分层管理。
4. 长期记忆支持查看、删除、置顶和证据回溯。
5. 问答页改成更大的主画布，同时保留历史会话和记忆治理能力。

## 现状问题
当前代码中的几个关键缺口已经明确：

- [`frontend/src/components/FinancialQA.vue`](/root/finmodpro/frontend/src/components/FinancialQA.vue) 在新建会话时直接用 `currentQuery.slice(0, 50)` 作为标题，这不是模型生成标题。
- [`backend/chat/models.py`](/root/finmodpro/backend/chat/models.py) 当前只有 `ChatSession` 和 `ChatMessage` 两层数据结构，没有 rolling summary，也没有长期记忆模型。
- [`backend/chat/services/session_service.py`](/root/finmodpro/backend/chat/services/session_service.py) 只负责把一轮问答持久化到 `ChatMessage`，但没有标题生成、摘要更新、长期记忆抽取的上层流程。
- [`frontend/src/style.css`](/root/finmodpro/frontend/src/style.css) 与 [`frontend/src/components/FinancialQA.vue`](/root/finmodpro/frontend/src/components/FinancialQA.vue) 共同限制了聊天区宽度，使问答页更像后台内容卡片，而不是主对话画布。

这些问题叠加后，导致“历史会话只像消息归档，不像真正的可持续对话上下文”。

## 设计结论
本次采用以下组合方案：

- 存储架构：`MySQL + Redis`
- 记忆模型：`原始消息层 + 会话工作记忆层 + 长期记忆层 + 检索编排层`
- 长期记忆作用域：`用户全局 + 项目/数据集`
- 长期记忆治理：支持 `查看 / 删除 / 置顶 / 证据回溯`
- 问答页布局：采用 `B1` 方案
  - 保留全局工作区导航，但压缩成更窄的图标轨
  - 聊天页历史会话改为按钮呼出的抽屉
  - 记忆面板改为按钮呼出的隐藏侧边栏
  - 中间区域改成更接近 ChatGPT 的大对话主画布

## 设计对比与取舍
### 记忆存储方案
本次明确不直接接入外部 memory layer。

#### 方案 A：MySQL-only
优点：

- 结构最简单
- 所有状态都能直接落到关系表

问题：

- 会话热状态、任务队列、重试状态、检索缓存都会挤进数据库
- 后续接向量检索时很难自然拆层

#### 方案 B：MySQL + Redis
这是本次选中的方案。

优点：

- MySQL 负责事实落库、治理和审计
- Redis 负责会话热状态、异步任务、检索缓存和幂等控制
- 与现有 Django 架构贴合，演进成本最低
- 为后续向量检索保留清晰升级口

#### 方案 C：直接接 Mem0 / Zep 一类外部记忆层
暂不采用。

原因：

- 当前项目的 `chat / rag / risk / llm` 边界仍应先在仓库内收束
- 现在最需要的是可靠可控的第一层能力，而不是额外平台抽象

### 问答页布局方案
本次最终采用 `B1`。

#### 方案 A：纯 ChatGPT 大画布
优点：

- 最接近通用聊天产品
- 对话沉浸感最强

问题：

- 长期记忆治理入口会偏隐藏
- 不适合当前项目已有的工作区导航和数据集范围能力

#### 方案 B：ChatGPT 主画布 + 记忆治理能力
这是大的方向。

在该方向下，进一步比较：

##### B1：保留全局侧边栏，但压缩成窄图标轨
优点：

- 不推翻现有工作区信息架构
- 聊天区仍可明显放大
- 历史与记忆都能通过按钮呼出，不再长期挤占横向空间

##### B2：把 QA 页全局导航上移到顶部
优点：

- 聊天页宽度最大
- 更接近纯聊天产品

问题：

- 需要让 QA 页脱离当前工作区壳层
- 会让工作区页面结构出现特殊分支

最终选择 `B1`，因为它兼顾空间效率和实现风险。

## 记忆分层设计
### 1. 原始消息层
职责：

- 保存所有原始用户消息和助手消息
- 作为审计源和问题回放真源
- 支撑导出、故障排查、证据追溯

设计原则：

- 原始消息必须全量保留，不允许只留摘要或首句
- 对话流式返回时，最终完整文本必须回写
- 删除长期记忆不应删除原始消息

### 2. 会话工作记忆层
职责：

- 支撑单个 `chat_session` 内的连续对话
- 通过 `rolling_summary + recent messages` 控制上下文长度
- 记录当前数据集/过滤条件和会话热状态

设计原则：

- 这是“本会话连续性”层，不是长期记忆
- 摘要更新失败不能阻断主聊天流程
- 优先保证上下文可用，再优化压缩质量

### 3. 长期记忆层
职责：

- 保存跨会话可复用的稳定信息
- 按用户和 scope 进行治理与检索
- 支撑个性化、项目连续性和工作习惯延续

自动长期记忆只允许写入以下类型：

- 用户稳定偏好
- 项目背景
- 已确认技术/业务事实
- 长期有效关注点和工作规则

绝不自动保留以下内容：

- 敏感信息
- 未确认推断
- 一次性上下文
- 原始整段聊天
- 高风险业务结论

### 4. 检索编排层
职责：

- 在每次提问时组装真正进入模型的上下文
- 避免把全部历史消息直接塞进 prompt
- 把记忆检索和 RAG 检索变成两个独立信号源

读取顺序固定为：

1. `rolling_summary`
2. 最近 N 轮原始消息
3. 命中的长期记忆
4. 命中的 RAG 文档

这保证会话连续性优先于长期记忆，长期记忆优先于外部文档证据。

## 数据模型设计
### ChatSession
在现有 [`backend/chat/models.py`](/root/finmodpro/backend/chat/models.py) 的 `ChatSession` 基础上扩展：

- `title`
- `title_status`
- `title_source`
- `rolling_summary`
- `summary_updated_through_message_id`
- `message_count`
- `last_message_at`
- `context_filters`

说明：

- `title` 是最终展示标题，不再由前端截断首句生成。
- `title_status` 用于区分 `pending / ready / failed`。
- `rolling_summary` 保存已压缩的会话摘要。
- `summary_updated_through_message_id` 用于避免重复摘要。

### ChatMessage
现有 `ChatMessage` 扩展为更完整的消息真源：

- `role`
- `message_type`
- `content`
- `status`
- `sequence`
- `citations_json`
- `model_metadata_json`
- `client_message_id`

说明：

- `status` 标识 `pending / complete / failed` 等状态。
- `citations_json` 保存回答关联的引用证据。
- `client_message_id` 用于前端幂等提交和消息去重。

### MemoryItem
新增长期记忆主表，建议位于 `backend/chat` 或独立 `backend/memory` 模块中。

核心字段：

- `user_id`
- `scope_type`
- `scope_key`
- `memory_type`
- `title`
- `content`
- `confidence_score`
- `source_kind`
- `status`
- `pinned`
- `fingerprint`
- `last_verified_at`

说明：

- `scope_type` 只允许 `user_global / project / dataset`
- `scope_key` 用于标识对应项目或数据集
- `memory_type` 只允许四类白名单类型
- `fingerprint` 用于抽取结果去重和合并

### MemoryEvidence
新增证据表，将长期记忆与来源会话、消息和抽取过程绑定：

- `memory_item_id`
- `session_id`
- `message_id`
- `evidence_excerpt`
- `extractor_version`
- `confirmation_status`

说明：

- 长期记忆必须能追溯到来源
- 前端“查看证据”能力依赖这张表

### MemoryActionLog
新增治理日志表，记录用户对长期记忆的显式操作：

- `memory_item_id`
- `actor_user_id`
- `action`
- `details_json`
- `created_at`

记录动作包括：

- 查看
- 删除
- 置顶
- 取消置顶
- 手动新增
- 手动修订

## Redis 职责边界
Redis 只负责以下几类热状态，不作为事实真源：

- 会话热窗口缓存
- 标题生成任务队列
- rolling summary 更新任务队列
- 长期记忆提取任务队列
- 检索缓存
- 并发锁和幂等键

这意味着：

- MySQL 存“最终可治理结果”
- Redis 存“处理中间态和加速状态”

## 对话写入流程
每次发送消息时，后端流程改成如下顺序：

1. 接收用户输入
2. 立即写入 `chat_message(user)`
3. 若会话不存在，则创建 `chat_session`
4. 创建 `assistant` 草稿消息或预留响应状态
5. 构建上下文
   - `rolling_summary`
   - 最近消息
   - 命中的长期记忆
   - 命中的 RAG 文档
6. 调用模型并流式返回
7. 回写完整 `assistant` 消息全文与引用
8. 更新 `message_count` 和 `last_message_at`
9. 异步触发三个后台任务
   - 标题生成
   - 摘要更新
   - 长期记忆提取

这比当前“先回答再统一落一轮消息”的模式更稳，能够避免消息未完整落库的情况。

## 标题生成设计
### 标题来源
会话标题由模型解析用户首轮稳定意图后生成，不再使用前端截断首句。

### 生成时机
建议异步执行：

- 新会话创建后先显示 `新对话`
- 第一轮消息完成后触发 `title job`
- 生成成功后回写 `chat_session.title`

### 失败回退
若标题生成失败：

- 保留 `新对话`
- 标记 `title_status=failed`
- 后台允许有限次重试

标题失败不影响对话和消息保存。

## Rolling Summary 设计
### 目标
在不丢失会话连续性的前提下，压缩较早消息，避免上下文无限增长。

### 策略
建议采用“最近 N 轮原始消息 + 已有 rolling summary”的迭代模式：

- 最近消息保留原文
- 早期内容折叠进 `rolling_summary`
- 每次更新都记录更新到哪一条消息

### 失败回退
若摘要任务失败：

- 不阻断主会话
- 读取链路退回更多原始消息

## 长期记忆抽取与治理
### 抽取原则
长期记忆抽取只处理白名单内容，并且默认保守：

- 宁可少记，不可误记
- 未确认推断不入库
- 高风险业务结论不入库
- 敏感信息不入库

### Scope 规则
长期记忆先支持两层作用域：

- `用户全局`
- `项目/数据集`

读取时先查用户全局，再叠加当前项目或数据集 scope。

### 冲突处理
若新记忆与已有记忆冲突：

- 不自动覆盖
- 生成候选或冲突状态
- 等待用户在治理界面处理

### 用户操作
长期记忆必须支持：

- 查看列表
- 删除
- 置顶
- 查看证据来源

删除与置顶的语义：

- 删除影响 `memory_item.status`
- 置顶只改变读取优先级
- 两者都不删除原始聊天消息

## 问答页布局设计
### 总体布局
问答页采用 `B1`：

- 保留全局工作区导航，但压缩成窄图标轨
- 历史会话通过顶部按钮呼出
- 记忆治理面板通过顶部按钮呼出
- 中间区域最大化给消息流和输入框

### 工作区壳层
影响文件：

- [`frontend/src/layouts/WorkspaceLayout.vue`](/root/finmodpro/frontend/src/layouts/WorkspaceLayout.vue)
- [`frontend/src/components/ui/AppSidebar.vue`](/root/finmodpro/frontend/src/components/ui/AppSidebar.vue)
- [`frontend/src/style.css`](/root/finmodpro/frontend/src/style.css)

调整方向：

- 将工作区侧边栏收缩为更窄的图标轨
- 弱化文字密度，释放给主内容区域更多横向宽度
- 保持其它工作区页面仍可复用同一壳层

### 聊天主画布
影响文件：

- [`frontend/src/components/FinancialQA.vue`](/root/finmodpro/frontend/src/components/FinancialQA.vue)
- [`frontend/src/views/workspace/WorkspaceQaView.vue`](/root/finmodpro/frontend/src/views/workspace/WorkspaceQaView.vue)

调整方向：

- 移除偏重 B 端卡片感的页面结构
- 放宽消息区最大宽度
- 让引用跟随消息折叠展示，不另设独立常驻栏
- 输入框固定在底部，形成稳定工作底座

### 历史会话
影响文件：

- [`frontend/src/components/ChatHistory.vue`](/root/finmodpro/frontend/src/components/ChatHistory.vue)
- [`frontend/src/api/chat.js`](/root/finmodpro/frontend/src/api/chat.js)

调整方向：

- 历史会话改为按钮呼出的抽屉
- 列表展示 AI 标题、最近更新时间、最新摘要预览
- 当前会话打开后自动关闭抽屉

### 记忆面板
建议新增组件，例如：

- `frontend/src/components/ChatMemoryDrawer.vue`
- `frontend/src/components/ChatMemoryList.vue`

交互规则：

- 默认隐藏
- 点击按钮后以右侧抽屉或侧滑面板形式出现
- 展示置顶记忆、最近命中记忆、最近新增记忆
- 支持查看、删除、置顶、查看证据

### 窄屏策略
在移动端或窄屏：

- 全局侧边栏仍保持最轻量状态
- 历史与记忆均使用抽屉
- 输入框固定在底部
- 会话标题和按钮保留在顶部轻量条

## API 与服务边界
### 现有接口继续保留
沿用现有 chat 路由：

- [`backend/chat/controllers/ask_controller.py`](/root/finmodpro/backend/chat/controllers/ask_controller.py)
- [`backend/chat/controllers/session_controller.py`](/root/finmodpro/backend/chat/controllers/session_controller.py)

### 需要新增或扩展的能力
建议新增：

- 会话标题与摘要字段的返回
- 长期记忆列表接口
- 长期记忆删除接口
- 长期记忆置顶接口
- 长期记忆证据查看接口

不要求本次直接引入复杂的新接口范式，仍沿用当前后端统一响应风格。

## 异常处理设计
### 标题生成失败
- 会话仍可用
- 保留 `新对话`
- 允许后台重试

### 摘要生成失败
- 不阻断主聊天链路
- 回退到更多原始消息拼接

### 长期记忆抽取失败
- 直接跳过，不入库
- 不影响当前回复

### 记忆冲突
- 不自动覆盖已有已确认记忆
- 标记冲突状态，交给用户处理

### 会话与记忆治理失败
- 前端展示可读错误
- 不让失败状态污染主消息流

## 测试策略
### 后端
扩展 [`backend/chat/tests.py`](/root/finmodpro/backend/chat/tests.py)，覆盖：

- 完整消息持久化
- 标题异步回写
- rolling summary 更新
- 长期记忆白名单过滤
- scope 检索顺序
- 删除与置顶治理

### 前端
扩展现有前端测试目录，覆盖：

- 历史项显示 AI 标题
- 历史抽屉与记忆抽屉开合
- 记忆列表治理状态
- 问答页主画布布局逻辑

### 集成验证
至少验证以下完整链路：

1. 发送第一句
2. 用户消息立即落库
3. 助手消息完整回写
4. 会话标题异步生成
5. 第二轮继续对话
6. rolling summary 更新
7. 命中长期记忆
8. 前端可以查看、删除、置顶该记忆

## 分阶段实施建议
### Phase 1：修正会话真源
目标：

- 修复消息全量保存
- 修复标题生成逻辑
- 修复历史会话预览与详情展示

### Phase 2：引入会话工作记忆
目标：

- 引入 `rolling_summary`
- 用 Redis 承接标题、摘要任务编排
- 固化上下文组装顺序

### Phase 3：引入长期记忆与问答页重构
目标：

- 新增长期记忆模型、证据表、治理日志
- 完成长期记忆治理接口
- 把问答页改为 `B1` 主画布布局

## 验收标准
- 原始消息全量保存，历史会话不再出现“只剩首句”的问题
- 会话标题由模型生成，而不是前端截断首句
- 会话具备 rolling summary，且失败时可安全回退
- 长期记忆只写入白名单内容，支持查看、删除、置顶和证据回溯
- 问答页主画布明显放大
- 历史与记忆不再常驻挤占主画布，而由按钮呼出
- 工作区导航压缩后不破坏其它页面结构

## 非目标
- 本次不直接接入向量库作为长期记忆主检索层
- 本次不直接引入 Mem0、Zep 等外部 memory platform
- 本次不把长期记忆做成自动黑盒系统
- 本次不改变现有 RAG 文档证据的基础职责
