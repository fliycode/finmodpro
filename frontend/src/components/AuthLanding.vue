<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import {
  AUTH_BRAND_STATEMENT,
  buildBrandStatementSegments,
  getPasswordToggleLabel,
} from '../lib/auth-landing.js';
import AppIcon from './ui/AppIcon.vue';

const props = defineProps({
  activeTab: {
    type: String,
    required: true,
  },
  showPassword: {
    type: Boolean,
    required: true,
  },
  isLoading: {
    type: Boolean,
    required: true,
  },
  status: {
    type: Object,
    required: true,
  },
  formData: {
    type: Object,
    required: true,
  },
  errors: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits([
  'toggle-tab',
  'submit',
  'toggle-password',
]);

const streamedStatement = ref('');
const usernameInput = ref(null);
let typingTimer = null;

const panelTitle = computed(() => (props.activeTab === 'login' ? '欢迎回来' : '创建账号'));
const panelEyebrow = computed(() => (props.activeTab === 'login' ? 'Welcome back' : 'Create account'));
const submitLabel = computed(() => (props.activeTab === 'login' ? '登录' : '创建账号'));
const statementSegments = computed(() => buildBrandStatementSegments(streamedStatement.value));
const passwordToggleLabel = computed(() => getPasswordToggleLabel(props.showPassword));
const STATEMENT_STREAM_INTERVAL_MS = 56;

const playStatementStream = () => {
  if (typingTimer) {
    clearInterval(typingTimer);
  }

  streamedStatement.value = '';

  let index = 0;
  typingTimer = setInterval(() => {
    index += 1;
    streamedStatement.value = AUTH_BRAND_STATEMENT.slice(0, index);

    if (index >= AUTH_BRAND_STATEMENT.length) {
      clearInterval(typingTimer);
      typingTimer = null;
    }
  }, STATEMENT_STREAM_INTERVAL_MS);
};

const focusUsernameInput = async () => {
  await nextTick();
  usernameInput.value?.focus();
};

onMounted(() => {
  playStatementStream();
  focusUsernameInput();
});

onBeforeUnmount(() => {
  if (typingTimer) {
    clearInterval(typingTimer);
  }
});

watch(() => props.activeTab, () => {
  focusUsernameInput();
});
</script>

<template>
  <section class="auth-entry">
    <div class="auth-entry__mesh"></div>
    <div class="auth-entry__grid"></div>
    <div class="auth-entry__orb auth-entry__orb--one"></div>
    <div class="auth-entry__orb auth-entry__orb--two"></div>

    <div class="auth-entry__shell">
      <aside class="brand-column">
        <div class="brand-column__topline">LLM-powered financial risk platform</div>

        <div class="brand-lockup">
          <div class="brand-lockup__icon-wrap">
            <img src="/favicon.svg" alt="FinModPro icon" class="brand-lockup__icon" />
          </div>
          <div class="brand-lockup__copy">
            <h1>FinModPro</h1>
            <p>基于大模型的金融风控平台</p>
          </div>
        </div>

        <div class="brand-column__statement">
          <h2>
            <template v-for="(segment, index) in statementSegments" :key="`${segment.text}-${index}`">
              <span :class="{ 'statement-accent': segment.emphasis }">{{ segment.text }}</span>
            </template>
            <span class="stream-caret" aria-hidden="true"></span>
          </h2>
        </div>
      </aside>

      <section class="form-column">
        <div class="form-card">
          <div class="tabs" role="tablist" aria-label="Authentication tabs">
            <button
              type="button"
              class="tab-btn"
              :class="{ active: activeTab === 'login' }"
              :disabled="isLoading"
              @click="emit('toggle-tab', 'login')"
            >
              登录
            </button>
            <button
              type="button"
              class="tab-btn"
              :class="{ active: activeTab === 'register' }"
              :disabled="isLoading"
              @click="emit('toggle-tab', 'register')"
            >
              注册
            </button>
          </div>

          <Transition name="auth-panel" mode="out-in">
            <div :key="activeTab" class="auth-panel-shell">
              <div class="panel-intro">
                <span class="panel-intro__eyebrow">{{ panelEyebrow }}</span>
                <h2>{{ panelTitle }}</h2>
              </div>

              <div v-if="status.message" :class="['status-box', status.type]" role="status" aria-live="polite">
                {{ status.message }}
              </div>

              <form class="auth-form" novalidate @submit="emit('submit', $event)">
                <div class="form-group">
                  <label for="username">用户名</label>
                  <input
                    id="username"
                    ref="usernameInput"
                    v-model="formData.username"
                    type="text"
                    :placeholder="activeTab === 'register' ? '例如：finance.ops' : '请输入用户名'"
                    :class="{ 'input-error': errors.username }"
                    :disabled="isLoading"
                  />
                  <span v-if="errors.username" class="error-msg">{{ errors.username }}</span>
                </div>

                <div v-if="activeTab === 'register'" class="form-group">
                  <label for="email">电子邮箱</label>
                  <input
                    id="email"
                    v-model="formData.email"
                    type="email"
                    placeholder="name@company.com"
                    :class="{ 'input-error': errors.email }"
                    :disabled="isLoading"
                  />
                  <span v-if="errors.email" class="error-msg">{{ errors.email }}</span>
                </div>

                <div class="form-group">
                  <div class="label-row">
                    <label for="password">密码</label>
                    <a v-if="activeTab === 'login'" href="#" class="inline-link">忘记密码？</a>
                  </div>
                  <div class="password-input-wrapper">
                    <input
                      id="password"
                      v-model="formData.password"
                      :type="showPassword ? 'text' : 'password'"
                      placeholder="••••••••"
                      :class="{ 'input-error': errors.password }"
                      :disabled="isLoading"
                    />
                    <button
                      type="button"
                      class="toggle-pwd"
                      :aria-label="passwordToggleLabel"
                      :title="passwordToggleLabel"
                      :disabled="isLoading"
                      @click="emit('toggle-password')"
                    >
                      <AppIcon :name="showPassword ? 'eye-off' : 'eye'" />
                    </button>
                  </div>
                  <span v-if="errors.password" class="error-msg">{{ errors.password }}</span>
                </div>

                <div v-if="activeTab === 'register'" class="form-group">
                  <label for="confirmPassword">确认密码</label>
                  <input
                    id="confirmPassword"
                    v-model="formData.confirmPassword"
                    :type="showPassword ? 'text' : 'password'"
                    placeholder="再次输入密码"
                    :class="{ 'input-error': errors.confirmPassword }"
                    :disabled="isLoading"
                  />
                  <span v-if="errors.confirmPassword" class="error-msg">{{ errors.confirmPassword }}</span>
                </div>

                <div v-if="activeTab === 'register'" class="form-group checkbox-group">
                  <label class="checkbox-label" for="agreeTerms">
                    <input id="agreeTerms" v-model="formData.agreeTerms" type="checkbox" :disabled="isLoading" />
                    <span>我同意 <a href="#" class="inline-link">服务条款</a> 与 <a href="#" class="inline-link">隐私政策</a></span>
                  </label>
                  <span v-if="errors.agreeTerms" class="error-msg">{{ errors.agreeTerms }}</span>
                </div>

                <div v-if="activeTab === 'login'" class="form-group checkbox-group checkbox-group--compact">
                  <label class="checkbox-label" for="rememberMe">
                    <input id="rememberMe" v-model="formData.rememberMe" type="checkbox" :disabled="isLoading" />
                    <span>7 天内记住我</span>
                  </label>
                </div>

                <button type="submit" class="primary-button" :disabled="isLoading">
                  <span v-if="isLoading" class="loader"></span>
                  <span v-else>{{ submitLabel }}</span>
                </button>
              </form>
            </div>
          </Transition>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.auth-entry {
  --entry-bg: #eff3f8;
  --entry-panel: rgba(255, 255, 255, 0.88);
  --entry-panel-strong: rgba(255, 255, 255, 0.96);
  --entry-border: rgba(15, 23, 42, 0.09);
  --entry-ink: #0f172a;
  --entry-muted: #5f6b7d;
  --entry-accent: #1d4ed8;
  --entry-accent-soft: rgba(29, 78, 216, 0.12);
  --entry-danger: #b42318;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at top left, rgba(148, 163, 184, 0.2), transparent 28%),
    radial-gradient(circle at 85% 18%, rgba(59, 130, 246, 0.12), transparent 24%),
    linear-gradient(180deg, #f7f9fc 0%, var(--entry-bg) 100%);
}

.auth-entry__mesh,
.auth-entry__grid,
.auth-entry__orb {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.auth-entry__mesh {
  background:
    radial-gradient(circle at 24% 24%, rgba(255, 255, 255, 0.78), transparent 28%),
    radial-gradient(circle at 78% 14%, rgba(191, 219, 254, 0.38), transparent 22%);
  animation: meshDrift 18s ease-in-out infinite;
}

.auth-entry__grid {
  opacity: 0.5;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(circle at center, black 44%, transparent 88%);
}

.auth-entry__orb {
  inset: auto;
  border-radius: 999px;
  filter: blur(18px);
  opacity: 0.9;
  mix-blend-mode: screen;
}

.auth-entry__orb--one {
  top: 12%;
  left: 7%;
  width: 300px;
  height: 300px;
  background:
    radial-gradient(circle, rgba(59, 130, 246, 0.28) 0%, rgba(96, 165, 250, 0.14) 36%, rgba(59, 130, 246, 0) 72%);
  animation: orbFloatOne 14s ease-in-out infinite;
}

.auth-entry__orb--two {
  right: 5%;
  bottom: 10%;
  width: 360px;
  height: 360px;
  background:
    radial-gradient(circle, rgba(15, 23, 42, 0.18) 0%, rgba(37, 99, 235, 0.12) 42%, rgba(15, 23, 42, 0) 76%);
  animation: orbFloatTwo 16s ease-in-out infinite;
}

.auth-entry__shell {
  position: relative;
  z-index: 1;
  width: min(1120px, 100%);
  min-height: 700px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 430px);
  border: 1px solid var(--entry-border);
  border-radius: 30px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.58));
  box-shadow:
    0 28px 80px rgba(15, 23, 42, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.76);
  backdrop-filter: blur(18px);
  animation: shellReveal 560ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.brand-column,
.form-card {
  opacity: 0;
  animation: contentReveal 480ms ease both;
}

.brand-column {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28px;
  padding: 56px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.46), rgba(255, 255, 255, 0)),
    linear-gradient(160deg, rgba(241, 245, 249, 0.92), rgba(219, 234, 254, 0.62) 58%, rgba(226, 232, 240, 0.66));
}

.brand-column::after {
  content: '';
  position: absolute;
  inset: 20px;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  pointer-events: none;
}

.brand-column__topline,
.panel-intro__eyebrow {
  margin: 0;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.73rem;
  font-weight: 700;
}

.brand-lockup {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 16px;
}

.brand-lockup__icon-wrap {
  width: 90px;
  height: 90px;
  border-radius: 26px;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.04), rgba(15, 23, 42, 0.09));
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 18px 38px rgba(30, 41, 59, 0.1);
}

.brand-lockup__icon {
  width: 62px;
  height: 62px;
  object-fit: contain;
  animation: iconPulse 7s ease-in-out infinite;
}

.brand-lockup__copy h1,
.brand-column__statement h2,
.panel-intro h2 {
  margin: 0;
  color: var(--entry-ink);
  font-family: 'Iowan Old Style', 'Palatino Linotype', 'Noto Serif SC', serif;
}

.brand-lockup__copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.brand-lockup__copy h1 {
  font-size: clamp(2.8rem, 4vw, 4.4rem);
  line-height: 0.94;
  letter-spacing: -0.05em;
}

.brand-lockup__copy p {
  margin: 4px 0 0;
  color: var(--entry-muted);
  line-height: 1.55;
  max-width: 420px;
}

.brand-column__statement {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 620px;
  min-height: 0;
  padding: 18px 20px 20px;
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.16)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(191, 219, 254, 0.1));
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
}

.brand-column__statement h2 {
  font-size: clamp(1.95rem, 2.65vw, 3.1rem);
  line-height: 1.16;
  letter-spacing: -0.04em;
  max-width: 560px;
}

.statement-accent {
  color: var(--entry-accent);
  font-weight: 700;
}

.stream-caret {
  display: inline-block;
  width: 0.12em;
  height: 0.96em;
  margin-left: 0.08em;
  vertical-align: -0.08em;
  border-radius: 999px;
  background: rgba(29, 78, 216, 0.72);
  animation: caretBlink 1s steps(1) infinite;
}

.form-column {
  padding: 24px;
  display: flex;
  align-items: stretch;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.4), rgba(248, 250, 252, 0.76));
}

.form-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 24px;
  padding: 36px;
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: var(--entry-panel-strong);
  box-shadow:
    0 18px 42px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  animation-delay: 140ms;
}

.tabs {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 6px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.78);
  align-self: flex-start;
}

.tab-btn {
  border: 0;
  border-radius: 999px;
  padding: 10px 18px;
  background: transparent;
  color: #475569;
  font-size: 0.94rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 180ms ease,
    background-color 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease;
}

.tab-btn.active {
  background: linear-gradient(180deg, #1e293b, #0f172a);
  color: #f8fafc;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.18);
}

.tab-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  color: var(--entry-ink);
}

.auth-panel-shell {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.panel-intro {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-intro h2 {
  font-size: clamp(1.9rem, 2vw, 2.35rem);
  line-height: 1.08;
  letter-spacing: -0.04em;
}

.auth-panel-enter-active,
.auth-panel-leave-active {
  transition:
    opacity 260ms ease,
    transform 320ms cubic-bezier(0.2, 0.8, 0.2, 1),
    filter 320ms ease;
}

.auth-panel-enter-from {
  opacity: 0;
  transform: translateY(14px);
  filter: blur(8px);
}

.auth-panel-leave-to {
  opacity: 0;
  transform: translateY(-10px);
  filter: blur(6px);
}

.status-box {
  padding: 13px 15px;
  border-radius: 16px;
  font-size: 0.92rem;
  line-height: 1.55;
  animation: statusFade 220ms ease;
}

.status-box.success {
  background: rgba(22, 163, 74, 0.1);
  color: #166534;
  border: 1px solid rgba(22, 163, 74, 0.16);
}

.status-box.error {
  background: rgba(180, 35, 24, 0.08);
  color: #912018;
  border: 1px solid rgba(180, 35, 24, 0.14);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.form-group label,
.label-row {
  color: var(--entry-ink);
  font-size: 0.92rem;
  font-weight: 600;
}

.label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-group input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 16px;
  padding: 14px 16px;
  background: var(--entry-panel);
  color: var(--entry-ink);
  outline: none;
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease,
    transform 180ms ease;
}

.form-group input::placeholder {
  color: rgba(100, 116, 139, 0.9);
}

.form-group input:focus {
  border-color: rgba(29, 78, 216, 0.45);
  background: #ffffff;
  box-shadow: 0 0 0 4px var(--entry-accent-soft);
  transform: translateY(-1px);
}

.input-error {
  border-color: rgba(180, 35, 24, 0.35) !important;
  box-shadow: 0 0 0 4px rgba(180, 35, 24, 0.08) !important;
}

.password-input-wrapper {
  position: relative;
}

.password-input-wrapper input {
  padding-right: 56px;
}

.toggle-pwd {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: #48617e;
  cursor: pointer;
  width: 36px;
  height: 36px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  transition: background-color 180ms ease, color 180ms ease;
}

.toggle-pwd:hover:not(:disabled) {
  background: rgba(29, 78, 216, 0.08);
  color: var(--entry-accent);
}

.toggle-pwd :deep(.app-icon) {
  width: 17px;
  height: 17px;
}

.checkbox-group {
  gap: 8px;
}

.checkbox-group--compact {
  margin-top: -4px;
}

.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: var(--entry-muted);
  font-size: 0.92rem;
  line-height: 1.6;
  font-weight: 400;
}

.checkbox-label input {
  width: 18px;
  height: 18px;
  margin-top: 3px;
  padding: 0;
}

.inline-link {
  color: var(--entry-accent);
  text-decoration: none;
}

.inline-link:hover {
  text-decoration: underline;
}

.error-msg {
  color: var(--entry-danger);
  font-size: 0.84rem;
}

.primary-button {
  border: 0;
  border-radius: 16px;
  padding: 15px 20px;
  background: linear-gradient(180deg, #2563eb, #1d4ed8);
  color: #f8fafc;
  cursor: pointer;
  font-size: 0.98rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-2px);
  filter: brightness(1.02);
  box-shadow: 0 16px 28px rgba(37, 99, 235, 0.24);
}

.primary-button:disabled,
.tab-btn:disabled,
.toggle-pwd:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.loader {
  display: inline-block;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(248, 250, 252, 0.4);
  border-top-color: #f8fafc;
  animation: spin 0.8s linear infinite;
}

@keyframes shellReveal {
  from {
    opacity: 0;
    transform: translateY(24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes contentReveal {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes meshDrift {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }

  50% {
    transform: translate3d(-8px, 12px, 0) scale(1.03);
  }
}

@keyframes orbFloatOne {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }

  50% {
    transform: translate3d(18px, -14px, 0) scale(1.08);
  }
}

@keyframes orbFloatTwo {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }

  50% {
    transform: translate3d(-22px, 16px, 0) scale(1.06);
  }
}

@keyframes iconPulse {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-4px);
  }
}

@keyframes caretBlink {
  0%,
  49% {
    opacity: 1;
  }

  50%,
  100% {
    opacity: 0;
  }
}

@keyframes statusFade {
  from {
    opacity: 0;
    transform: translateY(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1040px) {
  .auth-entry {
    padding: 18px;
  }

  .auth-entry__shell {
    min-height: auto;
    grid-template-columns: 1fr;
  }

  .brand-column {
    padding: 36px 36px 28px;
  }

  .form-column {
    padding: 0 18px 18px;
  }
}

@media (max-width: 640px) {
  .auth-entry {
    padding: 12px;
  }

  .brand-column,
  .form-card {
    padding: 24px;
  }

  .brand-lockup {
    grid-template-columns: 1fr;
  }

  .brand-lockup__icon-wrap {
    width: 78px;
    height: 78px;
    border-radius: 22px;
  }

  .brand-lockup__icon {
    width: 54px;
    height: 54px;
  }

  .brand-column__statement {
    min-height: 152px;
    padding: 22px 22px 24px;
  }

  .tabs {
    width: 100%;
  }

  .tab-btn {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-entry__shell,
  .auth-entry__mesh,
  .auth-entry__orb,
  .brand-column,
  .form-card,
  .brand-lockup__icon,
  .stream-caret,
  .status-box,
  .loader {
    animation: none !important;
    transition: none !important;
  }

  .form-group input:focus,
  .tab-btn:hover:not(:disabled),
  .primary-button:hover:not(:disabled) {
    transform: none;
  }
}
</style>
