# Workspace Sidebar and QA Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the business workspace sidebar so labels are always visible on desktop, remove redundant QA-page chrome, and make the chat canvas fill the available workspace while keeping history, memory, and new-chat actions intact.

**Architecture:** Keep the existing Vue workspace shell and `FinancialQA` component as the primary composition points, but extract the new UI decisions into tiny pure helpers so the simplified chrome can be covered by `node --test`. Most of the visible change lives in `frontend/src/style.css` and `frontend/src/components/FinancialQA.vue`; no backend API contract changes are needed.

**Tech Stack:** Vue 3, Vue Router, Vite, Node built-in test runner (`node --test`)

---

## File map

- **Create:** `frontend/src/lib/workspace-shell.js` — pure helpers that define whether a shell area uses rail or expanded sidebar presentation.
- **Create:** `frontend/src/lib/__tests__/workspace-shell.test.js` — desktop-sidebar behavior tests for the new shell helper.
- **Modify:** `frontend/src/components/ui/AppSidebar.vue` — replace the hard-coded `isWorkspaceCompact` logic with helper-driven presentation.
- **Modify:** `frontend/src/style.css:23-25,296-304,322-535,895-943` — widen the workspace sidebar, stop hiding brand/group/item labels on desktop, and keep current mobile behavior.
- **Modify:** `frontend/src/layouts/WorkspaceLayout.vue:13-19` — keep the compact topbar but shorten the subtitle to match the lighter QA chrome.
- **Modify:** `frontend/src/lib/workspace-qa.js` — add pure helpers that describe the simplified QA toolbar/empty-state presentation.
- **Create:** `frontend/src/lib/__tests__/workspace-qa.test.js` — tests for the simplified QA chrome state.
- **Modify:** `frontend/src/components/FinancialQA.vue:26-32,50-109,394-529,534-964` — remove redundant header content, move dataset selection into a lower-priority tools row, swap the always-on system welcome bubble for an empty-state card, and make the message canvas fill the shell.
- **Modify:** `frontend/src/views/workspace/WorkspaceQaView.vue:12-14` — keep the page wrapper minimal and full-height.

## Task 1: Add a testable workspace shell presentation helper

**Files:**
- Create: `frontend/src/lib/workspace-shell.js`
- Test: `frontend/src/lib/__tests__/workspace-shell.test.js`

- [ ] **Step 1: Write the failing test**

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import { getSidebarPresentation } from '../workspace-shell.js';

test('workspace sidebar uses expanded labels on desktop', () => {
  assert.deepEqual(getSidebarPresentation('workspace'), {
    mode: 'expanded',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  });
});

test('admin sidebar keeps the default expanded presentation', () => {
  assert.deepEqual(getSidebarPresentation('admin'), {
    mode: 'expanded',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/lib/__tests__/workspace-shell.test.js`
Expected: FAIL with `Cannot find module '../workspace-shell.js'` or `does not provide an export named 'getSidebarPresentation'`

- [ ] **Step 3: Write minimal implementation**

```js
export function getSidebarPresentation(area) {
  if (area === 'workspace') {
    return {
      mode: 'expanded',
      showBrandCopy: true,
      showGroupLabels: true,
      showItemLabels: true,
    };
  }

  return {
    mode: 'expanded',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test src/lib/__tests__/workspace-shell.test.js`
Expected: PASS with `2 tests` and `0 failures`

- [ ] **Step 5: Commit**

```bash
git -C /root/finmodpro add frontend/src/lib/workspace-shell.js frontend/src/lib/__tests__/workspace-shell.test.js
git -C /root/finmodpro commit -m "test(frontend): cover workspace shell presentation" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 2: Hook the expanded sidebar presentation into the workspace shell

**Files:**
- Modify: `frontend/src/components/ui/AppSidebar.vue:1-105`
- Modify: `frontend/src/style.css:23-25,296-304,322-535,895-943`
- Modify: `frontend/src/layouts/WorkspaceLayout.vue:13-19`
- Test: `frontend/src/lib/__tests__/workspace-shell.test.js`

- [ ] **Step 1: Extend the existing sidebar helper test with the desktop width expectation**

```js
test('workspace presentation is no longer a rail', () => {
  const presentation = getSidebarPresentation('workspace');

  assert.equal(presentation.mode, 'expanded');
  assert.equal(presentation.showItemLabels, true);
});
```

- [ ] **Step 2: Run test to verify the new assertion passes before the template work**

Run: `cd frontend && node --test src/lib/__tests__/workspace-shell.test.js`
Expected: PASS; this confirms the pure contract before wiring it into Vue and CSS

- [ ] **Step 3: Update the sidebar component and shell styles**

```vue
<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import AppIcon from './AppIcon.vue';
import finmodproMark from '../../assets/finmodpro-mark.svg';
import { getNavItems } from '../../config/navigation.js';
import { authStorage } from '../../lib/auth-storage.js';
import { getSidebarPresentation } from '../../lib/workspace-shell.js';

const props = defineProps({
  area: {
    type: String,
    required: true,
  },
});

const profile = computed(() => authStorage.getProfile());
const items = computed(() => getNavItems(props.area, profile.value));
const sidebarPresentation = computed(() => getSidebarPresentation(props.area));
</script>
```

```css
:root {
  --workspace-sidebar-width: 216px;
}

.app-shell__content--workspace {
  padding-inline: 20px;
}

.app-shell--workspace .app-sidebar {
  align-items: stretch;
  gap: 12px;
}

.app-shell--workspace .app-sidebar__brand-copy,
.app-shell--workspace .app-sidebar__group-label,
.app-shell--workspace .app-sidebar__item-label {
  display: initial;
}

.app-shell--workspace .app-sidebar__group,
.app-shell--workspace .app-sidebar__group-items,
.app-shell--workspace .app-sidebar__item {
  align-items: stretch;
  justify-content: flex-start;
}
```

```vue
<AppTopbar
  eyebrow="用户端"
  title="业务工作区"
  subtitle="连续问答与分析工作区。"
  area="workspace"
  compact
/>
```

- [ ] **Step 4: Run build to verify the shell still compiles**

Run: `cd frontend && npm run build`
Expected: PASS with Vite production build output and no Vue compile errors

- [ ] **Step 5: Commit**

```bash
git -C /root/finmodpro add frontend/src/components/ui/AppSidebar.vue frontend/src/style.css frontend/src/layouts/WorkspaceLayout.vue
git -C /root/finmodpro commit -m "feat(frontend): expand workspace sidebar labels" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 3: Add pure QA chrome helpers and tests

**Files:**
- Modify: `frontend/src/lib/workspace-qa.js`
- Create: `frontend/src/lib/__tests__/workspace-qa.test.js`

- [ ] **Step 1: Write the failing test**

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getQaChromeState,
  shouldShowQaEmptyState,
} from '../workspace-qa.js';

test('qa chrome only keeps the three primary actions', () => {
  assert.deepEqual(getQaChromeState(), {
    showEyebrow: false,
    showSessionState: false,
    showSessionMeta: false,
    showSessionSummary: false,
    actions: ['history', 'memory', 'new'],
  });
});

test('empty state disappears after the first real user or assistant message', () => {
  assert.equal(shouldShowQaEmptyState([{ role: 'system', content: '欢迎' }]), true);
  assert.equal(
    shouldShowQaEmptyState([
      { role: 'system', content: '欢迎' },
      { role: 'user', content: '帮我分析财报' },
    ]),
    false,
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/lib/__tests__/workspace-qa.test.js`
Expected: FAIL with `getQaChromeState is not a function` or `shouldShowQaEmptyState is not exported`

- [ ] **Step 3: Write minimal implementation**

```js
export function getQaChromeState() {
  return {
    showEyebrow: false,
    showSessionState: false,
    showSessionMeta: false,
    showSessionSummary: false,
    actions: ['history', 'memory', 'new'],
  };
}

export function shouldShowQaEmptyState(messages) {
  if (!Array.isArray(messages)) {
    return true;
  }

  return !messages.some((message) => message?.role === 'user' || message?.role === 'assistant');
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test src/lib/__tests__/workspace-qa.test.js`
Expected: PASS with `2 tests` and `0 failures`

- [ ] **Step 5: Commit**

```bash
git -C /root/finmodpro add frontend/src/lib/workspace-qa.js frontend/src/lib/__tests__/workspace-qa.test.js
git -C /root/finmodpro commit -m "test(frontend): add qa chrome state coverage" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 4: Simplify the QA page chrome and make the chat canvas fill the workspace

**Files:**
- Modify: `frontend/src/components/FinancialQA.vue:26-32,50-109,394-529,534-964`
- Modify: `frontend/src/views/workspace/WorkspaceQaView.vue:12-14`
- Modify: `frontend/src/style.css:296-304`
- Test: `frontend/src/lib/__tests__/workspace-qa.test.js`

- [ ] **Step 1: Add one more failing assertion for the compact QA actions contract**

```js
test('qa chrome action order matches the simplified toolbar', () => {
  assert.deepEqual(getQaChromeState().actions, ['history', 'memory', 'new']);
});
```

- [ ] **Step 2: Run the targeted tests before touching the component**

Run: `cd frontend && node --test src/lib/__tests__/workspace-qa.test.js`
Expected: PASS; this locks the intended toolbar contract before the Vue changes

- [ ] **Step 3: Implement the simplified toolbar, lowered dataset control, and full-height canvas**

```vue
<script setup>
import {
  getActiveSessionLabel,
  getDefaultSessionFilters,
  getQaChromeState,
  getSessionTitleSourceLabel,
  getSessionTitleStatusLabel,
  normalizeDatasetId,
  normalizeHistoryItems,
  shouldShowQaEmptyState,
} from '../lib/workspace-qa.js';

const qaChromeState = getQaChromeState();
const showEmptyState = computed(() => shouldShowQaEmptyState(messages.value));
</script>
```

```vue
<div class="qa-shell__toolbar">
  <div class="qa-shell__actions qa-shell__actions--primary">
    <button class="ghost-btn" type="button" @click="historyDrawerOpen = true">历史会话</button>
    <button class="ghost-btn" type="button" @click="memoryDrawerOpen = true">记忆</button>
    <button class="ghost-btn ghost-btn--primary" type="button" @click="startNewConversation">新对话</button>
  </div>

  <label class="qa-shell__dataset-picker qa-shell__dataset-picker--subtle">
    <span>数据集</span>
    <select v-model="selectedDatasetId" :disabled="isLoadingDatasets">
      <option value="">全部数据集</option>
      <option v-for="dataset in datasets" :key="dataset.id" :value="String(dataset.id)">
        {{ dataset.name }}
      </option>
    </select>
  </label>
</div>

<div class="chat-window">
  <div v-if="showEmptyState" class="qa-empty-state">
    <h2>开始新一轮分析</h2>
    <p>从历史会话继续、查看记忆，或直接输入新的金融问题。</p>
  </div>

  <div ref="messagesContainer" class="messages" :class="{ 'messages--empty': showEmptyState }">
    <!-- existing user / assistant message loop -->
  </div>

  <div class="input-area">
    <!-- existing textarea and send button -->
  </div>
</div>
```

```css
.qa-page,
.qa-shell,
.chat-window,
.messages {
  min-height: 0;
}

.qa-shell {
  flex: 1;
  min-height: calc(100svh - 150px);
}

.qa-shell__toolbar {
  align-items: flex-start;
  padding: 14px 20px;
}

.qa-shell__dataset-picker--subtle span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.qa-empty-state {
  margin: 20px 20px 0;
  padding: 18px 20px;
  border: 1px dashed var(--line-strong);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
}
```

- [ ] **Step 4: Run the full frontend checks**

Run: `cd frontend && node --test src/lib/__tests__/workspace-shell.test.js src/lib/__tests__/workspace-qa.test.js && npm run build`
Expected: PASS for both `node --test` files, followed by a successful Vite production build

- [ ] **Step 5: Commit**

```bash
git -C /root/finmodpro add frontend/src/components/FinancialQA.vue frontend/src/views/workspace/WorkspaceQaView.vue frontend/src/style.css
git -C /root/finmodpro commit -m "feat(frontend): simplify workspace qa chrome" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Self-review checklist

- Spec coverage: Task 2 covers the expanded, always-readable workspace sidebar; Task 4 covers the simplified QA toolbar, lowered dataset selector, empty-state treatment, and full-height canvas; Tasks 1 and 3 provide the pure helper coverage needed to keep the UI decisions testable.
- Placeholder scan: No `TBD`, `TODO`, or “test this later” placeholders remain; every code-changing task includes concrete snippets and exact commands.
- Type consistency: The plan uses `getSidebarPresentation`, `getQaChromeState`, and `shouldShowQaEmptyState` consistently across helper, test, and component steps.
