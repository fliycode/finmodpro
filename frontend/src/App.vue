<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { authApi } from './api/auth.js';
import { authStorage } from './lib/auth-storage.js';
import { permissionHelper } from './lib/permission.js';
import AdminUsers from './components/AdminUsers.vue';
import Workbench from './components/Workbench.vue';

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
  // Clear errors and status when switching tabs
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
  currentView.value = 'auth';
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
    // Login validation
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
        
        // Store token immediately to allow me() call
        if (response.access_token) {
          authStorage.saveToken(response.access_token);
        }

        // Fetch profile
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
  <div class="app-wrapper">
    <!-- Workbench View -->
    <div v-if="currentView === 'workbench'" class="workbench-wrapper">
      <Workbench :user="currentUser" @back="backToHome" />
    </div>

    <!-- Admin View -->
    <div v-if="currentView === 'admin' && isAdmin" class="admin-container">
      <nav class="admin-nav">
        <div class="nav-brand" @click="backToHome">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="w-8 h-8">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>FinModPro Admin</span>
        </div>
        <div class="nav-user">
          <span class="username">{{ currentUser.user.username }}</span>
          <button @click="backToHome" class="back-link">返回主页</button>
        </div>
      </nav>
      <main class="admin-main">
        <AdminUsers />
      </main>
    </div>

    <!-- Auth View -->
    <div v-else class="auth-container">
      <div class="auth-card">
        <!-- Left side: Selling Points -->
        <div class="brand-section">
          <div class="brand-content">
            <div class="logo-placeholder">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="w-12 h-12">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <h1>FinModPro</h1>
            </div>
            <p class="tagline">智能财务建模，助力精准决策</p>
            
            <ul class="selling-points">
              <li>
                <div class="point-icon">✓</div>
                <div class="point-text">
                  <h3>专业模板</h3>
                  <p>内置数十种行业标准财务模型，即插即用。</p>
                </div>
              </li>
              <li>
                <div class="point-icon">✓</div>
                <div class="point-text">
                  <h3>实时协作</h3>
                  <p>与团队成员实时共享数据，同步更新模型。</p>
                </div>
              </li>
              <li>
                <div class="point-icon">✓</div>
                <div class="point-text">
                  <h3>动态分析</h3>
                  <p>支持多种场景假设分析，快速洞察风险与机遇。</p>
                </div>
              </li>
            </ul>

            <!-- RBAC Status Demo -->
            <div v-if="currentUser.isLoggedIn" class="rbac-status-demo">
              <div class="demo-title">当前权限摘要 (RBAC)</div>
              <div class="profile-brief">
                <p><strong>用户:</strong> {{ currentUser.user.username }}</p>
                <p><strong>角色:</strong> {{ currentUser.groups.join(', ') || '无' }}</p>
                <div class="permissions-list">
                  <strong>权限:</strong>
                  <div class="tags">
                    <span v-for="p in currentUser.permissions" :key="p" class="tag">{{ p }}</span>
                  </div>
                </div>
              </div>
              
              <div class="demo-actions">
                <button class="demo-btn" :disabled="!isAdmin" @click="navigateToAdmin">
                  <span v-if="!isAdmin" class="lock-icon">🔒</span>
                  管理后台
                </button>
                <button @click="handleLogout" class="logout-btn">退出登录</button>
              </div>
              <p v-if="!isAdmin" class="demo-tip">注：管理后台仅对 admin/super_admin 角色开放</p>
            </div>
          </div>
          <div class="brand-footer">
            © 2026 FinModPro. All rights reserved.
          </div>
        </div>

        <!-- Right side: Auth Form -->
        <div class="form-section">
          <div v-if="!currentUser.isLoggedIn">
            <div class="tabs">
              <button 
                type="button"
                :class="['tab-btn', { active: activeTab === 'login' }]" 
                @click="toggleTab('login')"
                :disabled="isLoading"
              >
                登录
              </button>
              <button 
                type="button"
                :class="['tab-btn', { active: activeTab === 'register' }]" 
                @click="toggleTab('register')"
                :disabled="isLoading"
              >
                注册
              </button>
            </div>

            <div class="form-container">
              <h2 class="form-title">{{ activeTab === 'login' ? '欢迎回来' : '开启您的财务建模之旅' }}</h2>
              <p class="form-subtitle">
                {{ activeTab === 'login' ? '请输入您的凭据以访问您的帐户' : '只需几步，即可开始高效建模' }}
              </p>

              <!-- Feedback message -->
              <div v-if="status.message" :class="['status-box', status.type]">
                {{ status.message }}
              </div>

              <form @submit="handleSubmit" class="auth-form" novalidate>
                <!-- Username (Login & Registration) -->
                <div class="form-group">
                  <label for="username">用户名</label>
                  <input 
                    type="text" 
                    id="username" 
                    v-model="formData.username"
                    :placeholder="activeTab === 'register' ? '您的称呼' : '请输入用户名'" 
                    :class="{ 'input-error': errors.username }"
                    :disabled="isLoading"
                  />
                  <span class="error-msg" v-if="errors.username">{{ errors.username }}</span>
                </div>

                <!-- Email (Registration only) -->
                <div class="form-group" v-if="activeTab === 'register'">
                  <label for="email">电子邮箱</label>
                  <input 
                    type="email" 
                    id="email" 
                    v-model="formData.email"
                    placeholder="name@company.com" 
                    :class="{ 'input-error': errors.email }"
                    :disabled="isLoading"
                  />
                  <span class="error-msg" v-if="errors.email">{{ errors.email }}</span>
                </div>

                <!-- Password -->
                <div class="form-group">
                  <div class="label-row">
                    <label for="password">密码</label>
                    <a href="#" class="forgot-link" v-if="activeTab === 'login'">忘记密码？</a>
                  </div>
                  <div class="password-input-wrapper">
                    <input 
                      :type="showPassword ? 'text' : 'password'" 
                      id="password" 
                      v-model="formData.password"
                      placeholder="••••••••" 
                      :class="{ 'input-error': errors.password }"
                      :disabled="isLoading"
                    />
                    <button type="button" class="toggle-pwd" @click="showPassword = !showPassword" :disabled="isLoading">
                      {{ showPassword ? '隐藏' : '显示' }}
                    </button>
                  </div>
                  <span class="error-msg" v-if="errors.password">{{ errors.password }}</span>
                </div>

                <!-- Confirm Password (Registration only) -->
                <div class="form-group" v-if="activeTab === 'register'">
                  <label for="confirmPassword">确认密码</label>
                  <div class="password-input-wrapper">
                    <input 
                      :type="showPassword ? 'text' : 'password'" 
                      id="confirmPassword" 
                      v-model="formData.confirmPassword"
                      placeholder="••••••••" 
                      :class="{ 'input-error': errors.confirmPassword }"
                      :disabled="isLoading"
                    />
                  </div>
                  <span class="error-msg" v-if="errors.confirmPassword">{{ errors.confirmPassword }}</span>
                </div>

                <!-- Agree to Terms (Registration only) -->
                <div class="form-group checkbox-group" v-if="activeTab === 'register'">
                  <label class="checkbox-label">
                    <input type="checkbox" v-model="formData.agreeTerms" :disabled="isLoading" />
                    <span>我同意 <a href="#">服务条款</a> 和 <a href="#">隐私政策</a></span>
                  </label>
                  <span class="error-msg" v-if="errors.agreeTerms">{{ errors.agreeTerms }}</span>
                </div>

                <button type="submit" class="submit-btn" :disabled="isLoading">
                  <span v-if="isLoading" class="loader"></span>
                  <span v-else>{{ activeTab === 'login' ? '登录' : '创建账户' }}</span>
                </button>
              </form>

              <div class="divider">
                <span>或者使用以下方式</span>
              </div>

              <div class="social-auth">
                <button class="social-btn" :disabled="isLoading">
                  <svg viewBox="0 0 24 24" class="social-icon">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                  </svg>
                  <span>Google</span>
                </button>
                <button class="social-btn" :disabled="isLoading">
                  <svg viewBox="0 0 24 24" class="social-icon" fill="currentColor">
                    <path d="M12 1.27a11 11 0 00-3.48 21.46c.55.09.73-.24.73-.53v-1.84c-3.03.66-3.67-1.46-3.67-1.46-.5-1.26-1.21-1.6-1.21-1.6-1-.68.07-.66.07-.66 1.1.07 1.68 1.13 1.68 1.13.98 1.68 2.58 1.2 3.21.92.1-.7.38-1.2.69-1.47-2.42-.28-4.97-1.21-4.97-5.39 0-1.19.43-2.17 1.13-2.93-.11-.27-.49-1.39.1-2.89 0 0 .91-.29 2.99 1.12a10.37 10.37 0 015.5 0c2.07-1.41 2.98-1.12 2.98-1.12.6 1.5.22 2.62.11 2.89.7.76 1.13 1.74 1.13 2.93 0 4.2-2.55 5.1-4.98 5.37.39.33.74.99.74 2v2.97c0 .29.18.62.74.52A11 11 0 0012 1.27z"/>
                  </svg>
                  <span>GitHub</span>
                </button>
              </div>
            </div>
          </div>
          <!-- Logged in state for form section -->
          <div v-else class="welcome-back-section">
            <div v-if="status.message" :class="['status-box', status.type]">
              {{ status.message }}
            </div>
            <h2 class="form-title">您已成功登录</h2>
            <p class="form-subtitle">欢迎回来，{{ currentUser.user.username }}！您现在可以访问系统功能。</p>
            
            <div class="welcome-card">
              <div class="welcome-icon">🚀</div>
              <p>基于您的角色 <strong>{{ currentUser.groups[0] || '用户' }}</strong>，您已解锁对应权限。</p>
              <button @click="currentView = 'workbench'" class="submit-btn" style="width: 100%; margin-top: 16px;">进入工作台</button>
            </div>
            
            <button @click="handleLogout" class="social-btn" style="margin-top: 24px; width: 100%;">
              切换账号
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Admin View Styles */
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
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 700;
  cursor: pointer;
  color: #6366f1;
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
  color: #475569;
}

.username {
  font-weight: 600;
}

.back-link {
  background: transparent;
  border: 1px solid #cbd5e1;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.back-link:hover {
  background: #f8fafc;
  border-color: #6366f1;
  color: #6366f1;
}

.admin-main {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

/* RBAC Demo Styles */
.rbac-status-demo {
  margin-top: 40px;
  background: rgba(255, 255, 255, 0.1);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.demo-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: rgba(255, 255, 255, 0.9);
}

.profile-brief {
  font-size: 14px;
  color: white;
}

.profile-brief p {
  margin: 4px 0;
}

.permissions-list {
  margin-top: 12px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.tag {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.demo-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.demo-btn {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 6px;
  background: white;
  color: #6366f1;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.demo-btn:disabled {
  background: rgba(255, 255, 255, 0.4);
  color: rgba(0, 0, 0, 0.4);
  cursor: not-allowed;
}

.logout-btn {
  padding: 8px 12px;
  background: transparent;
  border: 1px solid white;
  color: white;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.demo-tip {
  font-size: 11px;
  margin-top: 10px;
  opacity: 0.8;
  font-style: italic;
}

.welcome-back-section {
  display: flex;
  flex-direction: column;
  height: 100%;
  justify-content: center;
}

.welcome-card {
  background: #f1f5f9;
  padding: 24px;
  border-radius: 12px;
  text-align: center;
  margin-top: 16px;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

/* Original Styles */
.status-box {
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 24px;
  font-size: 14px;
  font-weight: 500;
  text-align: center;
}

.status-box.success {
  background-color: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.status-box.error {
  background-color: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 48px;
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loader {
  width: 20px;
  height: 20px;
  border: 2px solid #ffffff;
  border-bottom-color: transparent;
  border-radius: 50%;
  display: inline-block;
  box-sizing: border-box;
  animation: rotation 1s linear infinite;
}

@keyframes rotation {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8fafc;
  padding: 20px;
  font-family: var(--sans);
}

.auth-card {
  display: flex;
  width: 100%;
  max-width: 1000px;
  background: white;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

/* Brand Section */
.brand-section {
  flex: 1;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  color: white;
  padding: 48px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.logo-placeholder {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.logo-placeholder h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  color: white;
  letter-spacing: -0.5px;
}

.tagline {
  font-size: 18px;
  opacity: 0.9;
  margin-bottom: 48px;
}

.selling-points {
  list-style: none;
  padding: 0;
  margin: 0;
}

.selling-points li {
  display: flex;
  gap: 16px;
  margin-bottom: 32px;
}

.point-icon {
  width: 24px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.point-text h3 {
  font-size: 18px;
  margin: 0 0 4px 0;
  color: white;
}

.point-text p {
  font-size: 14px;
  opacity: 0.8;
  line-height: 1.5;
}

.brand-footer {
  font-size: 12px;
  opacity: 0.7;
}

/* Form Section */
.form-section {
  flex: 1;
  padding: 48px;
  background: white;
  display: flex;
  flex-direction: column;
}

.tabs {
  display: flex;
  gap: 8px;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 10px;
  margin-bottom: 32px;
}

.tab-btn {
  flex: 1;
  padding: 10px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: white;
  color: #6366f1;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.tab-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
}

.form-subtitle {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 32px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-group label {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.forgot-link {
  font-size: 13px;
  color: #6366f1;
  text-decoration: none;
}

.forgot-link:hover {
  text-decoration: underline;
}

input[type="text"],
input[type="email"],
input[type="password"] {
  padding: 12px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 15px;
  transition: all 0.2s;
}

input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

input.input-error {
  border-color: #ef4444;
}

input.input-error:focus {
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
}

input:disabled {
  background-color: #f8fafc;
  color: #94a3b8;
  cursor: not-allowed;
}

.error-msg {
  font-size: 12px;
  color: #ef4444;
}

.password-input-wrapper {
  position: relative;
  display: flex;
}

.password-input-wrapper input {
  width: 100%;
}

.toggle-pwd {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.checkbox-group {
  margin-top: 4px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
}

.checkbox-label input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.checkbox-label a {
  color: #6366f1;
  text-decoration: none;
}

.submit-btn {
  margin-top: 8px;
  padding: 12px;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.submit-btn:hover:not(:disabled) {
  background: #4f46e5;
}

.divider {
  display: flex;
  align-items: center;
  margin: 24px 0;
  color: #cbd5e1;
}

.divider::before,
.divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}

.divider span {
  padding: 0 16px;
  font-size: 12px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.social-auth {
  display: flex;
  gap: 12px;
}

.social-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  background: white;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: background 0.2s;
}

.social-btn:hover:not(:disabled) {
  background: #f8fafc;
}

.social-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.social-icon {
  width: 20px;
  height: 20px;
}

/* Responsive */
@media (max-width: 900px) {
  .brand-section {
    display: none;
  }
  .auth-card {
    max-width: 500px;
  }
}

@media (max-width: 480px) {
  .auth-container {
    padding: 0;
  }
  .auth-card {
    border-radius: 0;
    height: 100vh;
    box-shadow: none;
  }
  .form-section {
    padding: 32px 20px;
  }
}
</style>

