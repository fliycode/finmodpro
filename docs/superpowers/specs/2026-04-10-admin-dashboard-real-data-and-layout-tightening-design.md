# FinModPro 管理端真实数据仪表盘与壳层收紧设计

## 目标
本次调整聚焦管理员端首页和管理壳层，解决两个当前问题：

- 管理端首页仍混有 mock 数据、兜底占位值和装饰性摘要，无法作为真实治理工作台使用。
- 左侧侧边栏和顶部管理员标题区占用过多横向与纵向空间，压缩了核心内容区，影响实际使用效率。

目标是把管理员端首页改成“真实数据驱动的治理总览”，同时把整体壳层变得更紧凑，让核心功能区明显变大。

## 设计结论
本次采用“治理优先，但保留趋势图”的均衡方案。

首页信息顺序调整为：

1. 待处理事项与平台当前判断
2. 真实核心指标
3. 关键趋势与分布图
4. 最近活动与运行证据

视觉方向延续现有浅色机构风格，但压缩无效留白和大块标题区，去掉当前偏“展示型”而不是“工作型”的占位内容。

## 真实数据范围
管理员端首页不再依赖前端 mock 和兜底假值。后台 `/api/dashboard/stats` 统一返回首页所需真实聚合数据，前端只做展示和轻量格式化。

### 核心统计
- `knowledgebase_count`：当前知识资产分组数量，暂按现有后端约定保持单知识库或隐式知识库口径。
- `document_count`：文档总数。
- `indexed_document_count`：已完成索引的文档数量。
- `processing_document_count`：处于上传、解析、切块、索引过程中的文档数量。
- `failed_document_count`：入库失败文档数量。
- `risk_event_count`：风险事件总量。
- `pending_risk_event_count`：待审核风险事件数量。
- `high_risk_event_count`：高风险与严重风险事件数量。
- `active_model_count`：当前启用模型数量。
- `chat_request_count_24h`：近 24 小时问答请求量。
- `retrieval_hit_rate_7d`：近 7 天检索命中率，按 `RetrievalLog.result_count > 0` 计算。

### 图表数据
- `chat_requests_7d`：近 7 天按天统计的问答请求量。
- `retrieval_hits_7d`：近 7 天按天统计的命中请求量，用于和问答请求量形成对照。
- `risk_level_distribution`：按 `low / medium / high / critical` 统计风险事件分布。
- `document_status_distribution`：按 `uploaded / parsed / chunked / indexed / failed` 统计文档状态分布。

### 最近活动
首页不再调用 `opsApi` 的前端假日志。最近活动改为基于真实数据拼装的统一活动流，来源按优先级组合：

- 最新入库任务
- 最新风险事件
- 最新检索日志
- 最新模型评测记录

活动流只保留最近若干条，每条统一输出时间、类型、简述、状态色。

## 后端设计
### 统计服务
扩展 [`dashboard_service.py`](/root/finmodpro/backend/systemcheck/services/dashboard_service.py)，由单纯返回 4 个计数改为返回完整首页聚合载荷。

实现原则：

- 所有指标都从当前真实模型表统计，不在接口层硬编码展示值。
- 聚合逻辑集中在 `systemcheck`，前端不再各自拼口径。
- 保持单接口返回，避免管理员首页首屏依赖多个串行请求。

### 数据来源
- 文档相关：`knowledgebase.models.Document`、`knowledgebase.models.IngestionTask`
- 风险相关：`risk.models.RiskEvent`
- 模型相关：`llm.models.ModelConfig`
- 问答与检索相关：`rag.models.RetrievalLog`
- 评测与活动补充：`llm.models.EvalRecord`

### 兼容性
保留现有已使用字段名，新增字段以增量方式加入，不破坏已存在调用方。

## 前端设计
### 页面结构
管理员端首页改成四段式：

1. `Action Summary`
   - 左侧显示当前态势判断和最近刷新时间
   - 右侧显示高优先事项卡，如待审风险、失败入库、低命中检索
   - 顶部摘要区整体高度收窄，不再使用大面积展示型横幅

2. `Core Metrics`
   - 四张真实指标卡
   - 只显示真实值和语义说明，不显示假增长、假环比

3. `Operational Charts`
   - 图 1：近 7 天问答请求与检索命中趋势
   - 图 2：风险等级分布
   - 图 3：文档状态分布

4. `Recent Activity`
   - 最近活动列表
   - 运行证据列表

### 图表策略
引入 ECharts，保持图表数量克制，只做管理员决策真正需要的图。

- 折线图：近 7 天问答请求量与检索命中量双序列展示
- 环形图或条形图：风险等级分布
- 横向条形图：文档状态分布

图表要求：

- 数据必须全部来自真实后端聚合字段
- 不使用装饰性渐变图、假趋势线、模拟波峰波谷
- 配色遵循现有状态语义，风险用红，警示用橙，中性统计用蓝灰

### 壳层收紧
#### 侧边栏
- 侧边栏宽度从当前约 `264px` 收窄到约 `224px`
- 缩小品牌区图标、上下内边距和组间距
- 保留两组导航结构，但降低空白消耗
- 当前页高亮更紧凑，不再依赖大块面状背景

#### 顶栏
- 顶栏整体 padding 收窄
- 品牌 logo、标题、副标题整体缩小一档
- `管理员端 / 管理控制台 / 面向平台治理...` 变为更薄的单行标题区
- 副标题缩成一句更短说明，例如“平台治理、风险审查与模型运维总览”

#### 内容区
- 内容区可用宽度相应增加
- 仪表盘首屏优先布局主工作内容，不让标题和装饰占据第一屏

## 组件改造范围
- [`frontend/src/components/OpsDashboard.vue`](/root/finmodpro/frontend/src/components/OpsDashboard.vue)
- [`frontend/src/api/dashboard.js`](/root/finmodpro/frontend/src/api/dashboard.js)
- [`frontend/src/api/ops.js`](/root/finmodpro/frontend/src/api/ops.js)
- [`frontend/src/layouts/AdminLayout.vue`](/root/finmodpro/frontend/src/layouts/AdminLayout.vue)
- [`frontend/src/style.css`](/root/finmodpro/frontend/src/style.css)
- 视情况新增图表封装组件，例如 `AdminTrendChart`、`AdminDistributionChart`
- [`backend/systemcheck/services/dashboard_service.py`](/root/finmodpro/backend/systemcheck/services/dashboard_service.py)
- [`backend/systemcheck/tests.py`](/root/finmodpro/backend/systemcheck/tests.py)

## 测试策略
### 后端
- 为 `/api/dashboard/stats` 新增测试，验证新增聚合字段和图表数据结构
- 覆盖无数据、部分数据、混合状态数据三种场景
- 验证命中率和近 7 天统计口径正确

### 前端
- 为管理员首页新增测试，验证真实接口字段映射，不再依赖 mock 默认值
- 验证图表配置在空数据和有数据时都能稳定渲染
- 验证侧边栏与顶栏 class 变化后的布局结构

### 验收标准
- 管理端首页不再展示任何 hardcoded 假统计
- 管理员可以在首页直接看到待审事项、真实趋势和最近活动
- 左侧导航明显收窄，核心内容区显著变宽
- 顶部管理员标题区高度下降，不再抢占首屏注意力
- 页面在桌面和移动宽度下都保持可用

## 非目标
- 不在这次改动里重做整个管理端导航结构
- 不新增复杂多筛选的大屏分析页
- 不引入需要单独后端任务的复杂 BI 预计算
- 不改变现有业务模块的权限边界
