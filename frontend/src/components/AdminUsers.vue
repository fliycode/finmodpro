<script setup>
import { ref, onMounted, computed } from 'vue';
import { adminApi } from '../api/admin.js';
import { useFlash } from '../lib/flash.js';
import GovernanceReviewDesk from './admin/governance/GovernanceReviewDesk.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from './admin/ops/OpsStatusBand.vue';
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

const reviewQueue = computed(() => filteredUsers.value.slice(0, 6));
const ungroupedCount = computed(() => users.value.filter((user) => user.groups.length === 0).length);
const userStatusItems = computed(() => ([
  {
    key: 'users',
    label: '用户总数',
    value: users.value.length,
    note: '当前纳入管理台的用户记录。',
  },
  {
    key: 'groups',
    label: '角色组',
    value: groups.value.length,
    note: '可分配给用户的角色组数量。',
  },
  {
    key: 'filtered',
    label: '当前筛选',
    value: filteredUsers.value.length,
    note: '搜索与角色过滤后的结果集。',
  },
  {
    key: 'ungrouped',
    label: '待补角色',
    value: ungroupedCount.value,
    note: '尚未分配角色组的用户。',
  },
]));
const frameMeta = computed(() => [
  `筛选结果：${filteredUsers.value.length}`,
  `待补角色：${ungroupedCount.value}`,
]);
const groupDistribution = computed(() => groups.value
  .map((group) => ({
    name: group.name,
    count: users.value.filter((user) => user.groups.includes(group.name)).length,
  }))
  .sort((left, right) => right.count - left.count)
  .slice(0, 6));

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
  <OpsSectionFrame
    eyebrow="Governance / Users"
    title="用户与角色管理"
    summary="把角色分配做成 review surface：先看待处理队列，再审表，再在决策侧确认当前角色覆盖。"
    :meta="frameMeta"
  >
    <template #actions>
      <el-button type="primary" @click="fetchData" :loading="isLoading">刷新数据</el-button>
    </template>

    <template #alerts>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    </template>

    <template #status-band>
      <OpsStatusBand :items="userStatusItems" />
    </template>

    <GovernanceReviewDesk>
      <template #queue>
        <AppSectionCard title="审核队列" desc="优先查看当前筛选范围内最需要处理的用户。" admin>
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

          <div v-if="reviewQueue.length === 0" class="admin-empty-state">当前筛选没有待审用户</div>
          <div v-else class="governance-review-queue">
            <button
              v-for="user in reviewQueue"
              :key="user.id"
              type="button"
              class="governance-review-queue__item"
              @click="openEditDrawer(user)"
            >
              <strong>{{ user.username }}</strong>
              <span>{{ user.email }}</span>
              <span class="muted-text">
                {{ user.groups.length ? user.groups.join(' / ') : '未分配角色组' }}
              </span>
            </button>
          </div>
        </AppSectionCard>
      </template>

      <AppSectionCard title="用户列表" desc="支持按用户名、邮箱和角色组快速筛选，并通过抽屉修改所属角色。" admin>
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

      <template #decision>
        <AppSectionCard title="决策侧栏" desc="先确认角色覆盖，再进入抽屉提交变更。" admin>
          <div class="governance-review-decision">
            <div v-if="selectedUser" class="governance-review-decision__focus">
              <span class="muted-text">当前待处理</span>
              <strong>{{ selectedUser.username }}</strong>
              <p>{{ selectedUser.email }}</p>
              <p class="muted-text">
                {{ selectedUser.groups.length ? selectedUser.groups.join(' / ') : '未分配角色组' }}
              </p>
            </div>

            <div class="governance-review-distribution">
              <article v-for="group in groupDistribution" :key="group.name" class="governance-review-distribution__item">
                <strong>{{ group.name }}</strong>
                <span>{{ group.count }} 人</span>
              </article>
            </div>
          </div>
        </AppSectionCard>
      </template>
    </GovernanceReviewDesk>

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
  </OpsSectionFrame>
</template>

<style scoped>
.governance-review-queue,
.governance-review-distribution {
  display: grid;
  gap: 10px;
}

.governance-review-queue__item {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid rgba(127, 146, 170, 0.18);
  border-radius: 14px;
  background: rgba(15, 23, 34, 0.86);
  color: #f3f6fb;
  text-align: left;
  cursor: pointer;
}

.governance-review-decision {
  display: grid;
  gap: 14px;
}

.governance-review-decision__focus {
  display: grid;
  gap: 6px;
}

.governance-review-distribution__item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid rgba(127, 146, 170, 0.14);
}
</style>
