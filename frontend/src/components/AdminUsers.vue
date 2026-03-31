<script setup>
import { ref, onMounted, computed } from 'vue';
import { adminApi } from '../api/admin.js';
import { useFlash } from '../lib/flash.js';

const users = ref([]);
const groups = ref([]);
const isLoading = ref(false);
const error = ref('');
const searchQuery = ref('');
const filterGroup = ref('');

const selectedUser = ref(null);
const showEditDrawer = ref(false);
const isUpdating = ref(false);
const flash = useFlash();

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
    const usernameMatch = user.username.toLowerCase().includes(searchQuery.value.toLowerCase());
    const emailMatch = user.email.toLowerCase().includes(searchQuery.value.toLowerCase());
    const matchesSearch = usernameMatch || emailMatch;
    
    const matchesGroup = !filterGroup.value || user.groups.includes(filterGroup.value);
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
    const groupNames = [...selectedUser.value.groups];
    await adminApi.updateUserGroups(selectedUser.value.id, groupNames);
    
    // Local refresh: find and update user in the list
    const index = users.value.findIndex(u => u.id === selectedUser.value.id);
    if (index !== -1) {
      users.value[index].groups = groupNames;
    }
    
    closeEditDrawer();
  } catch (err) {
    flash.error(err.message || '更新失败');
  } finally {
    isUpdating.value = false;
  }
};

const toggleGroupSelection = (groupName) => {
  const index = selectedUser.value.groups.indexOf(groupName);
  if (index === -1) {
    selectedUser.value.groups.push(groupName);
  } else {
    selectedUser.value.groups.splice(index, 1);
  }
};

const isGroupSelected = (groupName) => {
  return selectedUser.value && selectedUser.value.groups.includes(groupName);
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
                <span v-for="groupName in user.groups" :key="groupName" class="group-tag">{{ groupName }}</span>
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
              :class="{ selected: isGroupSelected(g.name) }"
              @click="toggleGroupSelection(g.name)"
            >
              <div class="checkbox">{{ isGroupSelected(g.name) ? '✓' : '' }}</div>
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

.loading-overlay {
  text-align: center;
  padding: 24px;
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
