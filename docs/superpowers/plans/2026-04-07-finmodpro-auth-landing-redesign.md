# FinModPro Auth Landing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the unauthenticated FinModPro landing page into a balanced brand-first login experience with restrained motion while preserving the existing auth flow and view switching logic.

**Architecture:** Keep `frontend/src/App.vue` as the auth state container and route switch, and concentrate the redesign inside `frontend/src/components/AuthLanding.vue`. Use component-scoped markup and CSS for the new layered lobby layout and motion system, relying on native Vue state and CSS keyframes/transitions instead of adding animation dependencies.

**Tech Stack:** Vue 3, Vite, component-scoped CSS, existing auth API and storage helpers

---

### Task 1: Replace the AuthLanding structure with the new brand-lobby layout

**Files:**
- Modify: `frontend/src/components/AuthLanding.vue`
- Test: `frontend/src/components/AuthLanding.vue`

- [ ] **Step 1: Write the failing structural check**

Add a temporary text assertion target to the component plan by verifying that the current template does not yet contain the new lobby copy or section names.

```bash
rg -n "brand-stage|auth-lobby|Risk Intelligence|Governed Access" frontend/src/components/AuthLanding.vue
```

Expected: no matches

- [ ] **Step 2: Run the structural check to verify it fails**

Run:

```bash
rg -n "brand-stage|auth-lobby|Risk Intelligence|Governed Access" frontend/src/components/AuthLanding.vue
```

Expected: exit code `1`

- [ ] **Step 3: Replace the content model with the new brand copy**

Update the script data so the component drives the new experience with concise brand messaging instead of the current feature/checkpoint blocks.

```vue
const capabilityPills = [
  'Financial Modeling',
  'Risk Intelligence',
  'Governed Access'
];

const signalMetrics = [
  { label: 'Workflow', value: 'Modeling + QA' },
  { label: 'Control', value: 'RBAC Ready' },
  { label: 'Output', value: 'Decision-ready' }
];
```

Delete the old `features`, `checkpoints`, and `trustItems` arrays once the new ones are wired into the template.

- [ ] **Step 4: Rewrite the template around the lobby card**

Replace the current `auth-shell` content with a single unauthenticated hero card that has:

- a background atmosphere layer
- a left brand stage with the logo, value proposition, capability pills, and signal metrics
- a right form chamber that preserves the existing login/register fields and submit behavior

Use a structure equivalent to:

```vue
<section class="auth-lobby">
  <div class="auth-lobby__ambient auth-lobby__ambient--one"></div>
  <div class="auth-lobby__ambient auth-lobby__ambient--two"></div>

  <div class="auth-lobby__frame">
    <aside class="brand-stage">
      <p class="brand-stage__eyebrow">Financial Modeling Platform</p>
      <div class="brand-stage__lockup">
        <img :src="finmodproLogo" alt="FinModPro logo" class="brand-stage__logo" />
        <div>
          <h1>FinModPro</h1>
          <p class="brand-stage__lede">进入更可信的财务建模与风险决策工作流。</p>
        </div>
      </div>

      <div class="brand-stage__story">
        <span class="brand-stage__badge">Brand Lobby</span>
        <h2>为建模、分析、治理与协作准备的统一入口</h2>
        <p>一个兼顾展示感与登录效率的品牌门厅，让 FinModPro 在首屏就建立信任和辨识度。</p>
      </div>

      <div class="brand-stage__pills">
        <span v-for="pill in capabilityPills" :key="pill">{{ pill }}</span>
      </div>

      <div class="brand-stage__metrics">
        <article v-for="item in signalMetrics" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </aside>

    <section class="form-chamber">
      <div class="tabs" role="tablist" aria-label="Authentication tabs">
        <button type="button" class="tab-btn" :class="{ active: activeTab === 'login' }" :disabled="isLoading" @click="emit('toggle-tab', 'login')">登录</button>
        <button type="button" class="tab-btn" :class="{ active: activeTab === 'register' }" :disabled="isLoading" @click="emit('toggle-tab', 'register')">注册</button>
      </div>

      <div class="panel-intro">
        <span class="panel-intro__eyebrow">{{ activeTab === 'login' ? 'Welcome back' : 'Create workspace access' }}</span>
        <h2>{{ activeTab === 'login' ? '登录后继续您的建模与分析工作' : '创建 FinModPro 账号以启用团队工作流' }}</h2>
      </div>

      <div v-if="status.message" :class="['status-box', status.type]" role="status" aria-live="polite">
        {{ status.message }}
      </div>

      <form class="auth-form" novalidate @submit="emit('submit', $event)">
        <div class="form-group">
          <label for="username">用户名</label>
          <input id="username" v-model="formData.username" type="text" :disabled="isLoading" :class="{ 'input-error': errors.username }" />
          <span v-if="errors.username" class="error-msg">{{ errors.username }}</span>
        </div>

        <div v-if="activeTab === 'register'" class="form-group">
          <label for="email">电子邮箱</label>
          <input id="email" v-model="formData.email" type="email" :disabled="isLoading" :class="{ 'input-error': errors.email }" />
          <span v-if="errors.email" class="error-msg">{{ errors.email }}</span>
        </div>

        <div class="form-group">
          <label for="password">密码</label>
          <input id="password" v-model="formData.password" :type="showPassword ? 'text' : 'password'" :disabled="isLoading" :class="{ 'input-error': errors.password }" />
          <span v-if="errors.password" class="error-msg">{{ errors.password }}</span>
        </div>

        <div v-if="activeTab === 'register'" class="form-group">
          <label for="confirmPassword">确认密码</label>
          <input id="confirmPassword" v-model="formData.confirmPassword" :type="showPassword ? 'text' : 'password'" :disabled="isLoading" :class="{ 'input-error': errors.confirmPassword }" />
          <span v-if="errors.confirmPassword" class="error-msg">{{ errors.confirmPassword }}</span>
        </div>

        <div v-if="activeTab === 'register'" class="form-group checkbox-group">
          <label class="checkbox-label" for="agreeTerms">
            <input id="agreeTerms" v-model="formData.agreeTerms" type="checkbox" :disabled="isLoading" />
            <span>我同意 <a href="#" class="inline-link">服务条款</a> 与 <a href="#" class="inline-link">隐私政策</a></span>
          </label>
          <span v-if="errors.agreeTerms" class="error-msg">{{ errors.agreeTerms }}</span>
        </div>

        <button type="submit" class="primary-button" :disabled="isLoading">
          <span v-if="isLoading" class="loader"></span>
          <span v-else>{{ activeTab === 'login' ? '登录 FinModPro' : '创建账号并继续' }}</span>
        </button>
      </form>
    </section>
  </div>
</section>
```

Do not change any emitted event names, `v-model` bindings, validation error bindings, or submit wiring inside the form.

- [ ] **Step 5: Run the structural check to verify it passes**

Run:

```bash
rg -n "brand-stage|auth-lobby|Risk Intelligence|Governed Access" frontend/src/components/AuthLanding.vue
```

Expected: matches for the new layout and copy

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AuthLanding.vue
git commit -m "feat: redesign auth landing layout"
```

### Task 2: Add the visual system, motion, and responsive behavior

**Files:**
- Modify: `frontend/src/components/AuthLanding.vue`
- Modify: `frontend/src/style.css`
- Test: `frontend/src/components/AuthLanding.vue`

- [ ] **Step 1: Write the failing style check**

Verify the component does not yet define the new motion and lobby class names.

```bash
rg -n "lobbyFloat|lobbyReveal|brand-stage__logo-ring|form-chamber" frontend/src/components/AuthLanding.vue
```

Expected: the motion class names are missing before this task starts

- [ ] **Step 2: Run the style check to verify it fails**

Run:

```bash
rg -n "lobbyFloat|lobbyReveal|brand-stage__logo-ring|form-chamber" frontend/src/components/AuthLanding.vue
```

Expected: no full set of matches

- [ ] **Step 3: Replace the component-scoped CSS with the new visual system**

Add scoped styles to `frontend/src/components/AuthLanding.vue` for:

- warm layered background
- large central frame with translucent panel treatment
- serif-forward heading presentation
- refined input and button styling
- responsive collapse from two columns to one
- reduced-motion support

The style block should include structures like:

```css
.auth-lobby {
  --lobby-bg: #f5efe6;
  --lobby-ink: #211913;
  --lobby-muted: #6e5a49;
  --lobby-panel: rgba(255, 252, 247, 0.76);
  --lobby-border: rgba(70, 48, 24, 0.12);
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(214, 183, 124, 0.22), transparent 34%),
    linear-gradient(135deg, #f7f1e8 0%, #efe4d4 52%, #f9f4ed 100%);
}

.auth-lobby__frame {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(360px, 0.92fr);
  border-radius: 32px;
  background: var(--lobby-panel);
  backdrop-filter: blur(18px);
  animation: lobbyReveal 720ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.brand-stage__logo {
  animation: lobbyFloat 8s ease-in-out infinite;
}

@keyframes lobbyReveal {
  from { opacity: 0; transform: translateY(26px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes lobbyFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

@media (prefers-reduced-motion: reduce) {
  .auth-lobby__frame,
  .brand-stage__logo,
  .auth-lobby__ambient {
    animation: none !important;
    transition: none !important;
  }
}
```

- [ ] **Step 4: Align the global root styles with the new landing page**

Trim the default Vite starter page styles in `frontend/src/style.css` so the root app container no longer imposes narrow centered borders or a template-like text alignment.

Replace the root rules with a minimal app shell:

```css
:root {
  font-family: 'Segoe UI', 'PingFang SC', 'Noto Sans SC', sans-serif;
  color: #211913;
  background: #f5efe6;
}

body {
  margin: 0;
  min-width: 320px;
  background: #f5efe6;
}

#app {
  min-height: 100vh;
}

* {
  box-sizing: border-box;
}

button,
input {
  font: inherit;
}
```

Keep only global rules that are still useful across the app. Remove or neutralize legacy `.hero`, `#center`, `#next-steps`, and similar starter styles if they are no longer referenced.

- [ ] **Step 5: Run a build to verify the styling compiles**

Run:

```bash
npm run build
```

In:

```bash
frontend
```

Expected: Vite production build completes successfully

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AuthLanding.vue frontend/src/style.css
git commit -m "feat: add auth landing motion and visual polish"
```

### Task 3: Tighten auth-state integration and remove unused landing props

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/AuthLanding.vue`
- Test: `frontend/src/App.vue`

- [ ] **Step 1: Write the failing prop-usage check**

Confirm the landing component still receives logged-in-only data that the redesigned screen should not need.

```bash
rg -n ":currentUser|:isAdmin|navigate-admin|logout|enter-workbench" frontend/src/App.vue frontend/src/components/AuthLanding.vue
```

Expected: matches show unused or unnecessary bindings in the unauthenticated landing path

- [ ] **Step 2: Run the check to capture the current coupling**

Run:

```bash
rg -n ":currentUser|:isAdmin|navigate-admin|logout|enter-workbench" frontend/src/App.vue frontend/src/components/AuthLanding.vue
```

Expected: matches in both files

- [ ] **Step 3: Remove logged-in-only props and emits from AuthLanding**

Update `frontend/src/components/AuthLanding.vue` so the component only accepts the props and emits it actually uses for the unauthenticated flow.

The definition should reduce to a shape like:

```vue
const props = defineProps({
  activeTab: { type: String, required: true },
  showPassword: { type: Boolean, required: true },
  isLoading: { type: Boolean, required: true },
  status: { type: Object, required: true },
  formData: { type: Object, required: true },
  errors: { type: Object, required: true }
});

const emit = defineEmits([
  'toggle-tab',
  'submit',
  'toggle-password'
]);
```

Delete the old permission panel and any unreachable logged-in-only action buttons from the template.

- [ ] **Step 4: Remove the stale bindings in App.vue**

Update the `AuthLanding` usage in `frontend/src/App.vue` so it only passes auth-form state and events that the landing page still consumes.

The final usage should be equivalent to:

```vue
<AuthLanding
  v-else
  :activeTab="activeTab"
  :showPassword="showPassword"
  :isLoading="isLoading"
  :status="status"
  :formData="formData"
  :errors="errors"
  @toggle-tab="toggleTab"
  @submit="handleSubmit"
  @toggle-password="showPassword = !showPassword"
/>
```

- [ ] **Step 5: Run the prop-usage check to verify the coupling is gone**

Run:

```bash
rg -n ":currentUser|:isAdmin|navigate-admin|logout|enter-workbench" frontend/src/App.vue frontend/src/components/AuthLanding.vue
```

Expected: no matches inside the `AuthLanding` path

- [ ] **Step 6: Run the frontend build again**

Run:

```bash
npm run build
```

In:

```bash
frontend
```

Expected: build succeeds with the cleaned component interface

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.vue frontend/src/components/AuthLanding.vue
git commit -m "refactor: simplify auth landing integration"
```

### Task 4: Verify the final experience manually and record outcomes

**Files:**
- Modify: `docs/test-report.md`
- Test: `frontend/src/App.vue`
- Test: `frontend/src/components/AuthLanding.vue`

- [ ] **Step 1: Add a manual verification checklist entry**

Append a short section to `docs/test-report.md` capturing the auth landing redesign verification items.

Use content like:

```md
## 2026-04-07 Auth Landing Redesign

- [ ] Login tab renders the new brand-lobby layout on desktop width
- [ ] Register tab renders email, confirm password, and terms fields
- [ ] Status and validation messages remain visible in the redesigned form area
- [ ] Mobile width collapses the layout into a single column without horizontal scroll
- [ ] Reduced-motion mode disables continuous ambient animation
```

- [ ] **Step 2: Run the production build as a final regression check**

Run:

```bash
npm run build
```

In:

```bash
frontend
```

Expected: build succeeds

- [ ] **Step 3: Run the dev server for visual verification**

Run:

```bash
npm run dev -- --host 0.0.0.0
```

In:

```bash
frontend
```

Expected: Vite prints a local URL and serves the redesigned landing page

- [ ] **Step 4: Verify the login and register UI states manually**

Check these states in the browser:

- desktop login tab
- desktop register tab
- mobile width around `390px`
- reduced motion in browser devtools

Record the outcome by updating the checklist in `docs/test-report.md`.

- [ ] **Step 5: Commit**

```bash
git add docs/test-report.md
git commit -m "docs: record auth landing verification"
```
