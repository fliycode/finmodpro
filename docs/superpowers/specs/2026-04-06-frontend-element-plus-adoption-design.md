# FinmodPro Frontend Element Plus Adoption Design

## Context

当前 `frontend` 是一个轻量 Vue 3 + Vue Router + 手写 CSS 的前端壳。依赖极少，页面结构已经成型，包含两类明显不同的界面：

1. 业务工作区（QA、风险、知识库、历史）
2. 管理后台（总览、模型配置、用户管理、评测）

现状的优点是轻、快、易改；问题是基础 UI 设施开始重复建设，尤其在后台页面里，表格、表单、筛选器、通知反馈、弹层与 tabs 会越来越重。继续完全手写虽然能工作，但维护成本会持续上升。

用户已明确选择方案 A：接入 Element Plus，但不立即引入 Tailwind CSS 和 Pinia。

## Goals

- 为后台和部分工作区高频交互提供成熟的 B 端组件基础设施
- 保留现有路由、页面结构和大部分业务组件边界，避免整仓大重构
- 强化“管理后台”与“业务工作区”的视觉差异，而不是把所有页面统一做成后台模板风格
- 控制迁移风险，让页面可以分批替换、每一步都能上线

## Non-Goals

- 本轮不引入 Tailwind CSS
- 本轮不做 Pinia 全局状态迁移
- 本轮不重写 QA 工作台的对话区体验
- 本轮不推翻当前 layout / router / api 组织方式

## Options Considered

### Option 1: 保持现状，继续手写 CSS 与基础控件

优点：
- 迁移成本最低
- 不引入新依赖
- 保持当前轻量性

缺点：
- 表格、表单、筛选、提示、弹层、分页等能力会持续重复造轮子
- 随页面增长，视觉一致性和交互稳定性会恶化
- 管理后台的产品成熟度提升缓慢

### Option 2: 一次性切到 Element Plus + Tailwind + Pinia

优点：
- 中长期体系更完整
- 理论上更现代化

缺点：
- 属于架构迁移，不是简单升级
- 当前项目规模下收益不匹配成本
- Tailwind 与 Element Plus 会引入额外设计约束成本
- Pinia 目前没有足够强的共享状态需求支撑立刻迁移

### Option 3: 渐进接入 Element Plus，优先后台与风险页基础交互件（推荐）

优点：
- 迁移成本与收益最平衡
- 对后台页面提升最明显
- 工作区页面能保留较轻的内容导向体验
- 可以逐页替换，失败面小

缺点：
- 迁移期会短暂存在“自定义样式 + 组件库”混合态
- 需要控制主题变量，避免视觉打架

## Recommended Approach

采用 Option 3：

- 全局接入 Element Plus
- 保留现有应用骨架与路由
- 优先替换 Admin 页面中高收益基础件
- 风险页优先替换 tabs / filters / table / button 等交互控件
- QA 工作台保持当前自定义对话 UI，只在全局反馈与局部输入控件层面按需接入

## Architecture

### 1. Bootstrap Layer

在 `src/main.js` 中接入 Element Plus，并引入其基础样式。应用启动仍保持：

- `createApp(App)`
- `use(router)`
- 新增 `use(ElementPlus)`

这是一层纯基础设施变更，不影响业务路由和 API 调用方式。

### 2. UI Foundation Layer

保留当前 `style.css` 作为品牌壳与 layout 样式主文件，但职责收口：

- 负责全局布局、品牌色、工作区 / 后台视觉语言差异
- 不再继续手写通用 B 端基础控件
- 对 Element Plus 做必要 token 覆盖（颜色、圆角、阴影、间距）

这意味着：
- `layout / shell / hero / content rhythm` 继续由自定义 CSS 控制
- `table / form / select / date picker / tabs / dialog / message` 逐步交给 Element Plus

### 3. Page Migration Boundaries

#### Admin 页面
优先迁移以下页面：
- `AdminOverviewView`
- `AdminModelsView`
- `AdminUsersView`
- `AdminEvaluationView`

策略：
- 维持页面级容器与布局骨架
- 把内部内容改为 Element Plus 为主
- 让后台页面表现出更标准、更稳定的运营后台气质

#### Workspace 风险页
优先迁移：
- tabs
- 筛选表单
- 表格
- 操作按钮

保留：
- 页面 hero
- 工作区整体风格
- 报告阅读区的大块内容展示节奏

#### Workspace QA 页
暂不重做聊天区。继续使用当前自定义 UI。
只允许做：
- 全局消息反馈整合
- 必要按钮 / 输入态规范化

### 4. State Strategy

本轮不引入 Pinia。

原因：
- 当前共享状态主要仍是局部页面级状态
- 现有 `lib/*` 与组件内 `ref/reactive` 还能承受
- 先完成 UI 基础设施升级，再观察真正需要跨页共享的状态边界

未来若出现以下情况，再迁到 Pinia：
- 用户 / 权限 / 会话要跨页共享
- 筛选条件跨页面复用
- 顶栏与工作区出现统一全局状态联动

## Files and Responsibilities

### Directly Modified
- `frontend/package.json`
  - 增加 `element-plus`
- `frontend/src/main.js`
  - 接入 Element Plus
- `frontend/src/style.css`
  - 增加 Element Plus 主题兼容和页面壳层 token
- `frontend/src/lib/flash.js`
  - 统一全局消息反馈接入 Element Plus message

### Likely Modified in First Migration Batch
- `frontend/src/components/ModelConfig.vue`
- `frontend/src/components/AdminUsers.vue`
- `frontend/src/components/OpsDashboard.vue`
- `frontend/src/components/RiskSummary.vue`

### Kept Mostly Stable
- `frontend/src/router/*`
- `frontend/src/layouts/*`
- `frontend/src/api/*`
- `frontend/src/components/FinancialQA.vue`

## Error Handling

Element Plus 接入不应改变现有 API error handling 模型。
原则：
- 请求失败逻辑仍在业务组件 / API 层处理
- 展示方式逐步统一到 `ElMessage` / 明确的 empty / error state
- 不把 UI 组件库当作业务错误恢复机制

## Testing Strategy

- 先保证 `npm run build` 持续通过
- 对受影响的纯逻辑模块继续保持现有单元测试
- 组件库接入主要用页面可运行性与构建稳定性验证
- 每一批替换后至少验证：
  - Admin 页面可进入
  - 风险页筛选与表格交互可用
  - 全局消息反馈正常显示

## Rollout Plan Summary

1. 接入 Element Plus 基础设施
2. 替换全局消息反馈
3. 优先迁移 Admin 页面内部控件
4. 迁移 RiskSummary 的交互控件
5. 保持 QA 工作台自定义风格
6. 视后续复杂度再决定是否引入 Pinia

## Why This Design

这个方案的关键不是“引不引库”，而是控制产品演化方向：

- 后台页面应该更标准化、工程化
- 工作区页面应该保持内容导向和业务感
- 组件库是为高收益交互减负，不是为了把全部页面做成同一种味道

因此，Element Plus 应该成为 finmodpro 的基础交互设施，而不是 UI 风格的唯一来源。