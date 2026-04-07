<script setup>
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { authApi } from '../../api/auth.js';
import AuthLanding from '../../components/AuthLanding.vue';
import { validateAuthForm } from '../../lib/auth-form.js';
import { authStorage } from '../../lib/auth-storage.js';
import { resolveHomeRoute } from '../../lib/session-state.js';

const router = useRouter();

const activeTab = ref('login');
const showPassword = ref(false);
const isLoading = ref(false);
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

const switchTab = (tab) => {
  activeTab.value = tab;
  showPassword.value = false;
  clearErrors();
  resetStatus();
};

onMounted(() => {
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
      const response = await authApi.login({
        username: formData.username,
        password: formData.password,
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
      username: formData.username,
      email: formData.email,
      password: formData.password,
    });

    status.message = '注册成功，请使用新账号登录。';
    status.type = 'success';
    activeTab.value = 'login';
    formData.password = '';
    formData.confirmPassword = '';
  } catch (error) {
    status.message = error.message || '操作失败，请重试';
    status.type = 'error';
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
