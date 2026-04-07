# Frontend Element Plus Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce Element Plus into finmodpro frontend and migrate high-value admin/risk interactions without rewriting the whole UI stack.

**Architecture:** Keep the existing Vue + Vue Router application shell and custom layout CSS, but move high-value B-end controls to Element Plus. Admin pages become the primary migration target; workspace QA remains custom while risk interactions are partially upgraded.

**Tech Stack:** Vue 3, Vue Router, Vite, Element Plus, existing custom CSS

---

## File Structure

- `frontend/package.json`
  - Add Element Plus dependency.
- `frontend/src/main.js`
  - Register Element Plus globally.
- `frontend/src/style.css`
  - Add Element Plus theme overrides and compatibility rules.
- `frontend/src/lib/flash.js`
  - Bridge current flash API to Element Plus message.
- `frontend/src/components/OpsDashboard.vue`
  - Replace admin overview internals with Element Plus cards/table-friendly shell where needed.
- `frontend/src/components/ModelConfig.vue`
  - Migrate forms/tables/actions to Element Plus.
- `frontend/src/components/AdminUsers.vue`
  - Migrate table/filter/action controls to Element Plus.
- `frontend/src/components/RiskSummary.vue`
  - Replace tabs, filters, table, and action buttons with Element Plus primitives while keeping workspace page shell.

## Task 1: Install and bootstrap Element Plus

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.js`
- Test: `frontend/package.json` via install + `npm run build`

- [ ] **Step 1: Add Element Plus dependency to `frontend/package.json`**

```json
{
  "dependencies": {
    "element-plus": "^2.11.1",
    "vue": "^3.5.30",
    "vue-router": "^4.6.3"
  }
}
```

- [ ] **Step 2: Install dependencies**

Run: `npm install`
Expected: package-lock updates and `element-plus` appears in installed dependencies

- [ ] **Step 3: Register Element Plus in `frontend/src/main.js`**

```js
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router/index.js'

createApp(App).use(router).use(ElementPlus).mount('#app')
```

- [ ] **Step 4: Run build to verify bootstrap is valid**

Run: `npm run build`
Expected: Vite build succeeds without unresolved import errors

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.js
git commit -m "feat(frontend): add element plus bootstrap"
```

## Task 2: Add Element Plus theme compatibility and global feedback bridge

**Files:**
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/lib/flash.js`
- Test: `frontend/src/lib/__tests__/flash.test.js`

- [ ] **Step 1: Add Element Plus token overrides near global theme rules in `frontend/src/style.css`**

```css
:root {
  --el-color-primary: #2563eb;
  --el-border-radius-base: 12px;
  --el-border-radius-small: 10px;
  --el-font-size-base: 14px;
  --el-box-shadow-light: 0 12px 30px -24px rgba(15, 23, 42, 0.35);
}

.page-shell .el-card,
.ui-card.el-card {
  border-radius: 20px;
}

.page-shell .el-tabs__header {
  margin-bottom: 20px;
}
```

- [ ] **Step 2: Update `frontend/src/lib/flash.js` to use Element Plus message when available**

```js
import { ElMessage } from 'element-plus'

const push = (type, text) => {
  ElMessage({
    type,
    message: text,
    duration: 2600,
    showClose: true,
  })
}

export function useFlash() {
  return {
    success: (text) => push('success', text),
    error: (text) => push('error', text),
    warning: (text) => push('warning', text),
    info: (text) => push('info', text),
  }
}
```

- [ ] **Step 3: Update `frontend/src/lib/__tests__/flash.test.js` to assert the message bridge contract**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { useFlash } from '../flash.js'

test('useFlash exposes standard message helpers', () => {
  const flash = useFlash()

  assert.equal(typeof flash.success, 'function')
  assert.equal(typeof flash.error, 'function')
  assert.equal(typeof flash.warning, 'function')
  assert.equal(typeof flash.info, 'function')
})
```

- [ ] **Step 4: Run focused tests and build**

Run: `node --test src/lib/__tests__/flash.test.js && npm run build`
Expected: test passes and build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/style.css frontend/src/lib/flash.js frontend/src/lib/__tests__/flash.test.js
git commit -m "feat(frontend): align global feedback with element plus"
```

## Task 3: Migrate admin model management to Element Plus controls

**Files:**
- Modify: `frontend/src/components/ModelConfig.vue`
- Test: `frontend/src/views/admin/AdminModelsView.vue` through build/manual render

- [ ] **Step 1: Replace ad-hoc form controls in `frontend/src/components/ModelConfig.vue` with Element Plus imports and shell**

```vue
<script setup>
import { ElButton, ElCard, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElSwitch, ElTable, ElTableColumn, ElTag } from 'element-plus'
</script>
```

- [ ] **Step 2: Wrap the page body in an `ElCard` and move filter/edit inputs into `ElForm` / `ElFormItem`**

```vue
<el-card class="ui-card ui-card--admin">
  <template #header>
    <div class="section-heading">
      <h3 class="section-heading__title">模型配置管理</h3>
      <div class="section-heading__desc">统一管理聊天、嵌入与评测模型配置。</div>
    </div>
  </template>

  <el-form :inline="true" class="admin-form-row">
    <el-form-item label="模型名称">
      <el-input v-model="filters.name" placeholder="输入模型名" clearable />
    </el-form-item>
  </el-form>
</el-card>
```

- [ ] **Step 3: Replace raw tabular layout with `ElTable` / `ElTableColumn`**

```vue
<el-table :data="models" style="width: 100%">
  <el-table-column prop="name" label="模型名" min-width="180" />
  <el-table-column prop="provider" label="Provider" width="140" />
  <el-table-column label="状态" width="120">
    <template #default="scope">
      <el-tag :type="scope.row.enabled ? 'success' : 'info'">
        {{ scope.row.enabled ? '启用' : '停用' }}
      </el-tag>
    </template>
  </el-table-column>
</el-table>
```

- [ ] **Step 4: Run build to verify admin models page compiles**

Run: `npm run build`
Expected: build succeeds and generated admin models chunk is emitted

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ModelConfig.vue
git commit -m "feat(frontend): migrate model config to element plus"
```

## Task 4: Migrate admin user management to Element Plus controls

**Files:**
- Modify: `frontend/src/components/AdminUsers.vue`
- Test: `frontend/src/views/admin/AdminUsersView.vue` through build/manual render

- [ ] **Step 1: Add Element Plus imports for user management controls**

```vue
<script setup>
import { ElButton, ElCard, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElTable, ElTableColumn, ElTag } from 'element-plus'
</script>
```

- [ ] **Step 2: Convert top filters/actions to `ElForm` + `ElInput` + `ElSelect`**

```vue
<el-form :inline="true" class="admin-form-row">
  <el-form-item label="用户">
    <el-input v-model="filters.keyword" placeholder="按用户名/邮箱搜索" clearable />
  </el-form-item>
  <el-form-item label="角色">
    <el-select v-model="filters.role" placeholder="全部角色" clearable>
      <el-option label="管理员" value="admin" />
      <el-option label="普通用户" value="user" />
    </el-select>
  </el-form-item>
  <el-form-item>
    <el-button type="primary" @click="fetchUsers">查询</el-button>
  </el-form-item>
</el-form>
```

- [ ] **Step 3: Replace raw list/table markup with `ElTable` and typed status tags**

```vue
<el-table :data="users" style="width: 100%">
  <el-table-column prop="username" label="用户名" min-width="160" />
  <el-table-column prop="email" label="邮箱" min-width="220" />
  <el-table-column label="角色" width="120">
    <template #default="scope">
      <el-tag>{{ scope.row.role }}</el-tag>
    </template>
  </el-table-column>
</el-table>
```

- [ ] **Step 4: Use `ElDialog` for create/edit user modal if the component currently uses custom overlay markup**

```vue
<el-dialog v-model="dialogVisible" title="编辑用户" width="560px">
  <el-form label-width="88px">
    <el-form-item label="用户名">
      <el-input v-model="form.username" />
    </el-form-item>
  </el-form>
</el-dialog>
```

- [ ] **Step 5: Run build and commit**

Run: `npm run build`
Expected: build succeeds and admin users page compiles

```bash
git add frontend/src/components/AdminUsers.vue
git commit -m "feat(frontend): migrate admin users to element plus"
```

## Task 5: Upgrade risk workspace interaction controls with Element Plus

**Files:**
- Modify: `frontend/src/components/RiskSummary.vue`
- Test: `frontend/src/views/workspace/WorkspaceRiskView.vue` through build/manual render

- [ ] **Step 1: Replace custom tabs in `frontend/src/components/RiskSummary.vue` with `ElTabs` / `ElTabPane`**

```vue
<el-tabs v-model="activeTab" class="risk-tabs">
  <el-tab-pane label="风险事件审核" name="events" />
  <el-tab-pane label="风险报告生成" name="reports" />
</el-tabs>
```

- [ ] **Step 2: Replace filter toolbar with `ElForm`, `ElInput`, `ElSelect`, and `ElButton`**

```vue
<el-form :inline="true" class="toolbar">
  <el-form-item>
    <el-input v-model="filters.company_name" placeholder="公司名称" clearable />
  </el-form-item>
  <el-form-item>
    <el-select v-model="filters.risk_level" placeholder="全部等级" clearable>
      <el-option label="高风险" value="high" />
      <el-option label="中风险" value="medium" />
      <el-option label="低风险" value="low" />
    </el-select>
  </el-form-item>
  <el-form-item>
    <el-button type="primary" @click="applyFilters">查询</el-button>
    <el-button @click="resetFilters">重置</el-button>
  </el-form-item>
</el-form>
```

- [ ] **Step 3: Replace the events table with `ElTable` while preserving custom summary/evidence cells**

```vue
<el-table :data="events" style="width: 100%">
  <el-table-column prop="company_name" label="公司名" min-width="160" />
  <el-table-column prop="risk_type" label="风险类型" width="140" />
  <el-table-column label="风险等级" width="120">
    <template #default="scope">
      <el-tag :type="scope.row.risk_level === 'high' ? 'danger' : scope.row.risk_level === 'medium' ? 'warning' : 'success'">
        {{ (scope.row.risk_level || 'unknown').toUpperCase() }}
      </el-tag>
    </template>
  </el-table-column>
</el-table>
```

- [ ] **Step 4: Convert report form controls to `ElRadioGroup`, `ElDatePicker`, and `ElInput`**

```vue
<el-radio-group v-model="reportType">
  <el-radio value="company">按公司维度</el-radio>
  <el-radio value="time-range">按时间区间</el-radio>
</el-radio-group>

<el-date-picker v-model="reportForm.period_start" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" />
```

- [ ] **Step 5: Run build and commit**

Run: `npm run build`
Expected: build succeeds and workspace risk page compiles

```bash
git add frontend/src/components/RiskSummary.vue
git commit -m "feat(frontend): upgrade risk controls with element plus"
```

## Task 6: Align admin overview internals with Element Plus card conventions

**Files:**
- Modify: `frontend/src/components/OpsDashboard.vue`
- Test: `frontend/src/views/admin/AdminOverviewView.vue`

- [ ] **Step 1: Replace raw metric tiles with `ElCard` usage where it improves consistency**

```vue
<el-card class="metric-card ui-card ui-card--admin" shadow="hover">
  <div class="label">知识库数</div>
  <div class="value">{{ dashboardStats.knowledgebase_count ?? '--' }}</div>
</el-card>
```

- [ ] **Step 2: Keep the dark log console custom, but wrap surrounding controls in Element Plus buttons where helpful**

```vue
<el-button type="primary" plain @click="fetchData" :loading="isLoading">
  刷新数据
</el-button>
```

- [ ] **Step 3: Run build to verify admin overview still compiles**

Run: `npm run build`
Expected: build succeeds and no template/runtime compile errors occur

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/OpsDashboard.vue
git commit -m "style(frontend): align admin overview with element plus cards"
```

## Task 7: Final regression build and integration pass

**Files:**
- Modify: any files from earlier tasks if integration fixes are needed
- Test: full frontend build

- [ ] **Step 1: Run the full frontend test/build pass**

Run: `node --test src/api/__tests__/auth.test.js src/api/__tests__/auth-expiry.test.js src/config/__tests__/navigation.test.js src/config/__tests__/navigation-actions.test.js src/lib/__tests__/auth-form.test.js src/lib/__tests__/flash.test.js src/lib/__tests__/session-state.test.js src/router/__tests__/routes.test.js && npm run build`
Expected: tests pass and Vite build succeeds

- [ ] **Step 2: Review the changed UI boundaries manually**

Check these routes in dev server:
- `/admin`
- `/admin/models`
- `/admin/users`
- `/workspace/risk`

Expected:
- Admin feels more standard B-end
- Risk page interactions are upgraded without losing workspace shell
- QA page remains visually lightweight

- [ ] **Step 3: Commit final integration fixes**

```bash
git add frontend
git commit -m "feat(frontend): complete first-stage element plus adoption"
```

## Self-Review

- Spec coverage: plan covers bootstrap, theme bridge, admin migration priority, risk page migration, and preservation of QA custom experience.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: Element Plus component names, file paths, and command flow are consistent across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-06-frontend-element-plus-adoption.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**