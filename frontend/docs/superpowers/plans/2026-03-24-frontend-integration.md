# FinModPro 前端第一阶段联调版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成前端登录/注册与后端 API 的联调，加入加载状态和反馈提示，对齐登录字段契约。

**Architecture:** 抽象 API 配置层（已基础实现），组件内维护加载与反馈状态，调用 `src/api/auth.js` 服务。

**Tech Stack:** Vue 3 (Composition API), Fetch API, Vite.

---

### Task 1: 调整登录表单字段与 UI 反馈

**Files:**
- Modify: `src/App.vue`

- [ ] **Step 1: 更新 `formData` 与 `errors` 结构**
  - 为登录增加 `loginUsername` 字段（避免与注册用户名冲突或混淆）。
  - 增加 `isLoading`, `statusMsg`, `statusType` (success/error) 响应式变量。

- [ ] **Step 2: 修改模板中的登录字段**
  - 将登录时的 "用户名 / 电子邮箱" 改为 "用户名"。
  - 绑定到 `formData.loginUsername`。
  - 类型改为 `text` 而不是 `email`。

- [ ] **Step 3: 增加加载状态与反馈 UI**
  - 在提交按钮增加 `disabled` 状态。
  - 在表单上方或下方增加全局反馈提示条。

- [ ] **Step 4: 更新验证逻辑**
  - 登录验证只检查 `loginUsername` 和 `password`。

- [ ] **Step 5: 接入 `authApi` 调用**
  - 在 `handleSubmit` 中根据 `activeTab` 调用 `authApi.login` 或 `authApi.register`。
  - 处理成功：存储 token (暂时存 localStorage)，提示成功。
  - 处理失败：提示后端返回的 `message`。

### Task 2: 完善 API 层配置 (可选/检查)

**Files:**
- Modify: `src/api/config.js`
- Modify: `src/api/auth.js`

- [ ] **Step 1: 确保 `config.js` 正确处理 `baseURL`**
  - 检查是否支持 `VITE_API_BASE_URL` 环境变量。

- [ ] **Step 2: 确保 `auth.js` 契约对齐**
  - Login: `{ username, password }`
  - Register: `{ username, password, email }`

### Task 3: 更新进度文档

**Files:**
- Modify: `FRONTEND_PROGRESS.md`

- [ ] **Step 1: 记录已完成项**
- [ ] **Step 2: 写入后端接口契约说明**
- [ ] **Step 3: 写入运行验证方式**

### Task 4: 构建验证

- [ ] **Step 1: 执行构建**
  - Run: `npm run build`
- [ ] **Step 2: 确认无构建错误**
