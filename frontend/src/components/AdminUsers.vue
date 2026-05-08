<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { ElMessageBox } from 'element-plus';

import { adminApi } from '../api/admin.js';
import { authStorage } from '../lib/auth-storage.js';
import { useFlash } from '../lib/flash.js';
import { permissionHelper } from '../lib/permission.js';
import AppIcon from './ui/AppIcon.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const flash = useFlash();

const users = ref([]);
const groups = ref([]);
const isLoading = ref(false);
const isSaving = ref(false);
const error = ref('');

const filterExpanded = ref(false);
const draftFilters = reactive({
  keyword: '',
  group: '',
  userId: '',
  accountType: '',
  groupStatus: '',
});
const appliedFilters = reactive({
  keyword: '',
  group: '',
  userId: '',
  accountType: '',
  groupStatus: '',
});

const pagination = reactive({
  page: 1,
  pageSize: 10,
});

const sortState = reactive({
  prop: 'id',
  order: 'ascending',
});

const dialogVisible = ref(false);
const dialogMode = ref('create');
const userForm = reactive({
  id: null,
  username: '',
  email: '',
  password: '',
  groups: [],
});

const currentProfile = computed(() => authStorage.getProfile());
const currentUserId = computed(() => currentProfile.value?.user?.id ?? null);

const canCreateUser = computed(() => permissionHelper.hasPermission('add_user'));
const canChangeUser = computed(() => permissionHelper.hasPermission('change_user'));
const canDeleteUser = computed(() => permissionHelper.hasPermission('delete_user'));
const canAssignRole = computed(() => permissionHelper.hasPermission('assign_role'));
const hasRowActions = computed(() => canChangeUser.value || canAssignRole.value || canDeleteUser.value);

const columns = ref([
  { key: 'id', label: 'ID', prop: 'id', width: 72, minWidth: 72, sortable: true, visible: true },
  { key: 'username', label: '用户名', prop: 'username', minWidth: 132, sortable: true, visible: true },
  { key: 'email', label: '邮箱', prop: 'email', minWidth: 220, sortable: true, visible: true },
  { key: 'groups', label: '角色组', prop: 'groups', minWidth: 180, sortable: true, visible: true },
  { key: 'accountType', label: '身份', prop: 'accountType', minWidth: 110, sortable: true, visible: true },
  { key: 'joinedAt', label: '创建时间', prop: 'joinedAt', minWidth: 146, sortable: true, visible: true },
  { key: 'actions', label: '操作', prop: 'actions', width: 104, minWidth: 104, visible: true },
]);

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

const formatJoinedAt = (value) => {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
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
  isStaff: Boolean(user.is_staff),
  isSuperuser: Boolean(user.is_superuser),
  joinedAt: formatJoinedAt(user.date_joined),
  joinedAtRaw: user.date_joined ?? '',
  raw: user,
});

const accountTypeValue = (user) => {
  if (user.isSuperuser) return 'super_admin';
  if (user.isStaff) return 'admin';
  return 'member';
};

const accountTypeLabel = (user) => {
  if (user.isSuperuser) return '超级管理员';
  if (user.isStaff) return '管理员';
  return '普通用户';
};

const groupStatusValue = (user) => (user.groups.length ? 'assigned' : 'missing');

const availableGroups = computed(() => groups.value.map((group) => group.name));

const orderedColumns = computed(() => columns.value.filter((column) => {
  if (column.key === 'actions' && !hasRowActions.value) {
    return false;
  }
  return column.visible;
}));

const columnControls = computed(() => columns.value.filter((column) => (
  column.key !== 'actions' || hasRowActions.value
)));

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新增用户' : '编辑用户'));

const fetchData = async () => {
  isLoading.value = true;
  error.value = '';
  try {
    const [usersData, groupsData] = await Promise.all([
      adminApi.listUsers(),
      adminApi.listGroups(),
    ]);
    users.value = normalizeUsers(usersData).map(normalizeUserRecord);
    groups.value = normalizeGroups(groupsData);
  } catch (err) {
    error.value = err.message || '加载用户数据失败。';
  } finally {
    isLoading.value = false;
  }
};

const applyFilters = () => {
  Object.assign(appliedFilters, draftFilters);
  pagination.page = 1;
};

const resetFilters = () => {
  Object.assign(draftFilters, {
    keyword: '',
    group: '',
    userId: '',
    accountType: '',
    groupStatus: '',
  });
  Object.assign(appliedFilters, {
    keyword: '',
    group: '',
    userId: '',
    accountType: '',
    groupStatus: '',
  });
  filterExpanded.value = false;
  pagination.page = 1;
};

const filteredUsers = computed(() => {
  const keyword = appliedFilters.keyword.trim().toLowerCase();
  const group = appliedFilters.group;
  const userId = appliedFilters.userId.trim();
  const accountType = appliedFilters.accountType;
  const groupStatus = appliedFilters.groupStatus;

  return users.value.filter((user) => {
    const haystack = [
      String(user.id),
      user.username,
      user.email,
      user.groups.join(' '),
      accountTypeLabel(user),
    ].join(' ').toLowerCase();

    if (keyword && !haystack.includes(keyword)) {
      return false;
    }
    if (group && !user.groups.includes(group)) {
      return false;
    }
    if (userId && !String(user.id).includes(userId)) {
      return false;
    }
    if (accountType && accountTypeValue(user) !== accountType) {
      return false;
    }
    if (groupStatus && groupStatusValue(user) !== groupStatus) {
      return false;
    }

    return true;
  });
});

const getSortValue = (user, prop) => {
  if (prop === 'groups') return user.groups.join(' / ');
  if (prop === 'accountType') return accountTypeLabel(user);
  if (prop === 'joinedAt') return user.joinedAtRaw;
  return user[prop];
};

const sortedUsers = computed(() => {
  const rows = [...filteredUsers.value];
  if (!sortState.prop || !sortState.order) {
    return rows;
  }

  const direction = sortState.order === 'descending' ? -1 : 1;
  return rows.sort((left, right) => {
    const leftValue = getSortValue(left, sortState.prop);
    const rightValue = getSortValue(right, sortState.prop);

    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * direction;
    }

    return String(leftValue ?? '').localeCompare(String(rightValue ?? ''), 'zh-CN', {
      numeric: true,
      sensitivity: 'base',
    }) * direction;
  });
});

const pagedUsers = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize;
  return sortedUsers.value.slice(start, start + pagination.pageSize);
});

const totalUsers = computed(() => filteredUsers.value.length);

watch(totalUsers, (nextTotal) => {
  const maxPage = Math.max(1, Math.ceil(nextTotal / pagination.pageSize));
  if (pagination.page > maxPage) {
    pagination.page = maxPage;
  }
});

const handleSortChange = ({ prop, order }) => {
  sortState.prop = prop || 'id';
  sortState.order = order || 'ascending';
};

const handlePageChange = (page) => {
  pagination.page = page;
};

const moveColumn = (columnKey, delta) => {
  const index = columns.value.findIndex((column) => column.key === columnKey);
  const targetIndex = index + delta;
  if (index === -1 || targetIndex < 0 || targetIndex >= columns.value.length) {
    return;
  }

  const nextColumns = [...columns.value];
  const [column] = nextColumns.splice(index, 1);
  nextColumns.splice(targetIndex, 0, column);
  columns.value = nextColumns;
};

const getDefaultGroups = () => {
  if (availableGroups.value.includes('member')) {
    return ['member'];
  }
  return availableGroups.value[0] ? [availableGroups.value[0]] : [];
};

const resetUserForm = () => {
  userForm.id = null;
  userForm.username = '';
  userForm.email = '';
  userForm.password = '';
  userForm.groups = canAssignRole.value ? getDefaultGroups() : [];
};

const openCreateDialog = () => {
  dialogMode.value = 'create';
  resetUserForm();
  dialogVisible.value = true;
};

const openEditDialog = (user) => {
  dialogMode.value = 'edit';
  userForm.id = user.id;
  userForm.username = user.username;
  userForm.email = user.email === '--' ? '' : user.email;
  userForm.password = '';
  userForm.groups = canAssignRole.value ? [...user.groups] : [];
  dialogVisible.value = true;
};

const closeDialog = () => {
  dialogVisible.value = false;
};

const validateUserForm = () => {
  if (!userForm.username.trim() || !userForm.email.trim()) {
    flash.error('请填写用户名和邮箱。');
    return false;
  }

  if (dialogMode.value === 'create' && !userForm.password.trim()) {
    flash.error('新增用户时必须填写初始密码。');
    return false;
  }

  if (canAssignRole.value && userForm.groups.length === 0) {
    flash.error('请至少选择一个角色组。');
    return false;
  }

  return true;
};

const buildUserPayload = () => {
  const payload = {
    username: userForm.username.trim(),
    email: userForm.email.trim(),
    password: userForm.password.trim(),
  };

  if (canAssignRole.value) {
    payload.groups = [...userForm.groups];
  }

  return payload;
};

const handleSubmit = async () => {
  if (!validateUserForm()) {
    return;
  }

  isSaving.value = true;
  error.value = '';
  try {
    const payload = buildUserPayload();
    if (dialogMode.value === 'create') {
      await adminApi.createUser(payload);
      flash.success('用户已创建。');
    } else {
      await adminApi.updateUser(userForm.id, payload);
      flash.success('用户已更新。');
    }
    closeDialog();
    await fetchData();
  } catch (err) {
    error.value = err.message || '保存用户失败。';
  } finally {
    isSaving.value = false;
  }
};

const handleDelete = async (user) => {
  if (user.id === currentUserId.value) {
    flash.error('不能删除当前登录用户。');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认删除用户 ${user.username} 吗？此操作不可撤销。`,
      '删除用户',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch {
    return;
  }

  isLoading.value = true;
  error.value = '';
  try {
    await adminApi.deleteUser(user.id);
    flash.success('用户已删除。');
    await fetchData();
  } catch (err) {
    error.value = err.message || '删除用户失败。';
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);
</script>

<template>
  <div class="page-stack users-page">
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <section class="users-page__filters">
      <div class="users-page__filters-grid">
        <label class="users-page__field users-page__field--keyword">
          <span>搜索</span>
          <el-input
            v-model="draftFilters.keyword"
            clearable
            placeholder="按 ID、用户名、邮箱、角色组搜索"
            @keyup.enter="applyFilters"
          >
            <template #prefix>
              <AppIcon name="search" />
            </template>
          </el-input>
        </label>

        <label class="users-page__field">
          <span>角色组</span>
          <el-select v-model="draftFilters.group" clearable placeholder="全部角色组">
            <el-option
              v-for="group in groups"
              :key="group.id"
              :label="group.name"
              :value="group.name"
            />
          </el-select>
        </label>

        <label v-if="filterExpanded" class="users-page__field">
          <span>用户 ID</span>
          <el-input
            v-model="draftFilters.userId"
            clearable
            placeholder="按 ID 查询"
            @keyup.enter="applyFilters"
          />
        </label>

        <label v-if="filterExpanded" class="users-page__field">
          <span>身份</span>
          <el-select v-model="draftFilters.accountType" clearable placeholder="全部身份">
            <el-option label="超级管理员" value="super_admin" />
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="member" />
          </el-select>
        </label>

        <label v-if="filterExpanded" class="users-page__field">
          <span>角色状态</span>
          <el-select v-model="draftFilters.groupStatus" clearable placeholder="全部状态">
            <el-option label="已分配角色" value="assigned" />
            <el-option label="未分配角色" value="missing" />
          </el-select>
        </label>
      </div>

      <div class="users-page__filter-actions">
        <el-button text @click="filterExpanded = !filterExpanded">
          {{ filterExpanded ? '收起筛选' : '展开筛选' }}
        </el-button>
        <el-button type="primary" :loading="isLoading" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <AppSectionCard admin>
      <div class="users-page__table-toolbar">
        <div class="users-page__table-toolbar-left">
          <el-button v-if="canCreateUser" type="primary" @click="openCreateDialog">
            <AppIcon name="plus" />
            新增用户
          </el-button>
        </div>

        <div class="users-page__table-toolbar-right">
          <el-popover placement="bottom-end" :width="280" trigger="click">
            <template #reference>
              <el-button>
                列排序
              </el-button>
            </template>

            <div class="users-page__column-list">
              <div
                v-for="(column, index) in columnControls"
                :key="column.key"
                class="users-page__column-item"
              >
                <el-checkbox v-model="column.visible" :disabled="column.key === 'actions'">
                  {{ column.label }}
                </el-checkbox>

                <div class="users-page__column-order">
                  <el-button text :disabled="index === 0" @click="moveColumn(column.key, -1)">
                    上移
                  </el-button>
                  <el-button
                    text
                    :disabled="index === columnControls.length - 1"
                    @click="moveColumn(column.key, 1)"
                  >
                    下移
                  </el-button>
                </div>
              </div>
            </div>
          </el-popover>
        </div>
      </div>

      <el-table
        :data="pagedUsers"
        row-key="id"
        size="small"
        :default-sort="{ prop: sortState.prop, order: sortState.order }"
        v-loading="isLoading"
        element-loading-text="加载中..."
        @sort-change="handleSortChange"
      >
        <el-table-column
          v-for="column in orderedColumns"
          :key="column.key"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :sortable="column.sortable ? 'custom' : false"
          :fixed="column.key === 'actions' ? 'right' : false"
          :show-overflow-tooltip="column.key !== 'actions'"
        >
          <template #default="{ row }">
            <template v-if="column.key === 'groups'">
              <div v-if="row.groups.length" class="users-page__group-list">
                <el-tag v-for="groupName in row.groups" :key="groupName" size="small">
                  {{ groupName }}
                </el-tag>
              </div>
              <span v-else class="muted-text">未分配</span>
            </template>

            <template v-else-if="column.key === 'accountType'">
              <span>{{ accountTypeLabel(row) }}</span>
            </template>

            <template v-else-if="column.key === 'actions'">
              <div class="users-page__row-actions">
                <el-tooltip
                  v-if="canChangeUser || canAssignRole"
                  content="编辑"
                  placement="top"
                >
                  <button
                    type="button"
                    class="users-page__icon-button"
                    @click="openEditDialog(row)"
                  >
                    <AppIcon name="edit" />
                  </button>
                </el-tooltip>

                <el-tooltip
                  v-if="canDeleteUser && row.id !== currentUserId"
                  content="删除"
                  placement="top"
                >
                  <button
                    type="button"
                    class="users-page__icon-button users-page__icon-button--danger"
                    @click="handleDelete(row)"
                  >
                    <AppIcon name="trash" />
                  </button>
                </el-tooltip>
              </div>
            </template>

            <template v-else>
              {{ row[column.prop] }}
            </template>
          </template>
        </el-table-column>

        <template #empty>
          <div class="admin-empty-state">当前筛选下没有用户记录</div>
        </template>
      </el-table>

      <div class="users-page__pagination">
        <el-pagination
          small
          background
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="totalUsers"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </AppSectionCard>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      destroy-on-close
    >
      <div class="users-page__dialog">
        <label class="users-page__field">
          <span>用户名</span>
          <el-input v-model="userForm.username" maxlength="150" />
        </label>

        <label class="users-page__field">
          <span>邮箱</span>
          <el-input v-model="userForm.email" type="email" maxlength="254" />
        </label>

        <label class="users-page__field">
          <span>{{ dialogMode === 'create' ? '初始密码' : '重置密码' }}</span>
          <el-input
            v-model="userForm.password"
            type="password"
            show-password
            :placeholder="dialogMode === 'create' ? '请输入初始密码' : '留空则不修改密码'"
          />
        </label>

        <label v-if="canAssignRole" class="users-page__field">
          <span>角色组</span>
          <el-select v-model="userForm.groups" multiple collapse-tags collapse-tags-tooltip>
            <el-option
              v-for="group in groups"
              :key="group.id"
              :label="group.name"
              :value="group.name"
            />
          </el-select>
        </label>
      </div>

      <template #footer>
        <div class="users-page__dialog-actions">
          <el-button @click="closeDialog" :disabled="isSaving">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="handleSubmit">
            {{ dialogMode === 'create' ? '创建用户' : '保存修改' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.users-page {
  min-width: 0;
}

.users-page__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-1);
}

.users-page__filters-grid {
  display: grid;
  flex: 1 1 720px;
  grid-template-columns: minmax(240px, 2.2fr) repeat(2, minmax(160px, 1fr));
  gap: 12px;
}

.users-page__field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.users-page__field span {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.users-page__field--keyword {
  grid-column: span 2;
}

.users-page__filter-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.users-page__table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.users-page__table-toolbar-left,
.users-page__table-toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.users-page__column-list {
  display: grid;
  gap: 10px;
}

.users-page__column-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.users-page__column-order {
  display: flex;
  align-items: center;
  gap: 4px;
}

.users-page__group-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.users-page__row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.users-page__icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.users-page__icon-button:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.users-page__icon-button--danger:hover {
  color: var(--risk);
}

.users-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 6px;
}

.users-page__dialog {
  display: grid;
  gap: 14px;
}

.users-page__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.users-page :deep(.el-input__wrapper),
.users-page :deep(.el-select__wrapper) {
  min-height: 36px;
}

.users-page :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 0;
}

.users-page :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.users-page :deep(.el-table th.el-table__cell) {
  height: 40px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: transparent;
}

.users-page :deep(.el-table td.el-table__cell) {
  padding-block: 8px;
}

.users-page :deep(.el-tag) {
  border-radius: 999px;
}

@media (max-width: 1180px) {
  .users-page__filters-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .users-page__field--keyword {
    grid-column: span 2;
  }
}

@media (max-width: 900px) {
  .users-page__filters {
    padding: 16px;
  }

  .users-page__filters-grid {
    grid-template-columns: 1fr;
  }

  .users-page__field--keyword {
    grid-column: span 1;
  }

  .users-page__filter-actions,
  .users-page__table-toolbar {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .users-page__table-toolbar,
  .users-page__column-item {
    flex-direction: column;
    align-items: stretch;
  }

  .users-page__column-order,
  .users-page__filter-actions,
  .users-page__dialog-actions {
    justify-content: flex-start;
  }
}
</style>
