<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { authApi } from './api/auth.js';
import { authStorage } from './lib/auth-storage.js';
import { permissionHelper } from './lib/permission.js';
import AdminUsers from './components/AdminUsers.vue';
import Workbench from './components/Workbench.vue';
import AuthLanding from './components/AuthLanding.vue';
import AuthenticatedHome from './components/AuthenticatedHome.vue';

const activeTab = ref('login');
const showPassword = ref(false);
const isLoading = ref(false);
const currentView = ref('auth'); // 'auth', 'admin', or 'workbench'
const status = reactive({
  message: '',
  type: '' // 'success' or 'error'
});

const currentUser = reactive({
  isLoggedIn: false,
  user: {},
  groups: [],
  permissions: []
});

const formData = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: false
});

const errors = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: ''
});

const loadProfile = async () => {
  const token = authStorage.getToken();
  if (token) {
    try {
      const profile = await authApi.me();
      authStorage.saveProfile(profile);
      updateUserFromStorage();
    } catch (err) {
      console.error('Failed to load profile:', err);
      authStorage.clear();
      updateUserFromStorage();
    }
  }
};

const updateUserFromStorage = () => {
  const profile = authStorage.getProfile();
  currentUser.user = profile.user;
  currentUser.groups = profile.groups;
  currentUser.permissions = profile.permissions;
  currentUser.isLoggedIn = !!authStorage.getToken();
};

onMounted(() => {
  updateUserFromStorage();
  if (currentUser.isLoggedIn) {
    loadProfile();
  }
});

const toggleTab = (tab) => {
  activeTab.value = tab;
  Object.keys(errors).forEach(key => errors[key] = '');
  status.message = '';
  status.type = '';
};

const handleLogout = () => {
  authStorage.clear();
  updateUserFromStorage();
  currentView.value = 'auth';
  status.message = '已退出登录';
  status.type = 'success';
};

const navigateToAdmin = () => {
  if (isAdmin.value) {
    currentView.value = 'admin';
  }
};

const navigateToWorkbench = () => {
  currentView.value = 'workbench';
};

const backToHome = () => {
  currentView.value = currentUser.isLoggedIn ? 'auth' : 'auth';
};

const validateEmail = (email) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

const validate = () => {
  let isValid = true;
  Object.keys(errors).forEach(key => errors[key] = '');
  status.message = '';

  if (activeTab.value === 'register') {
    if (!formData.username.trim()) {
      errors.username = '用户名必填';
      isValid = false;
    }
    if (!formData.email.trim()) {
      errors.email = '电子邮箱必填';
      isValid = false;
    } else if (!validateEmail(formData.email)) {
      errors.email = '电子邮箱格式不正确';
      isValid = false;
    }
    if (!formData.password) {
      errors.password = '密码必填';
      isValid = false;
    } else if (formData.password.length < 8) {
      errors.password = '密码长度至少为8位';
      isValid = false;
    }
    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = '两次输入的密码不一致';
      isValid = false;
    }
    if (!formData.agreeTerms) {
      errors.agreeTerms = '您必须同意服务条款和隐私政策';
      isValid = false;
    }
  } else {
    if (!formData.username.trim()) {
      errors.username = '用户名必填';
      isValid = false;
    }
    if (!formData.password) {
      errors.password = '密码必填';
      isValid = false;
    }
  }

  return isValid;
};

const handleSubmit = async (e) => {
  e.preventDefault();
  if (isLoading.value) return;

  if (validate()) {
    isLoading.value = true;
    status.message = '';

    try {
      let response;
      if (activeTab.value === 'login') {
        response = await authApi.login({
          username: formData.username,
          password: formData.password
        });

        if (response.access_token) {
          authStorage.saveToken(response.access_token);
        }

        await loadProfile();

        status.message = '登录成功！已加载权限信息';
      } else {
        response = await authApi.register({
          username: formData.username,
          email: formData.email,
          password: formData.password
        });
        status.message = '注册成功！请登录';
        activeTab.value = 'login';
      }

      status.type = 'success';
      console.log('API Response:', response);
    } catch (err) {
      status.message = err.message || '操作失败，请重试';
      status.type = 'error';
    } finally {
      isLoading.value = false;
    }
  }
};

const isAdmin = computed(() => permissionHelper.isAdmin());
</script>

<template>
  <div class="app-root">
    <!-- Workbench View -->
    <div v-if="currentView === 'workbench'" class="workbench-wrapper">
      <Workbench :user="currentUser" @back="backToHome" />
    </div>

    <!-- Admin View -->
    <div v-else-if="currentView === 'admin' && isAdmin" class="admin-container">
      <nav class="admin-nav">
        <div class="nav-brand" @click="backToHome">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="nav-brand__icon">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>FinModPro Admin</span>
        </div>
        <div class="nav-user">
          <span class="nav-user__name">{{ currentUser.user.username }}</span>
          <button @click="backToHome" class="nav-back-btn">返回主页</button>
        </div>
      </nav>
      <main class="admin-main">
        <AdminUsers />
      </main>
    </div>

    <!-- Auth View: not logged in → AuthLanding; logged in → AuthenticatedHome -->
    <template v-else>
      <AuthenticatedHome
        v-if="currentUser.isLoggedIn"
        :currentUser="currentUser"
        :isAdmin="isAdmin"
        @navigate-admin="navigateToAdmin"
        @logout="handleLogout"
        @enter-workbench="navigateToWorkbench"
      />
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
    </template>
  </div>
</template>

<style scoped>
.app-root {
  min-height: 100vh;
  width: 100%;
}

.workbench-wrapper {
  width: 100%;
  min-height: 100vh;
}

/* Admin View */
.admin-container {
  min-height: 100vh;
  background-color: #f1f5f9;
}

.admin-nav {
  height: 64px;
  background: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 16px;
  cursor: pointer;
  color: #4f46e5;
  transition: opacity 0.2s;
}

.nav-brand:hover {
  opacity: 0.8;
}

.nav-brand__icon {
  width: 28px;
  height: 28px;
  color: #4f46e5;
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
  color: #475569;
}

.nav-user__name {
  font-weight: 600;
  color: #1e293b;
}

.nav-back-btn {
  background: transparent;
  border: 1px solid #cbd5e1;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  transition: all 0.2s;
}

.nav-back-btn:hover {
  background: #f8fafc;
  border-color: #4f46e5;
  color: #4f46e5;
}

.admin-main {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
</style>
