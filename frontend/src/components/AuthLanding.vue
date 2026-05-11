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

const panelTitle = computed(() => {
  if (props.activeTab === 'forgot') return '忘记密码';
  if (props.activeTab === 'reset') return '重置密码';
  return props.activeTab === 'login' ? '欢迎回来' : '创建账号';
});
const panelEyebrow = computed(() => {
  if (props.activeTab === 'forgot') return 'Forgot password';
  if (props.activeTab === 'reset') return 'Reset password';
  return props.activeTab === 'login' ? 'Welcome back' : 'Create account';
});
const submitLabel = computed(() => {
  if (props.activeTab === 'forgot') return '发送重置链接';
  if (props.activeTab === 'reset') return '重置密码';
  return props.activeTab === 'login' ? '登录' : '创建账号';
});
const statementSegments = computed(() => buildBrandStatementSegments(streamedStatement.value));
const passwordToggleLabel = computed(() => getPasswordToggleLabel(props.showPassword));
const STATEMENT_STREAM_INTERVAL_MS = 56;

const prefersReducedMotion = typeof window !== 'undefined'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const playStatementStream = () => {
  if (typingTimer) {
    clearInterval(typingTimer);
  }

  if (prefersReducedMotion) {
    streamedStatement.value = AUTH_BRAND_STATEMENT;
    return;
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
              role="tab"
              class="tab-btn"
              :class="{ active: activeTab === 'login' }"
              :aria-selected="activeTab === 'login'"
              :tabindex="activeTab === 'login' ? 0 : -1"
              :disabled="isLoading"
              @click="emit('toggle-tab', 'login')"
            >
              登录
            </button>
            <button
              type="button"
              role="tab"
              class="tab-btn"
              :class="{ active: activeTab === 'register' }"
              :aria-selected="activeTab === 'register'"
              :tabindex="activeTab === 'register' ? 0 : -1"
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
                <!-- Login / Register fields -->
                <template v-if="activeTab === 'login' || activeTab === 'register'">
                  <div class="form-group">
                    <label for="username">用户名</label>
                    <input
                      id="username"
                      ref="usernameInput"
                      v-model="formData.username"
                      type="text"
                      autocomplete="username"
                      maxlength="64"
                      :placeholder="activeTab === 'register' ? '例如：finance.ops' : '请输入用户名'"
                      :class="{ 'input-error': errors.username }"
                      :aria-invalid="!!errors.username"
                      :aria-describedby="errors.username ? 'username-error' : undefined"
                      :disabled="isLoading"
                    />
                    <span v-if="errors.username" id="username-error" class="error-msg" role="alert">{{ errors.username }}</span>
                  </div>

                  <div v-if="activeTab === 'register'" class="form-group">
                    <label for="email">电子邮箱</label>
                    <input
                      id="email"
                      v-model="formData.email"
                      type="email"
                      autocomplete="email"
                      maxlength="254"
                      placeholder="name@company.com"
                      :class="{ 'input-error': errors.email }"
                      :aria-invalid="!!errors.email"
                      :aria-describedby="errors.email ? 'email-error' : undefined"
                      :disabled="isLoading"
                    />
                    <span v-if="errors.email" id="email-error" class="error-msg" role="alert">{{ errors.email }}</span>
                  </div>

                  <div class="form-group">
                    <div class="label-row">
                      <label for="password">密码</label>
                      <button
                        v-if="activeTab === 'login'"
                        type="button"
                        class="inline-link inline-link--muted"
                        :disabled="isLoading"
                        @click="emit('toggle-tab', 'forgot')"
                      >忘记密码？</button>
                    </div>
                    <div class="password-input-wrapper">
                      <input
                        id="password"
                        v-model="formData.password"
                        :type="showPassword ? 'text' : 'password'"
                        :autocomplete="activeTab === 'login' ? 'current-password' : 'new-password'"
                        maxlength="128"
                        placeholder="••••••••"
                        :class="{ 'input-error': errors.password }"
                        :aria-invalid="!!errors.password"
                        :aria-describedby="errors.password ? 'password-error' : undefined"
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
                    <span v-if="errors.password" id="password-error" class="error-msg" role="alert">{{ errors.password }}</span>
                  </div>

                  <div v-if="activeTab === 'register'" class="form-group">
                    <label for="confirmPassword">确认密码</label>
                    <input
                      id="confirmPassword"
                      v-model="formData.confirmPassword"
                      :type="showPassword ? 'text' : 'password'"
                      autocomplete="new-password"
                      maxlength="128"
                      placeholder="再次输入密码"
                      :class="{ 'input-error': errors.confirmPassword }"
                      :aria-invalid="!!errors.confirmPassword"
                      :aria-describedby="errors.confirmPassword ? 'confirm-password-error' : undefined"
                      :disabled="isLoading"
                    />
                    <span v-if="errors.confirmPassword" id="confirm-password-error" class="error-msg" role="alert">{{ errors.confirmPassword }}</span>
                  </div>

                  <div v-if="activeTab === 'register'" class="form-group checkbox-group">
                    <label class="checkbox-label" for="agreeTerms">
                      <input id="agreeTerms" v-model="formData.agreeTerms" type="checkbox" :disabled="isLoading" />
                      <span>我同意 <span class="inline-link inline-link--muted">服务条款</span> 与 <span class="inline-link inline-link--muted">隐私政策</span></span>
                    </label>
                    <span v-if="errors.agreeTerms" class="error-msg" role="alert">{{ errors.agreeTerms }}</span>
                  </div>

                  <div v-if="activeTab === 'login'" class="form-group checkbox-group checkbox-group--compact">
                    <label class="checkbox-label" for="rememberMe">
                      <input id="rememberMe" v-model="formData.rememberMe" type="checkbox" :disabled="isLoading" />
                      <span>7 天内免登录</span>
                    </label>
                  </div>
                </template>

                <!-- Forgot password fields -->
                <template v-if="activeTab === 'forgot'">
                  <div class="form-group">
                    <label for="username">用户名</label>
                    <input
                      id="username"
                      ref="usernameInput"
                      v-model="formData.username"
                      type="text"
                      autocomplete="username"
                      maxlength="64"
                      placeholder="请输入注册时的用户名"
                      :class="{ 'input-error': errors.username }"
                      :aria-invalid="!!errors.username"
                      :aria-describedby="errors.username ? 'username-error' : undefined"
                      :disabled="isLoading"
                    />
                    <span v-if="errors.username" id="username-error" class="error-msg" role="alert">{{ errors.username }}</span>
                  </div>
                  <p class="forgot-hint">输入用户名后，系统将生成密码重置链接。</p>
                </template>

                <!-- Reset password fields -->
                <template v-if="activeTab === 'reset'">
                  <div class="form-group">
                    <div class="label-row">
                      <label for="password">新密码</label>
                    </div>
                    <div class="password-input-wrapper">
                      <input
                        id="password"
                        v-model="formData.password"
                        :type="showPassword ? 'text' : 'password'"
                        autocomplete="new-password"
                        maxlength="128"
                        placeholder="••••••••"
                        :class="{ 'input-error': errors.password }"
                        :aria-invalid="!!errors.password"
                        :aria-describedby="errors.password ? 'password-error' : undefined"
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
                    <span v-if="errors.password" id="password-error" class="error-msg" role="alert">{{ errors.password }}</span>
                  </div>

                  <div class="form-group">
                    <label for="confirmPassword">确认新密码</label>
                    <input
                      id="confirmPassword"
                      v-model="formData.confirmPassword"
                      :type="showPassword ? 'text' : 'password'"
                      autocomplete="new-password"
                      maxlength="128"
                      placeholder="再次输入密码"
                      :class="{ 'input-error': errors.confirmPassword }"
                      :aria-invalid="!!errors.confirmPassword"
                      :aria-describedby="errors.confirmPassword ? 'confirm-password-error' : undefined"
                      :disabled="isLoading"
                    />
                    <span v-if="errors.confirmPassword" id="confirm-password-error" class="error-msg" role="alert">{{ errors.confirmPassword }}</span>
                  </div>
                </template>

                <button type="submit" class="primary-button" :disabled="isLoading">
                  <span v-if="isLoading" class="loader"></span>
                  <span v-else>{{ submitLabel }}</span>
                </button>

                <div v-if="activeTab === 'forgot' || activeTab === 'reset'" class="back-to-login">
                  <button
                    type="button"
                    class="inline-link inline-link--muted"
                    :disabled="isLoading"
                    @click="emit('toggle-tab', 'login')"
                  >返回登录</button>
                </div>
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
  --entry-bg-top: #f7f9fc;
  --entry-bg: #eef2f7;
  --entry-shell-surface: linear-gradient(180deg, rgba(248, 250, 252, 0.82), rgba(240, 245, 251, 0.62));
  --entry-shell-border: rgba(15, 23, 42, 0.09);
  --entry-shell-shadow:
    0 28px 80px rgba(15, 23, 42, 0.1),
    inset 0 1px 0 rgba(248, 250, 252, 0.78);
  --entry-brand-surface:
    linear-gradient(180deg, rgba(248, 250, 252, 0.52), rgba(248, 250, 252, 0)),
    linear-gradient(160deg, rgba(241, 245, 249, 0.94), rgba(219, 234, 254, 0.62) 58%, rgba(226, 232, 240, 0.68));
  --entry-brand-outline: rgba(148, 163, 184, 0.14);
  --entry-form-column-surface: linear-gradient(180deg, rgba(248, 250, 252, 0.48), rgba(240, 244, 249, 0.78));
  --entry-panel: rgba(248, 250, 252, 0.82);
  --entry-panel-strong: rgba(248, 250, 252, 0.94);
  --entry-panel-border: rgba(148, 163, 184, 0.16);
  --entry-panel-shadow:
    0 18px 42px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(248, 250, 252, 0.82);
  --entry-ink: #172033;
  --entry-muted: #5f6b7d;
  --entry-topline: #64748b;
  --entry-accent: #2457c5;
  --entry-accent-strong: #1d48a8;
  --entry-accent-contrast: #f8f9fb;
  --entry-accent-soft: rgba(36, 87, 197, 0.12);
  --entry-danger: #b42318;
  --entry-tab-rail: rgba(226, 232, 240, 0.78);
  --entry-tab-text: #475569;
  --entry-tab-active-bg: rgba(36, 87, 197, 0.14);
  --entry-tab-active-color: #183c8a;
  --entry-focus-border: rgba(36, 87, 197, 0.45);
  --entry-input-bg: rgba(248, 250, 252, 0.88);
  --entry-input-border: rgba(148, 163, 184, 0.24);
  --entry-input-focus-bg: rgba(255, 255, 255, 0.96);
  --entry-input-placeholder: rgba(100, 116, 139, 0.9);
  --entry-toggle-ink: #48617e;
  --entry-toggle-hover-bg: rgba(36, 87, 197, 0.08);
  --entry-button-bg: #2457c5;
  --entry-button-hover-bg: #1d48a8;
  --entry-button-text: #f8f9fb;
  --entry-button-shadow: 0 18px 38px rgba(36, 87, 197, 0.22);
  --entry-status-success-bg: rgba(33, 129, 92, 0.1);
  --entry-status-success-ink: #166534;
  --entry-status-success-border: rgba(33, 129, 92, 0.16);
  --entry-status-error-bg: rgba(180, 35, 24, 0.08);
  --entry-status-error-ink: #912018;
  --entry-status-error-border: rgba(180, 35, 24, 0.14);
  --entry-icon-surface: linear-gradient(180deg, rgba(15, 23, 42, 0.04), rgba(15, 23, 42, 0.09));
  --entry-icon-border: rgba(15, 23, 42, 0.08);
  --entry-icon-shadow:
    inset 0 1px 0 rgba(248, 250, 252, 0.72),
    0 18px 38px rgba(30, 41, 59, 0.1);
  --entry-statement-surface:
    linear-gradient(180deg, rgba(248, 250, 252, 0.34), rgba(248, 250, 252, 0.16)),
    linear-gradient(135deg, rgba(248, 250, 252, 0.12), rgba(191, 219, 254, 0.1));
  --entry-statement-border: rgba(148, 163, 184, 0.12);
  --entry-statement-shadow: inset 0 1px 0 rgba(248, 250, 252, 0.55);
  --entry-grid-line: rgba(148, 163, 184, 0.08);
  --entry-mesh-one: rgba(248, 250, 252, 0.8);
  --entry-mesh-two: rgba(191, 219, 254, 0.38);
  --entry-orb-one: radial-gradient(circle, rgba(96, 106, 180, 0.2) 0%, rgba(96, 106, 180, 0.1) 36%, rgba(96, 106, 180, 0) 72%);
  --entry-orb-two: radial-gradient(circle, rgba(60, 70, 100, 0.14) 0%, rgba(60, 70, 100, 0.08) 42%, rgba(60, 70, 100, 0) 76%);
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
    linear-gradient(180deg, var(--entry-bg-top) 0%, var(--entry-bg) 100%);
}

:global(:root[data-theme='dark']) .auth-entry {
  --entry-bg-top: #131c2d;
  --entry-bg: #101827;
  --entry-shell-surface: linear-gradient(180deg, rgba(24, 34, 53, 0.96), rgba(14, 21, 34, 0.92));
  --entry-shell-border: rgba(157, 173, 196, 0.18);
  --entry-shell-shadow:
    0 32px 84px rgba(4, 10, 20, 0.44),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  --entry-brand-surface:
    linear-gradient(180deg, rgba(28, 39, 60, 0.68), rgba(20, 29, 45, 0)),
    linear-gradient(160deg, rgba(24, 34, 53, 0.96), rgba(30, 49, 85, 0.78) 58%, rgba(16, 24, 39, 0.96));
  --entry-brand-outline: rgba(125, 160, 255, 0.16);
  --entry-form-column-surface: linear-gradient(180deg, rgba(8, 13, 22, 0.2), rgba(8, 13, 22, 0.48));
  --entry-panel: rgba(24, 34, 53, 0.9);
  --entry-panel-strong: rgba(24, 34, 53, 0.96);
  --entry-panel-border: rgba(157, 173, 196, 0.16);
  --entry-panel-shadow:
    0 22px 44px rgba(4, 10, 20, 0.26),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  --entry-ink: #eef3fb;
  --entry-muted: #b0bccd;
  --entry-topline: #94a3b8;
  --entry-accent: #7da0ff;
  --entry-accent-strong: #93b3ff;
  --entry-accent-contrast: #101827;
  --entry-accent-soft: rgba(125, 160, 255, 0.18);
  --entry-danger: #f4b6af;
  --entry-tab-rail: rgba(255, 255, 255, 0.04);
  --entry-tab-text: #aeb9c9;
  --entry-tab-active-bg: rgba(125, 160, 255, 0.16);
  --entry-tab-active-color: #eef3fb;
  --entry-focus-border: rgba(125, 160, 255, 0.52);
  --entry-input-bg: rgba(15, 24, 39, 0.84);
  --entry-input-border: rgba(157, 173, 196, 0.22);
  --entry-input-focus-bg: rgba(18, 27, 43, 0.96);
  --entry-input-placeholder: #7f8ca1;
  --entry-toggle-ink: #b0bccd;
  --entry-toggle-hover-bg: rgba(125, 160, 255, 0.14);
  --entry-button-bg: #7da0ff;
  --entry-button-hover-bg: #93b3ff;
  --entry-button-text: #101827;
  --entry-button-shadow: 0 18px 40px rgba(4, 10, 20, 0.36);
  --entry-status-success-bg: rgba(33, 129, 92, 0.18);
  --entry-status-success-ink: #c4eadc;
  --entry-status-success-border: rgba(77, 178, 136, 0.22);
  --entry-status-error-bg: rgba(196, 73, 61, 0.16);
  --entry-status-error-ink: #f7cbc6;
  --entry-status-error-border: rgba(196, 73, 61, 0.24);
  --entry-icon-surface: linear-gradient(180deg, rgba(125, 160, 255, 0.14), rgba(255, 255, 255, 0.04));
  --entry-icon-border: rgba(125, 160, 255, 0.18);
  --entry-icon-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 18px 38px rgba(4, 10, 20, 0.24);
  --entry-statement-surface:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02)),
    linear-gradient(135deg, rgba(125, 160, 255, 0.12), rgba(16, 24, 39, 0.04));
  --entry-statement-border: rgba(125, 160, 255, 0.16);
  --entry-statement-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
  --entry-grid-line: rgba(148, 163, 184, 0.1);
  --entry-mesh-one: rgba(59, 76, 108, 0.2);
  --entry-mesh-two: rgba(125, 160, 255, 0.14);
  --entry-orb-one: radial-gradient(circle, rgba(125, 160, 255, 0.22) 0%, rgba(88, 118, 188, 0.12) 34%, rgba(88, 118, 188, 0) 72%);
  --entry-orb-two: radial-gradient(circle, rgba(13, 148, 136, 0.18) 0%, rgba(13, 148, 136, 0.08) 40%, rgba(13, 148, 136, 0) 76%);
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
    radial-gradient(circle at 24% 24%, var(--entry-mesh-one), transparent 28%),
    radial-gradient(circle at 78% 14%, var(--entry-mesh-two), transparent 22%);
  animation: meshDrift 18s ease-in-out infinite;
}

.auth-entry__grid {
  opacity: 0.5;
  background-image:
    linear-gradient(var(--entry-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--entry-grid-line) 1px, transparent 1px);
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
  background: var(--entry-orb-one);
  animation: orbFloatOne 14s ease-in-out infinite;
}

.auth-entry__orb--two {
  right: 5%;
  bottom: 10%;
  width: 360px;
  height: 360px;
  background: var(--entry-orb-two);
  animation: orbFloatTwo 16s ease-in-out infinite;
}

.auth-entry__shell {
  position: relative;
  z-index: 1;
  width: min(1120px, 100%);
  min-height: 700px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 430px);
  border: 1px solid var(--entry-shell-border);
  border-radius: 30px;
  overflow: hidden;
  background: var(--entry-shell-surface);
  box-shadow: var(--entry-shell-shadow);
  backdrop-filter: blur(18px);
  animation: shellReveal 560ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.auth-entry .brand-column,
.auth-entry .form-card {
  opacity: 0;
  animation: contentReveal 480ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.auth-entry .brand-column {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28px;
  padding: 56px;
  background: var(--entry-brand-surface);
}

.auth-entry .brand-column::after {
  content: '';
  position: absolute;
  inset: 20px;
  border-radius: 22px;
  border: 1px solid var(--entry-brand-outline);
  pointer-events: none;
}

.brand-column__topline,
.panel-intro__eyebrow {
  margin: 0;
  color: var(--entry-topline);
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

.auth-entry .brand-lockup__icon-wrap {
  width: 90px;
  height: 90px;
  border-radius: 26px;
  display: grid;
  place-items: center;
  background: var(--entry-icon-surface);
  border: 1px solid var(--entry-icon-border);
  box-shadow: var(--entry-icon-shadow);
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
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
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
  background: var(--entry-statement-surface);
  border: 1px solid var(--entry-statement-border);
  box-shadow: var(--entry-statement-shadow);
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
  background: var(--entry-accent);
  animation: caretBlink 1s steps(1) infinite;
}

.auth-entry .form-column {
  padding: 24px;
  display: flex;
  align-items: stretch;
  background: var(--entry-form-column-surface);
}

.auth-entry .form-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 24px;
  padding: 36px;
  border-radius: 26px;
  border: 1px solid var(--entry-panel-border);
  background: var(--entry-panel-strong);
  box-shadow: var(--entry-panel-shadow);
  animation-delay: 140ms;
}

.auth-entry .tabs {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 6px;
  border-radius: 999px;
  background: var(--entry-tab-rail);
  align-self: flex-start;
}

.auth-entry .tab-btn {
  border: 0;
  border-radius: 999px;
  padding: 10px 18px;
  background: transparent;
  color: var(--entry-tab-text);
  font-size: 0.94rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 180ms ease,
    background-color 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease;
}

.auth-entry .tab-btn.active {
  background: var(--entry-tab-active-bg);
  color: var(--entry-tab-active-color);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.auth-entry .tab-btn:hover:not(:disabled) {
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
    transform 320ms cubic-bezier(0.16, 1, 0.3, 1),
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

.auth-entry .status-box.success {
  background: var(--entry-status-success-bg);
  color: var(--entry-status-success-ink);
  border: 1px solid var(--entry-status-success-border);
}

.auth-entry .status-box.error {
  background: var(--entry-status-error-bg);
  color: var(--entry-status-error-ink);
  border: 1px solid var(--entry-status-error-border);
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
  opacity: 0;
  animation: formGroupReveal 480ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.auth-form .form-group:nth-child(1) { animation-delay: 60ms; }
.auth-form .form-group:nth-child(2) { animation-delay: 120ms; }
.auth-form .form-group:nth-child(3) { animation-delay: 180ms; }
.auth-form .form-group:nth-child(4) { animation-delay: 240ms; }
.auth-form .form-group:nth-child(5) { animation-delay: 300ms; }
.auth-form .primary-button { animation-delay: 360ms; }

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

.auth-entry .form-group input {
  width: 100%;
  border: 1px solid var(--entry-input-border);
  border-radius: 16px;
  padding: 14px 16px;
  background: var(--entry-input-bg);
  color: var(--entry-ink);
  outline: none;
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease,
    transform 180ms ease;
}

.auth-entry .form-group input::placeholder {
  color: var(--entry-input-placeholder);
}

.auth-entry .form-group input:focus {
  border-color: var(--entry-focus-border);
  background: var(--entry-input-focus-bg);
  box-shadow: 0 0 0 4px var(--entry-accent-soft);
  transform: translateY(-1px);
}

.auth-entry .form-group input:-webkit-autofill,
.auth-entry .form-group input:-webkit-autofill:hover,
.auth-entry .form-group input:-webkit-autofill:focus {
  -webkit-box-shadow: 0 0 0 1000px var(--entry-input-bg) inset;
  -webkit-text-fill-color: var(--entry-ink);
  transition: background-color 5000s ease-in-out 0s;
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

.auth-entry .toggle-pwd {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--entry-toggle-ink);
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

.auth-entry .toggle-pwd:hover:not(:disabled) {
  background: var(--entry-toggle-hover-bg);
  color: var(--entry-accent);
}

.auth-entry .toggle-pwd :deep(.app-icon) {
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

.inline-link[href]:hover {
  text-decoration: underline;
}

.inline-link--muted {
  color: var(--entry-accent);
  opacity: 0.7;
  cursor: pointer;
  background: none;
  border: none;
  padding: 0;
  font: inherit;
}

.inline-link--muted:hover {
  opacity: 1;
  text-decoration: underline;
}

.forgot-hint {
  margin: -4px 0 8px;
  font-size: 0.84rem;
  color: var(--entry-muted);
  line-height: 1.5;
}

.back-to-login {
  text-align: center;
  margin-top: 12px;
  opacity: 0;
  animation: formGroupReveal 480ms cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: 200ms;
}

.error-msg {
  color: var(--entry-danger);
  font-size: 0.84rem;
}

.auth-entry .primary-button {
  border: 0;
  border-radius: 8px;
  padding: 15px 20px;
  background: var(--entry-button-bg);
  color: var(--entry-button-text);
  cursor: pointer;
  font-size: 0.98rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  opacity: 0;
  animation: formGroupReveal 480ms cubic-bezier(0.16, 1, 0.3, 1) both;
  transition: transform 180ms ease, box-shadow 180ms ease, background-color 180ms ease;
}

.auth-entry .primary-button:hover:not(:disabled) {
  background: var(--entry-button-hover-bg);
  transform: translateY(-1px);
  box-shadow: var(--entry-button-shadow);
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

@keyframes formGroupReveal {
  from {
    opacity: 0;
    transform: translateY(10px);
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
  .form-group,
  .primary-button,
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
