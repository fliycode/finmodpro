# FinModPro 前端开发进度

## 2026-03-26 (去 mock 化与后端对齐)
- [x] **知识库 API 联调**: `src/api/knowledgebase.js` 接入 `POST /api/knowledgebase/documents` 和 `GET /api/knowledgebase/documents`。
  - 支持单文件上传（Multipart）。
  - 对齐文档处理状态：`uploaded`, `parsed`, `chunked`, `indexed`, `failed`。
- [x] **RAG 问答 API 联调**: `src/api/qa.js` 接入 `POST /api/chat/ask`。
  - 适配引用 (Citations) 结构：支持 `document_title`, `doc_type`, `source_date`, `page_label`, `snippet` 等字段。
  - 在适配层处理后端字段差异（如 `rerank_score` 映射）。
- [x] **对话历史 API 联调**: `src/api/chat.js` 接入 `/api/chat/history` 和 `/api/chat/sessions`。
  - 统一会话列表与详情的数据结构映射。
- [x] **适配层收口**: 所有 API 模块统一使用 `config.js` 的配置与 `auth-storage.js` 的 Token。
- [x] **构建验证**: 运行 `npm run build` 确认生产环境构建通过。

## 2026-03-24 (管理员演示增强)
- [x] **管理员 API 模块**: 实现 `src/api/admin.js`，支持用户列表、角色组列表及用户角色更新。
- [x] **用户管理仪表盘**: 实现 `src/components/AdminUsers.vue`。
  - 支持用户列表展示。
  - 实现搜索（用户名/邮箱）与角色筛选功能。
  - 实现角色编辑抽屉，支持勾选角色组并同步后端。
  - 实现局部刷新逻辑，更新后立即反映在列表中。
- [x] **导航集成**: 在 `App.vue` 中集成视图切换逻辑。
  - 管理员登录后可看到并点击“管理后台”进入。
  - 提供“返回主页”按钮。
- [x] **视觉语言一致性**: 延续原有的配色方案、阴影和圆角风格，确保 UI 统一。
- [x] **构建验证**: 运行 `npm run build` 确认生产环境构建通过。

## 2026-03-24 (RBAC 功能集成完成)
- [x] **扩展 Auth API**: 支持 `GET /api/auth/me` 获取当前用户信息、角色及权限。
- [x] **本地存储增强**: 实现 `src/lib/auth-storage.js`，支持持久化存储 token、角色组和权限列表。
- [x] **权限校验助手**: 实现 `src/lib/permission.js`，提供 `hasPermission`, `hasGroup`, `isAdmin` 等便捷校验工具。
- [x] **登录后拉取 Profile**: 登录成功后自动调用 `/api/auth/me` 并更新本地权限缓存。
- [x] **UI 权限控制演示**:
  - 在侧边栏/品牌区域展示当前登录用户的角色与权限列表。
  - 实现基于 `isAdmin` 的按钮禁用/锁定演示。
  - 实现登录后的欢迎界面，展示基于角色的差异化提示。
- [x] **构建验证**: 运行 `npm run build` 确认生产环境构建通过。

## 2026-03-23
- [x] 清理默认 Vite/Vue 模板残留文件
- [x] 重构 `src/App.vue` 为登录/注册双 Tab 页面
- [x] 实现响应式布局（适配移动端）
- [x] 加入品牌卖点展示区域
- [x] 加入 Google/GitHub 登录占位按钮
- [x] 加入忘记密码入口
- [x] 完善基础前端校验
- [x] 补全注册表单字段

## 后端接口契约 (Auth)

### 1. 注册 (Register)
- **Endpoint**: `POST /api/auth/register`
- **Request Body**:
  ```json
  {
    "username": "...",
    "password": "...",
    "email": "..."
  }
  ```
- **Success Response**:
  ```json
  {
    "message": "...",
    "access_token": "...",
    "access_token_type": "bearer",
    "expires_in": 3600,
    "user": { ... }
  }
  ```

### 2. 登录 (Login)
- **Endpoint**: `POST /api/auth/login`
- **Request Body**:
  ```json
  {
    "username": "...",
    "password": "..."
  }
  ```
- **Success Response**: 同注册。
- **Error Response**:
  ```json
  { "message": "错误原因" }
  ```

## 运行与验证

1. **安装依赖**: `npm install`
2. **启动开发服务**: `npm run dev`
3. **环境变量配置**: 可在 `.env` 中设置 `VITE_API_BASE_URL` 指向后端服务。默认为 `http://localhost:8000`。
4. **构建验证**: `npm run build`

## 待办事项
- [ ] 丰富品牌卖点图标
- [ ] 添加深色模式支持
- [ ] 实现登录后的页面重定向逻辑
