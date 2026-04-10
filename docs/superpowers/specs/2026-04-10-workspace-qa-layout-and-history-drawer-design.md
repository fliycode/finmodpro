# FinModPro 智能问答页扩展对话区与历史抽屉设计

## 目标
本次调整聚焦用户端智能问答页与用户端壳层，解决三个当前问题：

- 智能问答页顶部仍保留一块独立介绍卡片，消耗了首屏高度，但对实际问答工作帮助很小。
- 对话区主体偏窄，消息区域和输入区没有形成“主工作面”，在大屏上显得局促。
- 历史会话选择器长期占据页面一整行，但用户在多数时间里并不需要持续展开它。

目标是把智能问答页改成更接近“连续工作台”的结构，让用户一进入页面就把注意力放在对话、引用证据和当前输入动作上，同时继续压小用户端顶部栏。

## 设计结论
本次采用“对话主体最大化 + 历史会话默认收起”的方案。

页面优先级调整为：

1. 顶部轻量操作栏
2. 大尺寸对话主区域
3. 固定感更强的输入区
4. 需要时才展开的历史会话抽屉

## 交互设计
### 顶部介绍卡片
移除 [`WorkspaceQaView.vue`](/root/finmodpro/frontend/src/views/workspace/WorkspaceQaView.vue) 里的整张问答页 hero 卡片：

- 不再显示“问答工作台 / 智能问答 / 说明文案”这块独立卡片
- 页面内容从进入工作区后直接落到问答组件
- 页面标题职责交给全局顶栏承担，不再在页内重复

### 历史会话
历史会话从“页面常驻一行工具条”调整为“默认收起的右侧抽屉”：

- 默认关闭，不占据主对话区宽度或高度
- 顶部轻量操作栏提供“历史会话”按钮
- 点击后从右侧展开抽屉，展示会话列表
- 选择会话后自动加载，并可选择关闭抽屉
- 新对话按钮保留在顶部操作栏，不放到抽屉内部作为主入口

采用右侧抽屉而不是左侧抽屉，是为了避免用户端已经存在的全局左导航再叠加第二层左栏，影响空间秩序。

## 页面结构
智能问答页最终结构改成三层：

### 第一层：轻量操作栏
位于对话主区域上方，但高度明显小于当前 hero。

包含：
- 当前会话状态，例如“新对话”或当前会话标题
- “历史会话”按钮
- “新对话”按钮

不再放长说明文案，不再用大块卡片式页面标题。

### 第二层：主对话区
这是页面绝对核心。

调整方向：
- 提高整体可用高度
- 放宽消息最大宽度限制
- 保持用户消息与 AI 消息左右分区，但让内容在桌面宽度下更舒展
- 系统提示消息继续保留，但弱化视觉权重
- 引用依据区继续跟随消息展示，不单独分栏抢占横向空间

### 第三层：输入区
输入区保留在页面底部，但更像完整工作区底座：

- 文本框更宽
- 发送按钮占用的横向空间更小
- 输入区内边距更克制但更稳
- 视觉上与消息区保持一体化

## 布局设计
### 对话宽度
当前 [`FinancialQA.vue`](/root/finmodpro/frontend/src/components/FinancialQA.vue) 中消息体的宽度上限偏保守。

本次改动：
- 放宽消息容器的最大宽度
- 放大聊天窗口最小高度
- 让问答页在桌面端更像“主工作台”，不是“居中小卡片”

### 页面高度
在移除 hero 卡片后：
- 问答页应更早进入消息区
- 首屏应尽可能同时看到若干轮消息与完整输入区
- 移动端仍保留垂直堆叠，但避免输入区拥挤

### 壳层收紧
用户端顶部栏继续压小一档：

- [`WorkspaceLayout.vue`](/root/finmodpro/frontend/src/layouts/WorkspaceLayout.vue) 中“业务工作区”副标题缩成更短一句
- 复用已收紧过的全局 topbar 样式，不再让用户端栏显得比内容更重
- 用户端侧边栏不重做结构，但保留更紧凑的全局间距

## 组件改造范围
- [`frontend/src/views/workspace/WorkspaceQaView.vue`](/root/finmodpro/frontend/src/views/workspace/WorkspaceQaView.vue)
- [`frontend/src/components/FinancialQA.vue`](/root/finmodpro/frontend/src/components/FinancialQA.vue)
- [`frontend/src/components/ChatHistory.vue`](/root/finmodpro/frontend/src/components/ChatHistory.vue)
- [`frontend/src/layouts/WorkspaceLayout.vue`](/root/finmodpro/frontend/src/layouts/WorkspaceLayout.vue)
- [`frontend/src/style.css`](/root/finmodpro/frontend/src/style.css) 视情况只做很小的全局同步

## 技术实现
### 会话抽屉
优先使用现有 Element Plus 能力实现抽屉，不额外引入新的状态管理层。

组件关系建议：
- `FinancialQA` 作为主状态源，管理当前会话、消息列表、抽屉开关
- `ChatHistory` 改造成更适合嵌入抽屉的列表面板
- `ChatHistory` 保持 `open-session` 事件输出，不负责路由

### 状态逻辑
抽屉引入后，保留现有逻辑：
- 读取历史会话
- 打开某个会话
- 创建新会话
- 路由 query 中的 `session` 保持兼容

本次不改 chat API 契约，不增加新的后端接口。

## 测试策略
### 前端
- 为会话抽屉相关的纯逻辑新增或扩展测试
- 验证新对话状态、历史会话按钮和会话切换逻辑
- 验证问答页不再渲染 hero 卡片文字

### 构建验证
- `npm test`
- `npm run build`

## 验收标准
- 智能问答页首屏不再出现独立 hero 卡片
- 对话区明显更大，消息阅读宽度更舒展
- 历史会话默认收起，不再长期占据页面主区域
- 用户端顶部“业务工作区”栏进一步压小
- 页面在桌面和移动端均可用

## 非目标
- 不重做整个用户端导航结构
- 不改 chat 后端协议
- 不把引用依据改成独立侧栏
- 不新增复杂的会话筛选、搜索或分组能力
