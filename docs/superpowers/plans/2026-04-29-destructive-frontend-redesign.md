# Destructive Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild every authenticated FinModPro frontend surface into a split workspace dossier and admin war-room system without changing backend contracts, auth rules, or login.

**Architecture:** Keep the current route tree and data flows, but replace authenticated shells, page composition, component boundaries, and visual tokens. Implement the redesign in three execution blocks: shared foundations, workspace redesign, and admin redesign. Drive the new UI with small page-model helpers and shell contracts that are testable with the repository's existing `node --test` setup.

**Tech Stack:** Vue 3, Vue Router, Element Plus, Vite, Node test runner, CSS custom properties

---

## File structure map

### Shared foundations

- Create: `frontend/src/lib/authenticated-shell.js` — shell contracts for workspace/admin chrome, responsive modes, and destructive audit rows
- Create: `frontend/src/lib/__tests__/authenticated-shell.test.js` — test-first contract coverage for split personas and audit dimensions
- Create: `frontend/src/components/ui/DestructiveAuditTable.vue` — reusable final audit table surface
- Modify: `frontend/src/style.css` — replace authenticated tokens and shell rules
- Modify: `frontend/src/layouts/WorkspaceLayout.vue` — new workspace frame
- Modify: `frontend/src/layouts/AdminLayout.vue` — new admin frame
- Modify: `frontend/src/components/ui/AppSidebar.vue` — dossier nav vs war-room nav rendering
- Modify: `frontend/src/components/ui/AppTopbar.vue` — shared identity actions without the old header pattern
- Modify: `frontend/src/lib/workspace-shell.js` — remove legacy always-expanded assumption
- Modify: `frontend/src/lib/__tests__/workspace-shell.test.js` — reflect new shell modes

### Workspace redesign

- Create: `frontend/src/lib/workspace-page-models.js` — page schemas for QA, knowledge, risk, sentiment, history, profile
- Create: `frontend/src/lib/__tests__/workspace-page-models.test.js`
- Create: `frontend/src/components/workspace/qa/ConversationCanvas.vue`
- Create: `frontend/src/components/workspace/qa/AnswerDossier.vue`
- Create: `frontend/src/components/workspace/qa/EvidenceRail.vue`
- Create: `frontend/src/components/workspace/knowledge/KnowledgeArchiveShell.vue`
- Create: `frontend/src/components/workspace/knowledge/KnowledgeAssetLedger.vue`
- Create: `frontend/src/components/workspace/knowledge/KnowledgeDocumentInspector.vue`
- Create: `frontend/src/components/workspace/dossier/DossierPageShell.vue`
- Create: `frontend/src/components/workspace/dossier/DossierEvidenceStack.vue`
- Create: `frontend/src/components/workspace/support/HistoryWorkbench.vue`
- Create: `frontend/src/components/workspace/support/ProfileIdentitySheet.vue`
- Modify: `frontend/src/views/workspace/WorkspaceQaView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceKnowledgeView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceRiskView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceSentimentView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceHistoryView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceProfileView.vue`
- Modify: `frontend/src/components/FinancialQA.vue`
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Modify: `frontend/src/components/RiskSummary.vue`
- Modify: `frontend/src/components/SentimentAnalysis.vue`

### Admin redesign

- Create: `frontend/src/lib/admin-page-models.js` — shell family contracts for overview, llm detail pages, and governance pages
- Create: `frontend/src/lib/__tests__/admin-page-models.test.js`
- Create: `frontend/src/components/admin/ops/OpsStatusBand.vue`
- Create: `frontend/src/components/admin/ops/OpsCommandDeck.vue`
- Create: `frontend/src/components/admin/ops/OpsInspectorDrawer.vue`
- Create: `frontend/src/components/admin/ops/OpsSectionFrame.vue`
- Create: `frontend/src/components/admin/governance/GovernanceReviewDesk.vue`
- Modify: `frontend/src/views/admin/AdminOverviewView.vue`
- Modify: `frontend/src/views/admin/AdminLlmOverviewView.vue`
- Modify: `frontend/src/views/admin/AdminLlmModelsView.vue`
- Modify: `frontend/src/views/admin/AdminLlmObservabilityView.vue`
- Modify: `frontend/src/views/admin/AdminLlmCostsView.vue`
- Modify: `frontend/src/views/admin/AdminLlmFineTunesView.vue`
- Modify: `frontend/src/views/admin/AdminUsersView.vue`
- Modify: `frontend/src/views/admin/AdminEvaluationView.vue`
- Modify: `frontend/src/components/OpsDashboard.vue`
- Modify: `frontend/src/components/LlmGatewayDashboard.vue`
- Modify: `frontend/src/components/LlmGatewayRouting.vue`
- Modify: `frontend/src/components/LlmGatewayObservability.vue`
- Modify: `frontend/src/components/LlmGatewayCosts.vue`
- Modify: `frontend/src/components/AdminUsers.vue`
- Modify: `frontend/src/components/EvaluationResult.vue`
- Modify: `frontend/src/components/ModelConfig.vue`
- Modify: `frontend/src/config/navigation.js`
- Modify: `frontend/src/config/__tests__/navigation.test.js`
- Modify: `frontend/src/router/__tests__/routes.test.js`

## Execution blocks

1. **Shared foundations** — new shell contract, token reset, shared destructive audit artifact
2. **Workspace redesign** — dossier canvas, archive desk, dossier result pages, support pages
3. **Admin redesign** — war-room shell, LLM operations family, governance review surfaces

## Task 1: Establish the authenticated shell contract

**Files:**
- Create: `frontend/src/lib/authenticated-shell.js`
- Create: `frontend/src/lib/__tests__/authenticated-shell.test.js`
- Modify: `frontend/src/lib/workspace-shell.js`
- Test: `frontend/src/lib/__tests__/authenticated-shell.test.js`
- Test: `frontend/src/lib/__tests__/workspace-shell.test.js`

- [ ] **Step 1: Write the failing shell-contract tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getAuthenticatedShellSpec,
  getDestructiveAuditRows,
} from '../authenticated-shell.js';

test('workspace and admin use intentionally different shell personas', () => {
  const workspace = getAuthenticatedShellSpec('workspace');
  const admin = getAuthenticatedShellSpec('admin');

  assert.equal(workspace.persona, 'dossier');
  assert.equal(admin.persona, 'war-room');
  assert.notDeepEqual(workspace.layout, admin.layout);
});

test('destructive audit covers at least six redesign dimensions', () => {
  const rows = getDestructiveAuditRows();

  assert.ok(rows.length >= 6);
  assert.ok(rows.every((row) => row.before && row.after && row.dimension));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/lib/__tests__/authenticated-shell.test.js src/lib/__tests__/workspace-shell.test.js`

Expected: FAIL with module-not-found or missing-export errors for `authenticated-shell.js`

- [ ] **Step 3: Write the minimal shell contract**

```js
const SHELL_SPECS = Object.freeze({
  workspace: {
    persona: 'dossier',
    layout: {
      desktop: 'split-dossier',
      tablet: 'folding-rail',
      mobile: 'chapter-tabs',
    },
  },
  admin: {
    persona: 'war-room',
    layout: {
      desktop: 'status-band',
      tablet: 'slice-grid',
      mobile: 'triage-stack',
    },
  },
});

const DESTRUCTIVE_AUDIT_ROWS = Object.freeze([
  { dimension: 'Layout system', before: 'Shared shell', after: 'Dossier vs war room' },
  { dimension: 'Color system', before: 'Blue-gray shared palette', after: 'Warm dossier and dark ops split' },
  { dimension: 'Typography', before: 'Uniform product sans', after: 'Editorial vs command hierarchy' },
  { dimension: 'Component shape', before: 'Rounded product cards', after: 'Folders, drawers, monitor slices' },
  { dimension: 'Information order', before: 'Tool-first', after: 'Conclusion and status first' },
  { dimension: 'Responsive strategy', before: 'Collapse and stack', after: 'Chapter tabs and triage modes' },
]);

export function getAuthenticatedShellSpec(area) {
  return SHELL_SPECS[area] ?? SHELL_SPECS.workspace;
}

export function getDestructiveAuditRows() {
  return [...DESTRUCTIVE_AUDIT_ROWS];
}
```

- [ ] **Step 4: Align the legacy sidebar helper with the new contract**

```js
import { getAuthenticatedShellSpec } from './authenticated-shell.js';

export function getSidebarPresentation(area) {
  const spec = getAuthenticatedShellSpec(area);

  if (spec.persona === 'war-room') {
    return { mode: 'dense', showBrandCopy: true, showGroupLabels: true, showItemLabels: true };
  }

  return { mode: 'editorial', showBrandCopy: true, showGroupLabels: true, showItemLabels: true };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/lib/__tests__/authenticated-shell.test.js src/lib/__tests__/workspace-shell.test.js`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/authenticated-shell.js frontend/src/lib/workspace-shell.js frontend/src/lib/__tests__/authenticated-shell.test.js frontend/src/lib/__tests__/workspace-shell.test.js
git commit -m "feat(frontend): define destructive shell contract"
```

## Task 2: Replace authenticated tokens and shared shells

**Files:**
- Create: `frontend/src/components/ui/DestructiveAuditTable.vue`
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/layouts/WorkspaceLayout.vue`
- Modify: `frontend/src/layouts/AdminLayout.vue`
- Modify: `frontend/src/components/ui/AppSidebar.vue`
- Modify: `frontend/src/components/ui/AppTopbar.vue`
- Test: `frontend/src/config/__tests__/navigation.test.js`

- [ ] **Step 1: Add a failing navigation-shell test for split personas**

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import { navigationMap } from '../navigation.js';

test('workspace and admin navigation keep separate grouping vocabularies', () => {
  const workspaceLabels = navigationMap.workspace.map((item) => item.label);
  const adminLabels = navigationMap.admin.map((item) => item.label);

  assert.ok(workspaceLabels.includes('智能问答'));
  assert.ok(adminLabels.includes('Gateway'));
  assert.notDeepEqual(workspaceLabels, adminLabels);
});
```

- [ ] **Step 2: Run the targeted test**

Run: `cd frontend && npm test -- src/config/__tests__/navigation.test.js`

Expected: FAIL only if the test asserts a grouping or vocabulary that current shell metadata does not yet expose cleanly

- [ ] **Step 3: Rewrite the shared CSS token layer**

```css
:root {
  --workspace-bg: #f3ecdf;
  --workspace-surface: #fbf6ed;
  --workspace-line: rgba(89, 66, 34, 0.16);
  --workspace-ink: #2f2418;
  --workspace-accent: #9a6a2c;

  --admin-bg: #0f1722;
  --admin-surface: #182231;
  --admin-line: rgba(148, 171, 204, 0.16);
  --admin-ink: #edf3ff;
  --admin-accent: #d5a441;
  --admin-alert: #8dd0d0;
}

.app-shell--workspace {
  background:
    radial-gradient(circle at top left, rgba(154, 106, 44, 0.12), transparent 32%),
    var(--workspace-bg);
}

.app-shell--admin {
  background:
    linear-gradient(180deg, rgba(16, 25, 38, 0.96), rgba(11, 18, 29, 1)),
    var(--admin-bg);
}
```

- [ ] **Step 4: Rebuild the layouts around the new personas**

```vue
<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <main class="workspace-frame">
      <FlashStack />
      <section class="workspace-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
```

```vue
<template>
  <div class="app-shell app-shell--admin">
    <AppSidebar area="admin" />
    <main class="admin-frame">
      <AppTopbar area="admin" eyebrow="War room" title="Model operations" />
      <FlashStack />
      <section class="admin-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
```

- [ ] **Step 5: Add the audit table surface**

```vue
<script setup>
import { getDestructiveAuditRows } from '../../lib/authenticated-shell.js';

const rows = getDestructiveAuditRows();
</script>

<template>
  <table class="destructive-audit-table">
    <thead>
      <tr><th>Dimension</th><th>Before</th><th>After</th></tr>
    </thead>
    <tbody>
      <tr v-for="row in rows" :key="row.dimension">
        <td>{{ row.dimension }}</td>
        <td>{{ row.before }}</td>
        <td>{{ row.after }}</td>
      </tr>
    </tbody>
  </table>
</template>
```

- [ ] **Step 6: Run tests and build**

Run: `cd frontend && npm test -- src/config/__tests__/navigation.test.js && npm run build`

Expected: PASS, then Vite build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/style.css frontend/src/layouts/WorkspaceLayout.vue frontend/src/layouts/AdminLayout.vue frontend/src/components/ui/AppSidebar.vue frontend/src/components/ui/AppTopbar.vue frontend/src/components/ui/DestructiveAuditTable.vue frontend/src/config/__tests__/navigation.test.js
git commit -m "feat(frontend): replace authenticated shell chrome"
```

## Task 3: Define workspace page models before rebuilding pages

**Files:**
- Create: `frontend/src/lib/workspace-page-models.js`
- Create: `frontend/src/lib/__tests__/workspace-page-models.test.js`
- Test: `frontend/src/lib/__tests__/workspace-page-models.test.js`

- [ ] **Step 1: Write failing page-model tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import { getWorkspacePageModel } from '../workspace-page-models.js';

test('qa page uses conversation, dossier, and evidence regions in order', () => {
  const model = getWorkspacePageModel('qa');

  assert.deepEqual(model.regions.map((region) => region.id), [
    'conversation',
    'dossier',
    'evidence',
  ]);
});

test('mobile qa mode switches to chapter tabs instead of stacked cards', () => {
  const model = getWorkspacePageModel('qa');

  assert.equal(model.mobileMode, 'chapter-tabs');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js`

Expected: FAIL with missing module or missing export errors

- [ ] **Step 3: Implement the workspace page schema helper**

```js
const MODELS = Object.freeze({
  qa: {
    mobileMode: 'chapter-tabs',
    regions: [
      { id: 'conversation', label: '会话' },
      { id: 'dossier', label: '结论' },
      { id: 'evidence', label: '证据' },
    ],
  },
  knowledge: {
    mobileMode: 'stacked-drawers',
    regions: [
      { id: 'filters', label: '筛选' },
      { id: 'ledger', label: '文档' },
      { id: 'inspector', label: '详情' },
    ],
  },
  risk: {
    mobileMode: 'chapter-tabs',
    regions: [
      { id: 'summary', label: '结论' },
      { id: 'evidence', label: '证据' },
      { id: 'actions', label: '导出' },
    ],
  },
  sentiment: {
    mobileMode: 'chapter-tabs',
    regions: [
      { id: 'summary', label: '判断' },
      { id: 'evidence', label: '样本' },
      { id: 'actions', label: '操作' },
    ],
  },
  history: {
    mobileMode: 'single-column',
    regions: [
      { id: 'filters', label: '检索' },
      { id: 'records', label: '记录' },
    ],
  },
  profile: {
    mobileMode: 'single-column',
    regions: [
      { id: 'identity', label: '身份' },
      { id: 'access', label: '权限' },
    ],
  },
});

export function getWorkspacePageModel(page) {
  return MODELS[page];
}
```

- [ ] **Step 4: Run the targeted tests**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/workspace-page-models.js frontend/src/lib/__tests__/workspace-page-models.test.js
git commit -m "feat(frontend): define workspace page models"
```

## Task 4: Rebuild the QA page as a dossier canvas

**Files:**
- Create: `frontend/src/components/workspace/qa/ConversationCanvas.vue`
- Create: `frontend/src/components/workspace/qa/AnswerDossier.vue`
- Create: `frontend/src/components/workspace/qa/EvidenceRail.vue`
- Modify: `frontend/src/views/workspace/WorkspaceQaView.vue`
- Modify: `frontend/src/components/FinancialQA.vue`
- Test: `frontend/src/lib/__tests__/workspace-page-models.test.js`

- [ ] **Step 1: Extend the failing test with QA section labels**

```js
test('qa page labels the mobile chapters in dossier order', () => {
  const model = getWorkspacePageModel('qa');

  assert.deepEqual(model.regions.map((region) => region.label), ['会话', '结论', '证据']);
});
```

- [ ] **Step 2: Run the QA model test**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js`

Expected: PASS if labels already exist, or FAIL if the schema is incomplete and needs the final QA wording

- [ ] **Step 3: Introduce the three QA subcomponents**

```vue
<!-- frontend/src/components/workspace/qa/ConversationCanvas.vue -->
<script setup>
defineProps({ messages: Array, query: String, isAsking: Boolean });
</script>

<template>
  <section class="conversation-canvas">
    <slot name="toolbar" />
    <slot />
  </section>
</template>
```

```vue
<!-- frontend/src/components/workspace/qa/AnswerDossier.vue -->
<script setup>
defineProps({ messages: Array, isEmpty: Boolean });
</script>

<template>
  <section class="answer-dossier">
    <header class="answer-dossier__header">结论档案</header>
    <slot />
  </section>
</template>
```

```vue
<!-- frontend/src/components/workspace/qa/EvidenceRail.vue -->
<script setup>
defineProps({ messages: Array, sessionLoadFailureNotice: String });
</script>

<template>
  <aside class="evidence-rail">
    <header class="evidence-rail__header">证据索引</header>
    <slot />
  </aside>
</template>
```

- [ ] **Step 4: Recompose `FinancialQA.vue` around the new regions**

```vue
<template>
  <div class="qa-dossier-layout">
    <ConversationCanvas :messages="visibleMessages" :query="query" :is-asking="isAsking">
      <template #toolbar>
        <button v-for="action in qaChromeState.actions" :key="action">{{ qaActionLabels[action] }}</button>
      </template>
      <article
        v-for="(message, index) in visibleMessages"
        :key="`${message.role}-${index}`"
        :class="['qa-message', `qa-message--${message.role}`]"
      >
        <header>{{ getAvatarLabel(message.role) }}</header>
        <p>{{ message.content }}</p>
      </article>
    </ConversationCanvas>

    <AnswerDossier :messages="visibleMessages" :is-empty="showEmptyState">
      <section v-if="showEmptyState" class="qa-empty-dossier">新对话将先生成结论档案。</section>
      <article
        v-else
        v-for="(message, index) in visibleMessages.filter((item) => item.role === 'assistant')"
        :key="`assistant-${index}`"
        class="qa-dossier-entry"
      >
        <h3>结论 {{ index + 1 }}</h3>
        <p>{{ message.content }}</p>
      </article>
    </AnswerDossier>

    <EvidenceRail :messages="visibleMessages" :session-load-failure-notice="sessionLoadFailureNotice">
      <p v-if="sessionLoadFailureNotice">{{ sessionLoadFailureNotice }}</p>
      <ul class="qa-evidence-list">
        <li v-for="item in historyItems.slice(0, 5)" :key="item.id">
          {{ item.title }} · {{ item.messageCount }} 条消息
        </li>
      </ul>
    </EvidenceRail>
  </div>
</template>
```

- [ ] **Step 5: Replace the old page hero wrapper**

```vue
<template>
  <section class="workspace-dossier-page workspace-dossier-page--qa">
    <FinancialQA :session-id="sessionId" />
  </section>
</template>
```

- [ ] **Step 6: Run the page-model test and build**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js && npm run build`

Expected: PASS, then build succeeds with the split QA components wired in

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/workspace/WorkspaceQaView.vue frontend/src/components/FinancialQA.vue frontend/src/components/workspace/qa
git commit -m "feat(frontend): rebuild workspace qa as dossier canvas"
```

## Task 5: Rebuild knowledge, risk, and sentiment into archive and dossier families

**Files:**
- Create: `frontend/src/components/workspace/knowledge/KnowledgeArchiveShell.vue`
- Create: `frontend/src/components/workspace/knowledge/KnowledgeAssetLedger.vue`
- Create: `frontend/src/components/workspace/knowledge/KnowledgeDocumentInspector.vue`
- Create: `frontend/src/components/workspace/dossier/DossierPageShell.vue`
- Create: `frontend/src/components/workspace/dossier/DossierEvidenceStack.vue`
- Modify: `frontend/src/views/workspace/WorkspaceKnowledgeView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceRiskView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceSentimentView.vue`
- Modify: `frontend/src/components/KnowledgeBase.vue`
- Modify: `frontend/src/components/RiskSummary.vue`
- Modify: `frontend/src/components/SentimentAnalysis.vue`
- Test: `frontend/src/lib/__tests__/workspace-page-models.test.js`

- [ ] **Step 1: Add failing knowledge and risk ordering tests**

```js
test('knowledge page keeps filters before ledger before inspector', () => {
  const model = getWorkspacePageModel('knowledge');
  assert.deepEqual(model.regions.map((region) => region.id), ['filters', 'ledger', 'inspector']);
});

test('risk page leads with summary before evidence and actions', () => {
  const model = getWorkspacePageModel('risk');
  assert.deepEqual(model.regions.map((region) => region.id), ['summary', 'evidence', 'actions']);
});
```

- [ ] **Step 2: Run the workspace model test**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js`

Expected: FAIL if the new region ordering is not yet encoded

- [ ] **Step 3: Build the knowledge archive shell**

```vue
<template>
  <section class="knowledge-archive-shell">
    <header class="knowledge-archive-shell__filters">
      <slot name="filters" />
    </header>
    <div class="knowledge-archive-shell__grid">
      <section class="knowledge-archive-shell__ledger"><slot name="ledger" /></section>
      <aside class="knowledge-archive-shell__inspector"><slot name="inspector" /></aside>
    </div>
  </section>
</template>
```

- [ ] **Step 4: Recompose `KnowledgeBase.vue` into archive regions**

```vue
<template>
  <KnowledgeArchiveShell>
    <template #filters>
      <KnowledgeBaseToolbar />
    </template>
    <template #ledger>
      <KnowledgeAssetLedger>
        <KnowledgeBaseTable />
      </KnowledgeAssetLedger>
    </template>
    <template #inspector>
      <KnowledgeDocumentInspector>
        <KnowledgeBaseDetailPanel />
      </KnowledgeDocumentInspector>
    </template>
  </KnowledgeArchiveShell>
</template>
```

- [ ] **Step 5: Recompose risk and sentiment as dossier pages**

```vue
<template>
  <DossierPageShell title="风险摘要与报告" eyebrow="Risk dossier">
    <template #summary>
      <section class="risk-dossier-summary">
        <article v-for="item in analyticsHighlights" :key="item.key">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </section>
    </template>
    <template #evidence>
      <DossierEvidenceStack>
        <article v-for="item in events.slice(0, 5)" :key="item.id || item.event_id">
          <h4>{{ item.company_name || '未命名主体' }}</h4>
          <p>{{ item.summary || item.content || '等待事件摘要字段映射' }}</p>
        </article>
      </DossierEvidenceStack>
    </template>
    <template #actions>
      <div class="risk-dossier-actions">
        <button type="button" @click="generateReport">生成报告</button>
        <button type="button" @click="downloadGeneratedReport('markdown')">导出 Markdown</button>
      </div>
    </template>
  </DossierPageShell>
</template>
```

- [ ] **Step 6: Run the workspace model test and build**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js && npm run build`

Expected: PASS, then build succeeds with archive and dossier compositions

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/workspace/WorkspaceKnowledgeView.vue frontend/src/views/workspace/WorkspaceRiskView.vue frontend/src/views/workspace/WorkspaceSentimentView.vue frontend/src/components/KnowledgeBase.vue frontend/src/components/RiskSummary.vue frontend/src/components/SentimentAnalysis.vue frontend/src/components/workspace/knowledge frontend/src/components/workspace/dossier
git commit -m "feat(frontend): rebuild workspace archive and dossier pages"
```

## Task 6: Quiet the support pages without reverting to generic app cards

**Files:**
- Create: `frontend/src/components/workspace/support/HistoryWorkbench.vue`
- Create: `frontend/src/components/workspace/support/ProfileIdentitySheet.vue`
- Modify: `frontend/src/views/workspace/WorkspaceHistoryView.vue`
- Modify: `frontend/src/views/workspace/WorkspaceProfileView.vue`
- Test: `frontend/src/lib/__tests__/workspace-page-models.test.js`

- [ ] **Step 1: Add support-page model tests**

```js
test('history page remains a support surface with filters and records only', () => {
  const model = getWorkspacePageModel('history');
  assert.deepEqual(model.regions.map((region) => region.id), ['filters', 'records']);
});

test('profile page uses identity before access details', () => {
  const model = getWorkspacePageModel('profile');
  assert.deepEqual(model.regions.map((region) => region.id), ['identity', 'access']);
});
```

- [ ] **Step 2: Run the support-page model test**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js`

Expected: FAIL if the helper has not encoded support-page ordering

- [ ] **Step 3: Create quieter support-page shells**

```vue
<template>
  <section class="history-workbench">
    <header class="history-workbench__filters"><slot name="filters" /></header>
    <section class="history-workbench__records"><slot /></section>
  </section>
</template>
```

```vue
<template>
  <section class="profile-identity-sheet">
    <header class="profile-identity-sheet__hero"><slot name="identity" /></header>
    <section class="profile-identity-sheet__access"><slot name="access" /></section>
  </section>
</template>
```

- [ ] **Step 4: Recompose the history and profile views**

```vue
<template>
  <HistoryWorkbench>
    <template #filters>
      <label class="history-workbench__search">
        <span>关键词筛选</span>
        <input v-model="keyword" type="text" @keydown.enter.prevent="applySearch" />
      </label>
    </template>
    <ChatHistory
      :items="historyItems"
      :is-loading="isLoading"
      :active-session-id="activeSessionId"
      :enable-export="true"
      :show-session-metadata="true"
      @refresh="refreshHistory"
      @open-session="openSession"
      @export-session="exportSession"
      @delete-session="deleteSession"
    />
  </HistoryWorkbench>
</template>
```

```vue
<template>
  <ProfileIdentitySheet>
    <template #identity>
      <section class="profile-identity-hero">
        <div class="profile-panel__avatar">{{ initials }}</div>
        <div>
          <span>{{ roleLabel }}</span>
          <h1>{{ displayName }}</h1>
          <p>{{ email }}</p>
        </div>
      </section>
    </template>
    <template #access>
      <section class="profile-access-grid">
        <article><span>角色组</span><strong>{{ groupsLabel }}</strong></article>
        <article><span>权限</span><strong>{{ permissionsLabel }}</strong></article>
      </section>
    </template>
  </ProfileIdentitySheet>
</template>
```

- [ ] **Step 5: Run the workspace model test and build**

Run: `cd frontend && npm test -- src/lib/__tests__/workspace-page-models.test.js && npm run build`

Expected: PASS, then build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/workspace/WorkspaceHistoryView.vue frontend/src/views/workspace/WorkspaceProfileView.vue frontend/src/components/workspace/support
git commit -m "feat(frontend): restage workspace support pages"
```

## Task 7: Define admin page models before rebuilding the war room

**Files:**
- Create: `frontend/src/lib/admin-page-models.js`
- Create: `frontend/src/lib/__tests__/admin-page-models.test.js`
- Test: `frontend/src/lib/__tests__/admin-page-models.test.js`

- [ ] **Step 1: Write failing admin page-model tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';

import { getAdminPageModel } from '../admin-page-models.js';

test('llm overview page uses status band, command deck, and inspector regions', () => {
  const model = getAdminPageModel('llm-overview');

  assert.deepEqual(model.regions.map((region) => region.id), [
    'status-band',
    'command-deck',
    'inspector',
  ]);
});

test('admin mobile mode is triage-stack rather than full dashboard carryover', () => {
  const model = getAdminPageModel('overview');
  assert.equal(model.mobileMode, 'triage-stack');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/lib/__tests__/admin-page-models.test.js`

Expected: FAIL with missing module or export errors

- [ ] **Step 3: Implement the admin page schema helper**

```js
const MODELS = Object.freeze({
  overview: {
    mobileMode: 'triage-stack',
    regions: [
      { id: 'status-band', label: '状态' },
      { id: 'command-deck', label: '中枢' },
      { id: 'inspector', label: '检视' },
    ],
  },
  'llm-overview': {
    mobileMode: 'triage-stack',
    regions: [
      { id: 'status-band', label: '健康' },
      { id: 'command-deck', label: '路由' },
      { id: 'inspector', label: '异常' },
    ],
  },
  governance: {
    mobileMode: 'review-stack',
    regions: [
      { id: 'queue', label: '队列' },
      { id: 'comparison', label: '对比' },
      { id: 'decision', label: '动作' },
    ],
  },
});

export function getAdminPageModel(page) {
  return MODELS[page];
}
```

- [ ] **Step 4: Run the targeted tests**

Run: `cd frontend && npm test -- src/lib/__tests__/admin-page-models.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/admin-page-models.js frontend/src/lib/__tests__/admin-page-models.test.js
git commit -m "feat(frontend): define admin war room page models"
```

## Task 8: Rebuild the admin shell, overview, and LLM operations family

**Files:**
- Create: `frontend/src/components/admin/ops/OpsStatusBand.vue`
- Create: `frontend/src/components/admin/ops/OpsCommandDeck.vue`
- Create: `frontend/src/components/admin/ops/OpsInspectorDrawer.vue`
- Create: `frontend/src/components/admin/ops/OpsSectionFrame.vue`
- Modify: `frontend/src/views/admin/AdminOverviewView.vue`
- Modify: `frontend/src/views/admin/AdminLlmOverviewView.vue`
- Modify: `frontend/src/views/admin/AdminLlmModelsView.vue`
- Modify: `frontend/src/views/admin/AdminLlmObservabilityView.vue`
- Modify: `frontend/src/views/admin/AdminLlmCostsView.vue`
- Modify: `frontend/src/views/admin/AdminLlmFineTunesView.vue`
- Modify: `frontend/src/components/OpsDashboard.vue`
- Modify: `frontend/src/components/LlmGatewayDashboard.vue`
- Modify: `frontend/src/components/LlmGatewayRouting.vue`
- Modify: `frontend/src/components/LlmGatewayObservability.vue`
- Modify: `frontend/src/components/LlmGatewayCosts.vue`
- Modify: `frontend/src/components/ModelConfig.vue`
- Test: `frontend/src/lib/__tests__/admin-page-models.test.js`

- [ ] **Step 1: Add a failing admin model test for the common operations family**

```js
test('governance pages do not reuse the llm operations region order', () => {
  const llm = getAdminPageModel('llm-overview');
  const governance = getAdminPageModel('governance');

  assert.notDeepEqual(llm.regions, governance.regions);
});
```

- [ ] **Step 2: Run the admin page-model test**

Run: `cd frontend && npm test -- src/lib/__tests__/admin-page-models.test.js`

Expected: PASS if the model contract already distinguishes operations vs governance, or FAIL if it still needs the final region split

- [ ] **Step 3: Create the war-room primitives**

```vue
<template>
  <section class="ops-status-band">
    <slot />
  </section>
</template>
```

```vue
<template>
  <section class="ops-command-deck">
    <slot />
  </section>
</template>
```

```vue
<template>
  <aside class="ops-inspector-drawer">
    <slot />
  </aside>
</template>
```

- [ ] **Step 4: Recompose the LLM dashboard family around shared war-room regions**

```vue
<template>
  <OpsSectionFrame>
    <template #status>
      <OpsStatusBand>
        <article v-for="metric in metricCards" :key="metric.key">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </OpsStatusBand>
    </template>
    <template #main>
      <OpsCommandDeck>
        <router-view />
      </OpsCommandDeck>
    </template>
    <template #inspect>
      <OpsInspectorDrawer>
        <article v-for="item in summary.recent_errors.slice(0, 3)" :key="`${item.trace_id}-${item.time}`">
          <strong>{{ item.alias }}</strong>
          <p>{{ item.error_message }}</p>
        </article>
      </OpsInspectorDrawer>
    </template>
  </OpsSectionFrame>
</template>
```

- [ ] **Step 5: Update the admin overview entry page**

```vue
<template>
  <section class="ops-war-room-page">
    <OpsDashboard />
    <DestructiveAuditTable />
  </section>
</template>
```

- [ ] **Step 6: Run tests and build**

Run: `cd frontend && npm test -- src/lib/__tests__/admin-page-models.test.js src/config/__tests__/navigation.test.js src/router/__tests__/routes.test.js && npm run build`

Expected: PASS, then build succeeds with the new operations family

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/admin/AdminOverviewView.vue frontend/src/views/admin/AdminLlmOverviewView.vue frontend/src/views/admin/AdminLlmModelsView.vue frontend/src/views/admin/AdminLlmObservabilityView.vue frontend/src/views/admin/AdminLlmCostsView.vue frontend/src/views/admin/AdminLlmFineTunesView.vue frontend/src/components/OpsDashboard.vue frontend/src/components/LlmGatewayDashboard.vue frontend/src/components/LlmGatewayRouting.vue frontend/src/components/LlmGatewayObservability.vue frontend/src/components/LlmGatewayCosts.vue frontend/src/components/ModelConfig.vue frontend/src/components/admin/ops
git commit -m "feat(frontend): rebuild admin llm war room"
```

## Task 9: Rebuild governance pages and finish the handoff checks

**Files:**
- Create: `frontend/src/components/admin/governance/GovernanceReviewDesk.vue`
- Modify: `frontend/src/views/admin/AdminUsersView.vue`
- Modify: `frontend/src/views/admin/AdminEvaluationView.vue`
- Modify: `frontend/src/components/AdminUsers.vue`
- Modify: `frontend/src/components/EvaluationResult.vue`
- Modify: `frontend/src/config/navigation.js`
- Modify: `frontend/src/config/__tests__/navigation.test.js`
- Modify: `frontend/src/router/__tests__/routes.test.js`
- Test: `frontend/src/config/__tests__/navigation.test.js`
- Test: `frontend/src/router/__tests__/routes.test.js`

- [ ] **Step 1: Extend the admin tests for governance continuity**

```js
test('admin navigation still exposes governance pages after the redesign', () => {
  const governanceItems = navigationMap.admin.filter((item) => item.group === 'admin-governance');

  assert.deepEqual(
    governanceItems.map((item) => item.to),
    ['/admin/users', '/admin/evaluation'],
  );
});
```

```js
test('admin route tree still includes the evaluation page route', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('evaluation'));
});
```

- [ ] **Step 2: Run the governance continuity tests**

Run: `cd frontend && npm test -- src/config/__tests__/navigation.test.js src/router/__tests__/routes.test.js`

Expected: PASS before UI work, proving the tests target continuity rather than brand-new routing

- [ ] **Step 3: Introduce the governance review desk**

```vue
<template>
  <section class="governance-review-desk">
    <header class="governance-review-desk__queue"><slot name="queue" /></header>
    <section class="governance-review-desk__comparison"><slot /></section>
    <aside class="governance-review-desk__decision"><slot name="decision" /></aside>
  </section>
</template>
```

- [ ] **Step 4: Recompose users and evaluation pages into review surfaces**

```vue
<template>
  <GovernanceReviewDesk>
    <template #queue>
      <ul class="governance-review-queue">
        <li>待审核对象队列</li>
        <li>高优先级人工复核</li>
        <li>最近异常评测</li>
      </ul>
    </template>
    <section class="governance-review-comparison">
      <slot />
    </section>
    <template #decision>
      <div class="governance-review-actions">
        <button type="button">通过</button>
        <button type="button">驳回</button>
      </div>
    </template>
  </GovernanceReviewDesk>
</template>
```

- [ ] **Step 5: Run the full frontend test suite and production build**

Run: `cd frontend && npm test && npm run build`

Expected: Full test suite PASS, then Vite build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/admin/AdminUsersView.vue frontend/src/views/admin/AdminEvaluationView.vue frontend/src/components/AdminUsers.vue frontend/src/components/EvaluationResult.vue frontend/src/components/admin/governance/GovernanceReviewDesk.vue frontend/src/config/navigation.js frontend/src/config/__tests__/navigation.test.js frontend/src/router/__tests__/routes.test.js
git commit -m "feat(frontend): rebuild admin governance review surfaces"
```

## Final verification checklist

- [ ] `/login` unchanged
- [ ] `/workspace/*` visually reads as dossier work, not as the old product shell
- [ ] `/admin/*` visually reads as war-room operations, not as the old product shell
- [ ] No Inter / Roboto / Arial / purple-blue AI gradients / pure black / equal three-card hero rows / `h-screen`
- [ ] Each major redesigned page split into at least three focused UI units
- [ ] Final handoff response includes the destructive audit table
