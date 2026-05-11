<script setup>
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import AuthLanding from '../../components/AuthLanding.vue';
import { validateAuthForm } from '../../lib/auth-form.js';
import { authApi } from '../../api/auth.js';
import { authSession } from '../../lib/auth-session.js';
import { authStorage } from '../../lib/auth-storage.js';
import { resolveHomeRoute } from '../../lib/session-state.js';

const router = useRouter();

const activeTab = ref('login');
const showPassword = ref(false);
const isLoading = ref(false);
const resetToken = ref('');
const status = reactive({
  message: '',
  type: '',
});

const formData = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: false,
  rememberMe: false,
});

const errors = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: '',
});

const clearErrors = () => {
  Object.keys(errors).forEach((key) => {
    errors[key] = '';
  });
};

const resetStatus = () => {
  status.message = '';
  status.type = '';
};

const clearForm = () => {
  formData.username = '';
  formData.email = '';
  formData.password = '';
  formData.confirmPassword = '';
  formData.agreeTerms = false;
  formData.rememberMe = false;
};

const switchTab = (tab) => {
  activeTab.value = tab;
  showPassword.value = false;
  clearErrors();
  resetStatus();
  if (tab === 'login' || tab === 'register') {
    clearForm();
    resetToken.value = '';
  }
};

onMounted(() => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (token) {
    resetToken.value = token;
    activeTab.value = 'reset';
    window.history.replaceState({}, '', window.location.pathname);
    return;
  }

  const flashMessage = authStorage.consumeFlashMessage();
  if (flashMessage) {
    status.message = flashMessage;
    status.type = 'error';
  }
});

const submit = async (event) => {
  event.preventDefault();

  if (isLoading.value) {
    return;
  }

  clearErrors();
  resetStatus();

  const validationErrors = validateAuthForm(activeTab.value, formData);
  Object.entries(validationErrors).forEach(([key, value]) => {
    errors[key] = value;
  });

  if (Object.keys(validationErrors).length > 0) {
    return;
  }

  isLoading.value = true;

  try {
    if (activeTab.value === 'login') {
      const { profile } = await authSession.login({
        username: formData.username,
        password: formData.password,
        rememberMe: formData.rememberMe,
      });
      await router.replace(resolveHomeRoute(profile));
      return;
    }

    if (activeTab.value === 'register') {
      await authSession.register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });

      status.message = '注册成功，请使用新账号登录。';
      status.type = 'success';
      activeTab.value = 'login';
      formData.password = '';
      formData.confirmPassword = '';
      return;
    }

    if (activeTab.value === 'forgot') {
      const result = await authApi.forgotPassword({
        username: formData.username,
      });
      resetToken.value = result.reset_token;
      status.message = '重置链接已生成，请在下方设置新密码。';
      status.type = 'success';
      formData.password = '';
      formData.confirmPassword = '';
      activeTab.value = 'reset';
      return;
    }

    if (activeTab.value === 'reset') {
      await authApi.resetPassword({
        token: resetToken.value,
        newPassword: formData.password,
      });
      status.message = '密码已重置，请使用新密码登录。';
      status.type = 'success';
      clearForm();
      resetToken.value = '';
      activeTab.value = 'login';
      return;
    }
  } catch (error) {
    status.type = 'error';

    if (error.name === 'TypeError' && /fetch|network/i.test(error.message)) {
      status.message = '网络连接失败，请检查网络后重试';
    } else if (error.status === 429 || error.statusCode === 429) {
      status.message = '操作过于频繁，请稍后再试';
    } else if (error.status === 401 || error.statusCode === 401) {
      status.message = activeTab.value === 'login'
        ? '用户名或密码错误'
        : '注册失败，请检查输入信息';
    } else {
      status.message = error.message || '操作失败，请重试';
    }
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <AuthLanding
    :active-tab="activeTab"
    :show-password="showPassword"
    :is-loading="isLoading"
    :status="status"
    :form-data="formData"
    :errors="errors"
    @toggle-tab="switchTab"
    @submit="submit"
    @toggle-password="showPassword = !showPassword"
  />
</template>
