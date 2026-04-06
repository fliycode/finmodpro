<script setup>
import { ref, onMounted, computed } from 'vue';
import { adminApi } from '../api/admin.js';
import { useFlash } from '../lib/flash.js';
import AppSectionCard from './ui/AppSectionCard.vue';
import AppToolbar from './ui/AppToolbar.vue';

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

const normalizeUsers = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.users)) return payload.users;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
};

const normalizeGroups = (payload) => {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.groups)
      ? payload.groups
      : Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.results)
          ? payload.results
          : Array.isArray(payload?.data)
            ? payload.data
            : [];

  return list.map((group, index) => {
    if (typeof group === 'string') {
      return { id: group, name: group };
    }
    return {
      id: group.id ?? group.name ?? index,
      name: group.name ?? group.group_name ?? String(group.id ?? index),
    };
  });
};

const normalizeUserRecord = (user, index) => ({
  id: user.id ?? user.user_id ?? index,
  username: user.username ?? user.name ?? user.email ?? `user-${index}`,
  email: user.email ?? user.mail ?? '--',
  groups: Array.isArray(user.groups)
    ? user.groups.map((group) => (typeof group === 'string' ? group : group.name ?? group.group_name ?? String(group.id ?? ''))).filter(Boolean)
    : Array.isArray(user.roles)
      ? user.roles.map((role) => (typeof role === 'string' ? role : role.name ?? String(role.id ?? ''))).filter(Boolean)
      : [],
  raw: user,
});

const fetchData = async () => {
  isLoading.value = true;
  error.value = '';
  try {
    const [usersData, groupsData] = await Promise.all([
      adminApi.listUsers(),
      adminApi.listGroups()
    ]);
    users.value = normalizeUsers(usersData).map(normalizeUserRecord);
    groups.value = normalizeGroups(groupsData);
  } catch (err) {
    error.value = err.message || '加载数据失败';
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const filteredUsers = computed(() => {
  return users.value.filter((user) => {
    const keyword = searchQuery.value.toLowerCase();
    const usernameMatch = user.username.toLowerCase().includes(keyword);
    const emailMatch = user.email.toLowerCase().includes(keyword);
    const matchesSearch = usernameMatch || emailMatch;

    const matchesGroup = !filterGroup.value || user.groups.includes(filterGroup.value);
    return matchesSearch && matchesGroup;
  });
});

const openEditDrawer = (user) => {
  if (!user) return;
  selectedUser.value = {
    ...JSON.parse(JSON.stringify(user)),
    groups: Array.isArray(user.groups) ? [...user.groups] : [],
  };
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

    const index = users.value.findIndex((u) => u.id === selectedUser.value.id);
    if (index !== -1) {
      users.value[index].groups = groupNames;
    }

    flash.success('用户角色已更新');
    closeEditDrawer();
  } catch (err) {
    flash.error(err.message || '更新失败');
  } finally {
    isUpdating.value = false;
  }
};
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">Admin / Users</div>
        <h1 class="page-hero__title">用户与角色管理</h1>
        <p class="page-hero__subtitle">
          后台统一采用标准化筛选、表格和抽屉编辑交互，减少后续权限和用户管理的重复 UI 维护成本。
        </p>
      </div>
      <el-button type="primary" @click="fetchData" :loading="isLoading">刷新数据</el-button>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <AppSectionCard title="用户列表" desc="支持按用户名、邮箱和角色组快速筛选，并通过抽屉修改所属角色。" admin>
      <AppToolbar>
        <el-form :inline="true" class="admin-form-row">
          <el-form-item>
            <el-input v-model="searchQuery" placeholder="搜索用户名或邮箱..." clearable />
          </el-form-item>
          <el-form-item>
            <el-select v-model="filterGroup" placeholder="所有角色" clearable>
              <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.name" />
            </el-select>
          </el-form-item>
        </el-form>
      </AppToolbar>

      <el-table :data="filteredUsers" stripe style="width: 100%" v-loading="isLoading">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column label="角色组" min-width="220">
          <template #default="scope">
            <div v-if="scope && scope.row && scope.row.groups && scope.row.groups.length" class="tag-list">
              <el-tag v-for="groupName in scope.row.groups" :key="groupName" size="small">{{ groupName }}</el-tag>
            </div>
            <span v-else class="muted-text">无角色</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="scope">
            <el-button type="primary" plain size="small" @click="openEditDrawer(scope && scope.row ? scope.row : null)">编辑角色</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="admin-empty-state">未找到匹配的用户</div>
        </template>
      </el-table>
    </AppSectionCard>

    <el-drawer v-model="showEditDrawer" size="420px" :with-header="true" destroy-on-close>
      <template #header>
        <div class="section-heading">
          <h3 class="section-heading__title">编辑用户角色</h3>
          <div class="section-heading__desc">{{ selectedUser?.username || '未选择用户' }}</div>
        </div>
      </template>

      <div v-if="selectedUser" class="status-stack">
        <p class="muted-text">请选择该用户所属的角色组：</p>
        <el-checkbox-group v-model="selectedUser.groups">
          <div class="status-stack">
            <el-checkbox v-for="g in groups" :key="g.id" :value="g.name" :label="g.name">
              {{ g.name }}
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </div>

      <template #footer>
        <div class="inline-actions">
          <el-button @click="closeEditDrawer" :disabled="isUpdating">取消</el-button>
          <el-button type="primary" @click="handleUpdateGroups" :loading="isUpdating">保存更改</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>
