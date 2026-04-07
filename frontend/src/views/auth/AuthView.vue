<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { authApi } from '../../api/auth.js';
import { validateAuthForm } from '../../lib/auth-form.js';
import { authStorage } from '../../lib/auth-storage.js';
import { resolveHomeRoute } from '../../lib/session-state.js';

const userIcon = '◉';
const mailIcon = '✉';
const lockIcon = '◆';

const router = useRouter();

const mode = ref('login');
const loading = ref(false);
const status = ref({ type: '', message: '' });
const passwordVisible = ref(false);
const confirmPasswordVisible = ref(false);
const submitted = ref(false);
const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: false,
});

const validationErrors = computed(() => validateAuthForm(mode.value, form));
const errors = computed(() => (submitted.value ? validationErrors.value : {}));

const resetStatus = () => {
  status.value = { type: '', message: '' };
};

const switchMode = (nextMode) => {
  mode.value = nextMode;
  submitted.value = false;
  passwordVisible.value = false;
  confirmPasswordVisible.value = false;
  resetStatus();
};

onMounted(() => {
  const flashMessage = authStorage.consumeFlashMessage();
  if (flashMessage) {
    status.value = { type: 'error', message: flashMessage };
  }
});

const submit = async () => {
  resetStatus();
  submitted.value = true;

  const currentValidationErrors = validationErrors.value;
  if (Object.keys(currentValidationErrors).length > 0 || loading.value) {
    return;
  }

  loading.value = true;

  try {
    if (mode.value === 'login') {
      const response = await authApi.login({
        username: form.username,
        password: form.password,
      });

      if (response.access_token) {
        authStorage.saveToken(response.access_token);
      }

      const profile = await authApi.me();
      authStorage.saveProfile(profile);
      await router.replace(resolveHomeRoute(profile));
      return;
    }

    await authApi.register({
      username: form.username,
      email: form.email,
      password: form.password,
    });

    status.value = { type: 'success', message: '注册成功，请使用新账号登录。' };
    mode.value = 'login';
    submitted.value = false;
    form.password = '';
    form.confirmPassword = '';
  } catch (error) {
    status.value = { type: 'error', message: error.message || '操作失败，请重试' };
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="auth-card">
    <div class="auth-card__tabs">
      <button
        type="button"
        class="auth-card__tab"
        :class="{ 'is-active': mode === 'login' }"
        :disabled="loading"
        @click="switchMode('login')"
      >
        登录
      </button>
      <button
        type="button"
        class="auth-card__tab"
        :class="{ 'is-active': mode === 'register' }"
        :disabled="loading"
        @click="switchMode('register')"
      >
        注册
      </button>
    </div>

    <div class="auth-card__body">
      <div class="auth-card__heading">
        <p class="auth-card__eyebrow">FinModPro</p>
      </div>

      <div v-if="status.message" class="auth-card__status" :class="`is-${status.type}`">
        {{ status.message }}
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <label class="auth-form__field">
          <span>用户名</span>
          <div class="auth-form__control">
            <span class="auth-form__icon" aria-hidden="true">{{ userIcon }}</span>
            <input v-model="form.username" type="text" :disabled="loading" placeholder="请输入用户名" />
          </div>
          <small v-if="errors.username" class="auth-form__error">{{ errors.username }}</small>
        </label>

        <label v-if="mode === 'register'" class="auth-form__field">
          <span>电子邮箱</span>
          <div class="auth-form__control">
            <span class="auth-form__icon" aria-hidden="true">{{ mailIcon }}</span>
            <input v-model="form.email" type="email" :disabled="loading" placeholder="name@company.com" />
          </div>
          <small v-if="errors.email" class="auth-form__error">{{ errors.email }}</small>
        </label>

        <label class="auth-form__field">
          <span>密码</span>
          <div class="auth-form__control auth-form__control--password">
            <span class="auth-form__icon" aria-hidden="true">{{ lockIcon }}</span>
            <input
              v-model="form.password"
              :type="passwordVisible ? 'text' : 'password'"
              :disabled="loading"
              placeholder="请输入密码"
            />
            <button
              type="button"
              class="auth-form__toggle"
              :disabled="loading"
              @click="passwordVisible = !passwordVisible"
            >
              {{ passwordVisible ? '隐藏' : '显示' }}
            </button>
          </div>
          <small v-if="errors.password" class="auth-form__error">{{ errors.password }}</small>
        </label>

        <label v-if="mode === 'register'" class="auth-form__field">
          <span>确认密码</span>
          <div class="auth-form__control auth-form__control--password">
            <span class="auth-form__icon" aria-hidden="true">{{ lockIcon }}</span>
            <input
              v-model="form.confirmPassword"
              :type="confirmPasswordVisible ? 'text' : 'password'"
              :disabled="loading"
              placeholder="请再次输入密码"
            />
            <button
              type="button"
              class="auth-form__toggle"
              :disabled="loading"
              @click="confirmPasswordVisible = !confirmPasswordVisible"
            >
              {{ confirmPasswordVisible ? '隐藏' : '显示' }}
            </button>
          </div>
          <small v-if="errors.confirmPassword" class="auth-form__error">{{ errors.confirmPassword }}</small>
        </label>

        <label v-if="mode === 'register'" class="auth-form__checkbox">
          <input v-model="form.agreeTerms" type="checkbox" :disabled="loading" />
          <span>我同意服务条款和隐私政策</span>
        </label>
        <small v-if="mode === 'register' && errors.agreeTerms" class="auth-form__error">
          {{ errors.agreeTerms }}
        </small>

        <button class="auth-form__submit" type="submit" :disabled="loading">
          {{ loading ? '提交中...' : mode === 'login' ? '进入工作台' : '创建并继续' }}
        </button>
      
        <div class="auth-card__footnote" />
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-card {
  width: min(100%, 480px);
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-soft);
  overflow: hidden;
}

.auth-card__tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 8px;
  gap: 8px;
  background: var(--surface-3);
  border-bottom: 1px solid var(--line-soft);
}

.auth-card__tab {
  border: 1px solid transparent;
  border-radius: 16px;
  padding: 13px 16px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.auth-card__tab.is-active {
  background: var(--surface-2);
  border-color: var(--line-soft);
  color: var(--text-primary);
}

.auth-card__body {
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.auth-card__heading {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  padding-bottom: 4px;
}

.auth-card__eyebrow {
  color: var(--brand);
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.auth-card__status {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 14px;
}

.auth-card__status.is-success {
  background: rgba(33, 129, 92, 0.1);
  color: var(--success);
}

.auth-card__status.is-error {
  background: rgba(196, 73, 61, 0.1);
  color: var(--risk);
}

.auth-card__footnote {
  display: none;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.auth-form__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.auth-form__control {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--line-strong);
  border-radius: 16px;
  padding: 0 14px;
  background: var(--surface-2);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.auth-form__control:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 4px rgba(36, 87, 197, 0.12);
}

.auth-form__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  color: var(--text-muted);
  font-size: 13px;
  flex-shrink: 0;
}

.auth-form__field input {
  width: 100%;
  border: 0;
  padding: 13px 0;
  font-size: 15px;
  color: var(--text-primary);
  background: transparent;
}

.auth-form__field input:focus {
  outline: none;
}

.auth-form__field input:focus-visible,
.auth-card__tab:focus-visible,
.auth-form__submit:focus-visible,
.auth-form__toggle:focus-visible {
  outline: 3px solid rgba(36, 87, 197, 0.22);
  outline-offset: 2px;
}

.auth-form__control--password {
  padding-right: 8px;
}

.auth-form__toggle {
  border: 0;
  background: transparent;
  color: var(--brand);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  padding: 8px 10px;
  border-radius: 10px;
}

.auth-form__toggle:hover {
  background: var(--brand-soft);
}

.auth-form__checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 14px;
}

.auth-form__error {
  color: var(--risk);
  font-size: 13px;
  font-weight: 500;
}

.auth-form__submit {
  border: 0;
  border-radius: 16px;
  padding: 15px 18px;
  background: var(--brand);
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 0.18s ease;
}

.auth-form__submit:hover:not(:disabled) {
  background: #1d469d;
}

.auth-form__submit:disabled,
.auth-card__tab:disabled,
.auth-form__toggle:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
