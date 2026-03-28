# Frontend Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Admin Dashboard for FinModPro, including user management, role editing, and search/filtering capabilities, integrated with the Django backend.

**Architecture:** Use Vue 3 Composition API with `<script setup>`. Separate API calls into a dedicated module. Use a sub-view approach in `App.vue` for simplicity in this demo project.

**Tech Stack:** Vue 3, Vite, Vanilla CSS.

---

### Task 1: Create Admin API Module

**Files:**
- Create: `src/api/admin.js`

- [ ] **Step 1: Implement `src/api/admin.js`**

```javascript
import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || '请求失败，请稍后重试');
  }
  return data;
};

const getJson = async (config, path) => {
  const token = authStorage.getToken();
  const headers = { ...config.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await config.fetchImpl(joinUrl(config.baseURL, path), {
    method: 'GET',
    headers,
  });
  return parseResponse(response);
};

const putJson = async (config, path, payload) => {
  const token = authStorage.getToken();
  const headers = { ...config.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await config.fetchImpl(joinUrl(config.baseURL, path), {
    method: 'PUT',
    headers,
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
};

export const createAdminApi = (overrides = {}) => {
  const config = createApiConfig(overrides);
  return {
    listUsers() {
      return getJson(config, '/api/admin/users');
    },
    listGroups() {
      return getJson(config, '/api/admin/groups');
    },
    updateUserGroups(userId, groupIds) {
      return putJson(config, `/api/admin/users/${userId}/groups`, {
        groups: groupIds
      });
    }
  };
};

export const adminApi = createAdminApi();
```

- [ ] **Step 2: Commit**

```bash
git add src/api/admin.js
git commit -m "feat(api): add admin api module"
```

### Task 2: Implement Admin Dashboard UI Components

**Files:**
- Create: `src/components/AdminUsers.vue`

- [ ] **Step 1: Create `src/components/AdminUsers.vue` with basic layout and user list**

```vue
<script setup>
import { ref, onMounted, computed } from 'vue';
import { adminApi } from '../api/admin.js';

const users = ref([]);
const groups = ref([]);
const isLoading = ref(false);
const error = ref('');
const searchQuery = ref('');
const filterGroup = ref('');

const selectedUser = ref(null);
const showEditDrawer = ref(false);
const isUpdating = ref(false);

const fetchData = async () => {
  isLoading.value = true;
  error.value = '';
  try {
    const [usersData, groupsData] = await Promise.all([
      adminApi.listUsers(),
      adminApi.listGroups()
    ]);
    users.value = usersData;
    groups.value = groupsData;
  } catch (err) {
    error.value = err.message || '加载数据失败';
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const filteredUsers = computed(() => {
  return users.value.filter(user => {
    const matchesSearch = user.username.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
                         user.email.toLowerCase().includes(searchQuery.value.toLowerCase());
    const matchesGroup = !filterGroup.value || user.groups.some(g => g.name === filterGroup.value);
    return matchesSearch && matchesGroup;
  });
});

const openEditDrawer = (user) => {
  selectedUser.value = JSON.parse(JSON.stringify(user));
  showEditDrawer.value = true;
};

const closeEditDrawer = () => {
  selectedUser.value = null;
  showEditDrawer.value = false;
};

const handleUpdateGroups = async () => {
  if (!selectedUser.value) return;
  isUpdating.value = true;
  try {
    const groupIds = selectedUser.value.groups.map(g => g.id);
    await adminApi.updateUserGroups(selectedUser.value.id, groupIds);
    
    // Local refresh: find and update user in the list
    const index = users.value.findIndex(u => u.id === selectedUser.value.id);
    if (index !== -1) {
      users.value[index].groups = groups.value.filter(g => groupIds.includes(g.id));
    }
    
    closeEditDrawer();
  } catch (err) {
    alert(err.message || '更新失败');
  } finally {
    isUpdating.value = false;
  }
};

const toggleGroupSelection = (groupId) => {
  const index = selectedUser.value.groups.findIndex(g => g.id === groupId);
  if (index === -1) {
    const group = groups.value.find(g => g.id === groupId);
    selectedUser.value.groups.push(group);
  } else {
    selectedUser.value.groups.splice(index, 1);
  }
};

const isGroupSelected = (groupId) => {
  return selectedUser.value.groups.some(g => g.id === groupId);
};
</script>

<template>
  <div class="admin-users">
    <header class="page-header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <div class="search-bar">
          <input type="text" v-model="searchQuery" placeholder="搜索用户名或邮箱..." />
        </div>
        <select v-model="filterGroup" class="filter-select">
          <option value="">所有角色</option>
          <option v-for="g in groups" :key="g.id" :value="g.name">{{ g.name }}</option>
        </select>
        <button @click="fetchData" :disabled="isLoading" class="refresh-btn">刷新</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div class="table-container">
      <table class="user-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>邮箱</th>
            <th>角色组</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in filteredUsers" :key="user.id">
            <td>{{ user.id }}</td>
            <td class="username-cell">{{ user.username }}</td>
            <td>{{ user.email }}</td>
            <td>
              <div class="group-tags">
                <span v-for="g in user.groups" :key="g.id" class="group-tag">{{ g.name }}</span>
                <span v-if="!user.groups.length" class="no-groups">无角色</span>
              </div>
            </td>
            <td>
              <button @click="openEditDrawer(user)" class="edit-btn">编辑角色</button>
            </td>
          </tr>
          <tr v-if="!filteredUsers.length && !isLoading">
            <td colspan="5" class="empty-state">未找到匹配的用户</td>
          </tr>
        </tbody>
      </table>
      <div v-if="isLoading" class="loading-overlay">加载中...</div>
    </div>

    <!-- Edit Drawer -->
    <div v-if="showEditDrawer" class="drawer-backdrop" @click.self="closeEditDrawer">
      <div class="edit-drawer">
        <header class="drawer-header">
          <h3>编辑用户角色: {{ selectedUser?.username }}</h3>
          <button @click="closeEditDrawer" class="close-btn">&times;</button>
        </header>
        <div class="drawer-content">
          <p>请选择该用户所属的角色组：</p>
          <div class="groups-selection">
            <div 
              v-for="g in groups" 
              :key="g.id" 
              class="group-item" 
              :class="{ selected: isGroupSelected(g.id) }"
              @click="toggleGroupSelection(g.id)"
            >
              <div class="checkbox">{{ isGroupSelected(g.id) ? '✓' : '' }}</div>
              <div class="group-info">
                <span class="group-name">{{ g.name }}</span>
              </div>
            </div>
          </div>
        </div>
        <footer class="drawer-footer">
          <button @click="closeEditDrawer" :disabled="isUpdating" class="cancel-btn">取消</button>
          <button @click="handleUpdateGroups" :disabled="isUpdating" class="save-btn">
            {{ isUpdating ? '保存中...' : '保存更改' }}
          </button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-users {
  padding: 24px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.search-bar input {
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  width: 240px;
}

.filter-select {
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.refresh-btn {
  padding: 8px 16px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
}

.table-container {
  position: relative;
  overflow-x: auto;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
}

.user-table th {
  text-align: left;
  padding: 12px;
  background: #f8fafc;
  border-bottom: 2px solid #e2e8f0;
  font-weight: 600;
  color: #475569;
}

.user-table td {
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.username-cell {
  font-weight: 600;
  color: #1e293b;
}

.group-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.group-tag {
  background: #e0e7ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.no-groups {
  color: #94a3b8;
  font-size: 12px;
  font-style: italic;
}

.edit-btn {
  background: #6366f1;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.edit-btn:hover {
  background: #4f46e5;
}

.error-banner {
  background: #fef2f2;
  color: #991b1b;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 24px;
}

.empty-state {
  text-align: center;
  padding: 48px;
  color: #64748b;
}

/* Drawer Styles */
.drawer-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}

.edit-drawer {
  width: 400px;
  background: white;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 15px rgba(0,0,0,0.1);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-header {
  padding: 20px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #64748b;
}

.drawer-content {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.groups-selection {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.group-item:hover {
  border-color: #6366f1;
  background: #f5f3ff;
}

.group-item.selected {
  border-color: #6366f1;
  background: #f5f3ff;
}

.checkbox {
  width: 20px;
  height: 20px;
  border: 2px solid #cbd5e1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
}

.selected .checkbox {
  background: #6366f1;
  border-color: #6366f1;
}

.drawer-footer {
  padding: 20px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 12px;
}

.cancel-btn {
  flex: 1;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: white;
  cursor: pointer;
}

.save-btn {
  flex: 2;
  padding: 10px;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.save-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/components/AdminUsers.vue
git commit -m "feat(ui): implement user management dashboard component"
```

### Task 3: Update `src/App.vue` for Navigation

**Files:**
- Modify: `src/App.vue`

- [ ] **Step 1: Update `src/App.vue` with view switching logic and Admin Dashboard entry**

```vue
<script setup>
// ... existing imports
import AdminUsers from './components/AdminUsers.vue'; // Add this

const currentView = ref('auth'); // 'auth' or 'admin'

// ... existing state and methods

const navigateToAdmin = () => {
  if (isAdmin.value) {
    currentView.value = 'admin';
  }
};

const backToHome = () => {
  currentView.value = 'auth';
};

// ...
</script>

<template>
  <div class="app-wrapper">
    <!-- Admin View -->
    <div v-if="currentView === 'admin' && isAdmin" class="admin-container">
      <nav class="admin-nav">
        <div class="nav-brand" @click="backToHome">
          <svg viewBox="0 0 24 24" fill="none" class="w-6 h-6">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>FinModPro Admin</span>
        </div>
        <div class="nav-user">
          <span>{{ currentUser.user.username }}</span>
          <button @click="backToHome" class="back-link">返回主页</button>
        </div>
      </nav>
      <main class="admin-main">
        <AdminUsers />
      </main>
    </div>

    <!-- Auth View (Original content) -->
    <div v-else class="auth-container">
      <!-- ... existing content ... -->
      <!-- Update the "管理后台" button to use navigateToAdmin -->
      <button class="demo-btn" :disabled="!isAdmin" @click="navigateToAdmin">
        <span v-if="!isAdmin" class="lock-icon">🔒</span>
        管理后台
      </button>
      <!-- ... -->
    </div>
  </div>
</template>

<style scoped>
/* Add these styles */
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

.back-link {
  background: transparent;
  border: 1px solid #cbd5e1;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
}

.admin-main {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
/* ... existing styles ... */
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/App.vue src/components/AdminUsers.vue
git commit -m "feat(ui): integrate admin dashboard navigation in App.vue"
```

### Task 4: Documentation and Build Verification

**Files:**
- Modify: `FRONTEND_PROGRESS.md`

- [ ] **Step 1: Update `FRONTEND_PROGRESS.md`**

Add a new section for Admin Demo.

- [ ] **Step 2: Run build**

Run: `npm run build`
Expected: Success

- [ ] **Step 3: Final Commit**

```bash
git add FRONTEND_PROGRESS.md
git commit -m "docs: update progress and verify build"
```
