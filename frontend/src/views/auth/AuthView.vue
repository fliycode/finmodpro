<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { authApi } from '../../api/auth.js';
import { validateAuthForm } from '../../lib/auth-form.js';
import { authStorage } from '../../lib/auth-storage.js';
import { resolveHomeRoute } from '../../lib/session-state.js';

const router = useRouter();

const mode = ref('login');
const loading = ref(false);
const status = ref({ type: '', message: '' });
const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: false,
});

const errors = computed(() => validateAuthForm(mode.value, form));

const resetStatus = () => {
  status.value = { type: '', message: '' };
};

const switchMode = (nextMode) => {
  mode.value = nextMode;
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

  const validationErrors = errors.value;
  if (Object.keys(validationErrors).length > 0 || loading.value) {
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
      <h2>{{ mode === 'login' ? '欢迎回来' : '创建账户' }}</h2>
      <p class="auth-card__hint">
        {{ mode === 'login' ? '请输入账号密码继续访问。' : '注册后将按角色进入对应首页。' }}
      </p>

      <div v-if="status.message" class="auth-card__status" :class="`is-${status.type}`">
        {{ status.message }}
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <label class="auth-form__field">
          <span>用户名</span>
          <input v-model="form.username" type="text" :disabled="loading" placeholder="请输入用户名" />
          <small v-if="errors.username" class="auth-form__error">{{ errors.username }}</small>
        </label>

        <label v-if="mode === 'register'" class="auth-form__field">
          <span>电子邮箱</span>
          <input v-model="form.email" type="email" :disabled="loading" placeholder="name@company.com" />
          <small v-if="errors.email" class="auth-form__error">{{ errors.email }}</small>
        </label>

        <label class="auth-form__field">
          <span>密码</span>
          <input v-model="form.password" type="password" :disabled="loading" placeholder="请输入密码" />
          <small v-if="errors.password" class="auth-form__error">{{ errors.password }}</small>
        </label>

        <label v-if="mode === 'register'" class="auth-form__field">
          <span>确认密码</span>
          <input
            v-model="form.confirmPassword"
            type="password"
            :disabled="loading"
            placeholder="请再次输入密码"
          />
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
          {{ loading ? '提交中...' : mode === 'login' ? '登录' : '注册' }}
        </button>
      </form>
    </div>
  </div>
</template>
