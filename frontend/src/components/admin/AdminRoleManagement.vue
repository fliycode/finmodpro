<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { ElMessageBox } from 'element-plus';

import { adminApi } from '../../api/admin.js';
import {
  decorateRole,
  getRoleDescription,
  groupPermissionsCatalog,
  roleMatchesQuery,
  sortRolesByPriority,
} from '../../lib/admin-roles.js';
import { useFlash } from '../../lib/flash.js';
import { permissionHelper } from '../../lib/permission.js';
import AppIcon from '../ui/AppIcon.vue';
import AppSectionCard from '../ui/AppSectionCard.vue';

const flash = useFlash();

const roles = ref([]);
const permissions = ref([]);
const selectedRoleId = ref(null);
const selectedRole = ref(null);
const isLoading = ref(false);
const isSaving = ref(false);
const error = ref('');
const filterExpanded = ref(false);

const draftFilters = reactive({
  keyword: '',
  roleType: '',
  customized: '',
});

const appliedFilters = reactive({
  keyword: '',
  roleType: '',
  customized: '',
});

const createDialogVisible = ref(false);
const createForm = reactive({
  name: '',
  permissions: [],
});

const roleDraft = reactive({
  name: '',
  permissions: [],
});

const canManageRoles = computed(() => permissionHelper.hasPermission('assign_role'));
const canRestoreDefaults = computed(() => canManageRoles.value && selectedRole.value?.is_system);
const groupedPermissions = computed(() => groupPermissionsCatalog(permissions.value));

const filteredRoles = computed(() => {
  const sortedRoles = sortRolesByPriority(roles.value);

  return sortedRoles.filter((role) => {
    if (!roleMatchesQuery(role, appliedFilters.keyword)) {
      return false;
    }

    if (appliedFilters.roleType && role.role_type !== appliedFilters.roleType) {
      return false;
    }

    if (appliedFilters.customized === 'customized' && !role.has_customized_permissions) {
      return false;
    }

    if (appliedFilters.customized === 'default' && role.has_customized_permissions) {
      return false;
    }

    return true;
  });
});

const roleRows = computed(() => filteredRoles.value.map((role) => ({
  ...role,
  permissionCount: role.permissions.length,
  defaultCount: role.default_permissions.length,
})));

const currentRoleDescription = computed(() => (
  selectedRole.value ? getRoleDescription(selectedRole.value) : ''
));

const isSelectedRoleDirty = computed(() => {
  if (!selectedRole.value) {
    return false;
  }

  const currentPermissions = [...(selectedRole.value.permissions ?? [])].sort();
  const draftPermissions = [...roleDraft.permissions].sort();

  return roleDraft.name !== selectedRole.value.name
    || JSON.stringify(currentPermissions) !== JSON.stringify(draftPermissions);
});

const syncDraft = (role) => {
  roleDraft.name = role?.name ?? '';
  roleDraft.permissions = [...(role?.permissions ?? [])];
};

const loadRoleDetail = async (roleId, { preserveError = false } = {}) => {
  if (!roleId) {
    selectedRole.value = null;
    syncDraft(null);
    return;
  }

  try {
    const detail = decorateRole(await adminApi.getRole(roleId));
    selectedRole.value = detail;
    syncDraft(detail);

    const index = roles.value.findIndex((role) => role.id === detail.id);
    if (index >= 0) {
      roles.value.splice(index, 1, decorateRole({ ...roles.value[index], ...detail }));
    }

    if (!preserveError) {
      error.value = '';
    }
  } catch (err) {
    error.value = err.message || '加载角色详情失败。';
  }
};

const loadData = async () => {
  isLoading.value = true;
  error.value = '';

  try {
    const [rolesData, permissionsData] = await Promise.all([
      adminApi.listRoles(),
      adminApi.listPermissions(),
    ]);

    roles.value = sortRolesByPriority((rolesData || []).map(decorateRole));
    permissions.value = permissionsData || [];

    const preferredRoleId = roles.value.find((role) => role.id === selectedRoleId.value)?.id
      ?? roles.value[0]?.id
      ?? null;
    selectedRoleId.value = preferredRoleId;
    await loadRoleDetail(preferredRoleId, { preserveError: true });
  } catch (err) {
    error.value = err.message || '加载角色与权限数据失败。';
  } finally {
    isLoading.value = false;
  }
};

watch(filteredRoles, (nextRoles) => {
  if (!nextRoles.length) {
    selectedRoleId.value = null;
    selectedRole.value = null;
    syncDraft(null);
    return;
  }

  if (!nextRoles.some((role) => role.id === selectedRoleId.value)) {
    selectedRoleId.value = nextRoles[0].id;
  }
}, { immediate: true });

watch(selectedRoleId, async (roleId) => {
  if (roleId && roleId !== selectedRole.value?.id) {
    await loadRoleDetail(roleId, { preserveError: true });
  }
});

const applyFilters = () => {
  Object.assign(appliedFilters, draftFilters);
};

const resetFilters = () => {
  Object.assign(draftFilters, {
    keyword: '',
    roleType: '',
    customized: '',
  });
  Object.assign(appliedFilters, {
    keyword: '',
    roleType: '',
    customized: '',
  });
  filterExpanded.value = false;
};

const handleRoleRowClick = (row) => {
  selectedRoleId.value = row.id;
};

const openCreateDialog = () => {
  createForm.name = '';
  createForm.permissions = [];
  createDialogVisible.value = true;
};

const handleCreateRole = async () => {
  isSaving.value = true;
  try {
    const createdRole = decorateRole(await adminApi.createRole({
      name: createForm.name,
      permissions: createForm.permissions,
    }));
    createDialogVisible.value = false;
    flash.success('角色已创建。');
    await loadData();
    selectedRoleId.value = createdRole.id;
    await loadRoleDetail(createdRole.id);
  } catch (err) {
    flash.error(err.message || '创建角色失败。');
  } finally {
    isSaving.value = false;
  }
};

const handleSaveRole = async () => {
  if (!selectedRole.value || !canManageRoles.value || !isSelectedRoleDirty.value) {
    return;
  }

  isSaving.value = true;
  try {
    const payload = {
      permissions: [...roleDraft.permissions],
    };

    if (roleDraft.name !== selectedRole.value.name) {
      payload.name = roleDraft.name;
    }

    const updatedRole = decorateRole(await adminApi.updateRole(selectedRole.value.id, payload));
    flash.success('角色已更新。');

    const index = roles.value.findIndex((role) => role.id === updatedRole.id);
    if (index >= 0) {
      roles.value.splice(index, 1, updatedRole);
      roles.value = sortRolesByPriority(roles.value);
    }

    selectedRoleId.value = updatedRole.id;
    selectedRole.value = updatedRole;
    syncDraft(updatedRole);
  } catch (err) {
    flash.error(err.message || '保存角色失败。');
  } finally {
    isSaving.value = false;
  }
};

const handleDeleteRole = async (roleOverride = null) => {
  const roleTarget = roleOverride ?? selectedRole.value;

  if (!roleTarget || roleTarget.is_system || !canManageRoles.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认删除角色 ${roleTarget.name} 吗？此操作不可撤销。`,
      '删除角色',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch (reason) {
    if (reason === 'cancel' || reason === 'close') {
      return;
    }
    throw reason;
  }

  isSaving.value = true;
  try {
    await adminApi.deleteRole(roleTarget.id);
    flash.success('角色已删除。');
    await loadData();
  } catch (err) {
    flash.error(err.message || '删除角色失败。');
  } finally {
    isSaving.value = false;
  }
};

const handleRestoreDefaults = async () => {
  if (!selectedRole.value || !selectedRole.value.is_system || !canManageRoles.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认将角色 ${selectedRole.value.name} 恢复到系统默认权限吗？`,
      '恢复默认权限',
      {
        confirmButtonText: '恢复默认',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch (reason) {
    if (reason === 'cancel' || reason === 'close') {
      return;
    }
    throw reason;
  }

  isSaving.value = true;
  try {
    const restoredRole = decorateRole(await adminApi.restoreRoleDefaults(selectedRole.value.id));
    flash.success('系统角色已恢复默认权限。');

    const index = roles.value.findIndex((role) => role.id === restoredRole.id);
    if (index >= 0) {
      roles.value.splice(index, 1, restoredRole);
      roles.value = sortRolesByPriority(roles.value);
    }

    selectedRole.value = restoredRole;
    syncDraft(restoredRole);
  } catch (err) {
    flash.error(err.message || '恢复默认失败。');
  } finally {
    isSaving.value = false;
  }
};

onMounted(loadData);
</script>

<template>
  <div class="page-stack roles-page">
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <section class="roles-page__filters">
      <div class="roles-page__filters-grid">
        <label class="roles-page__field roles-page__field--keyword">
          <span>搜索</span>
          <el-input
            v-model="draftFilters.keyword"
            clearable
            placeholder="按角色名称、说明或类型搜索"
            @keyup.enter="applyFilters"
          >
            <template #prefix>
              <AppIcon name="search" />
            </template>
          </el-input>
        </label>

        <label class="roles-page__field">
          <span>角色类型</span>
          <el-select v-model="draftFilters.roleType" clearable placeholder="全部类型">
            <el-option label="系统角色" value="system" />
            <el-option label="自定义角色" value="custom" />
          </el-select>
        </label>

        <label v-if="filterExpanded" class="roles-page__field">
          <span>权限状态</span>
          <el-select v-model="draftFilters.customized" clearable placeholder="全部状态">
            <el-option label="已偏离默认" value="customized" />
            <el-option label="默认基线" value="default" />
          </el-select>
        </label>
      </div>

      <div class="roles-page__filter-actions">
        <el-button text @click="filterExpanded = !filterExpanded">
          {{ filterExpanded ? '收起筛选' : '展开筛选' }}
        </el-button>
        <el-button type="primary" :loading="isLoading" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <AppSectionCard admin class="roles-page__table-card">
      <div class="roles-page__table-toolbar">
        <div class="roles-page__table-toolbar-left">
          <el-button v-if="canManageRoles" type="primary" @click="openCreateDialog">
            <AppIcon name="plus" />
            新增角色
          </el-button>
        </div>

        <div class="roles-page__table-toolbar-right">
          <el-button :loading="isLoading" @click="loadData">
            <AppIcon name="refresh" />
            刷新
          </el-button>
        </div>
      </div>

      <el-table
        :data="roleRows"
        row-key="id"
        size="small"
        highlight-current-row
        :current-row-key="selectedRoleId"
        v-loading="isLoading"
        element-loading-text="加载中..."
        @row-click="handleRoleRowClick"
      >
        <el-table-column prop="name" label="角色名称" min-width="168" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="roles-page__name-cell">
              <strong>{{ row.label }}</strong>
              <small>{{ row.name }}</small>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="role_type" label="类型" min-width="126">
          <template #default="{ row }">
            <span :class="['roles-page__role-badge', row.is_system ? 'is-admin' : 'is-member']">
              <AppIcon :name="row.is_system ? 'shield' : 'user'" />
              {{ row.is_system ? '系统角色' : '自定义角色' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="member_count" label="成员数" width="92" />
        <el-table-column prop="permissionCount" label="权限数" width="92" />
        <el-table-column label="状态" min-width="132">
          <template #default="{ row }">
            <span :class="['roles-page__status-badge', row.has_customized_permissions ? 'is-customized' : 'is-default']">
              <span class="roles-page__status-dot"></span>
              {{ row.has_customized_permissions ? '已偏离默认' : '默认基线' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="108" fixed="right" align="right" header-align="right">
          <template #default="{ row }">
            <div class="roles-page__row-actions">
              <el-tooltip content="查看详情" placement="top">
                <button
                  type="button"
                  class="roles-page__icon-button"
                  @click.stop="handleRoleRowClick(row)"
                >
                  <AppIcon name="eye" />
                </button>
              </el-tooltip>

              <el-tooltip
                v-if="canManageRoles && !row.is_system"
                content="删除"
                placement="top"
              >
                <button
                  type="button"
                  class="roles-page__icon-button roles-page__icon-button--danger"
                  @click.stop="handleDeleteRole(row)"
                >
                  <AppIcon name="trash" />
                </button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <div class="admin-empty-state">当前筛选下没有角色记录</div>
        </template>
      </el-table>
    </AppSectionCard>

    <AppSectionCard
      admin
      class="roles-page__detail-card"
      title="角色详情"
      desc="查看成员、编辑角色标识与权限矩阵。"
    >
      <template #header>
        <div v-if="selectedRole" class="roles-page__detail-actions">
          <el-button
            v-if="canRestoreDefaults"
            :disabled="isSaving"
            @click="handleRestoreDefaults"
          >
            恢复默认
          </el-button>
          <el-button
            v-if="canManageRoles && !selectedRole.is_system"
            type="danger"
            plain
            :disabled="isSaving || selectedRole.member_count > 0"
            @click="handleDeleteRole"
          >
            删除角色
          </el-button>
        </div>
      </template>

      <div v-if="!selectedRole" class="roles-page__empty">
        请选择一个角色查看详情。
      </div>

      <div v-else class="roles-page__detail">
        <div class="roles-page__detail-grid">
          <label class="roles-page__field">
            <span class="roles-page__field-label">角色标识</span>
            <el-input
              v-model="roleDraft.name"
              :disabled="!canManageRoles || selectedRole.is_system || isSaving"
              placeholder="例如 ops_observer"
            />
          </label>

          <label class="roles-page__field">
            <span class="roles-page__field-label">角色说明</span>
            <div class="roles-page__static-field">
              {{ currentRoleDescription }}
            </div>
          </label>
        </div>

        <div class="roles-page__summary-row">
          <span :class="['roles-page__role-badge', selectedRole.is_system ? 'is-admin' : 'is-member']">
            <AppIcon :name="selectedRole.is_system ? 'shield' : 'user'" />
            {{ selectedRole.is_system ? '系统角色' : '自定义角色' }}
          </span>
          <span class="roles-page__summary-chip">成员 {{ selectedRole.member_count }}</span>
          <span class="roles-page__summary-chip">权限 {{ roleDraft.permissions.length }}</span>
          <span class="roles-page__summary-chip">默认 {{ selectedRole.default_permissions.length }}</span>
        </div>

        <section class="roles-page__detail-section">
          <div class="roles-page__section-heading">
            <strong>关联成员</strong>
            <span>删除自定义角色前，需确保没有用户仍绑定它。</span>
          </div>
          <div v-if="selectedRole.assigned_users?.length" class="roles-page__member-list">
            <el-tag
              v-for="member in selectedRole.assigned_users"
              :key="member.id"
              size="small"
            >
              {{ member.username }} · {{ member.email || '未设置邮箱' }}
            </el-tag>
          </div>
          <div v-else class="roles-page__muted-text">当前没有用户绑定这个角色。</div>
        </section>

        <section class="roles-page__detail-section">
          <div class="roles-page__section-heading">
            <strong>权限矩阵</strong>
            <span>按治理域分组，勾选后保存即生效。</span>
          </div>

          <section
            v-for="group in groupedPermissions"
            :key="group.key"
            class="roles-page__permission-group"
          >
            <header class="roles-page__permission-group-header">
              <strong>{{ group.label }}</strong>
              <span>{{ group.items.length }} 项能力</span>
            </header>

            <div class="roles-page__permission-grid">
              <label
                v-for="permission in group.items"
                :key="permission.codename"
                class="roles-page__permission-item"
              >
                <el-checkbox
                  v-model="roleDraft.permissions"
                  :label="permission.codename"
                  :disabled="!canManageRoles || isSaving"
                >
                  <div class="roles-page__permission-copy">
                    <strong>{{ permission.codename }}</strong>
                    <span>{{ permission.name }}</span>
                  </div>
                </el-checkbox>
              </label>
            </div>
          </section>
        </section>

        <div class="roles-page__detail-footer">
          <span v-if="!canManageRoles" class="roles-page__muted-text">
            你当前只有查看权限，不能修改角色配置。
          </span>
          <el-button
            v-else
            type="primary"
            :loading="isSaving"
            :disabled="!isSelectedRoleDirty"
            @click="handleSaveRole"
          >
            保存修改
          </el-button>
        </div>
      </div>
    </AppSectionCard>

    <el-dialog
      v-model="createDialogVisible"
      title="新增角色"
      width="720px"
      class="roles-page__dialog-modal"
      destroy-on-close
    >
      <div class="roles-page__dialog">
        <label class="roles-page__field">
          <span class="roles-page__field-label"><em class="roles-page__required">*</em>角色标识</span>
          <el-input v-model="createForm.name" maxlength="150" />
        </label>

        <section
          v-for="group in groupedPermissions"
          :key="`create-${group.key}`"
          class="roles-page__permission-group"
        >
          <header class="roles-page__permission-group-header">
            <strong>{{ group.label }}</strong>
            <span>{{ group.items.length }} 项能力</span>
          </header>

          <div class="roles-page__permission-grid">
            <label
              v-for="permission in group.items"
              :key="`create-${permission.codename}`"
              class="roles-page__permission-item"
            >
              <el-checkbox
                v-model="createForm.permissions"
                :label="permission.codename"
              >
                <div class="roles-page__permission-copy">
                  <strong>{{ permission.codename }}</strong>
                  <span>{{ permission.name }}</span>
                </div>
              </el-checkbox>
            </label>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="roles-page__dialog-actions">
          <el-button @click="createDialogVisible = false" :disabled="isSaving">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="handleCreateRole">
            创建角色
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.roles-page {
  min-width: 0;
}

.roles-page__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--line-strong);
  border-radius: 20px;
  background: var(--surface-1);
}

.roles-page__filters-grid {
  display: grid;
  flex: 1 1 720px;
  grid-template-columns: minmax(240px, 2.2fr) repeat(2, minmax(160px, 1fr));
  gap: 12px;
}

.roles-page__field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.roles-page__field span {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.roles-page__field-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.roles-page__required {
  color: var(--risk);
  font-style: normal;
}

.roles-page__field--keyword {
  grid-column: span 2;
}

.roles-page__filter-actions,
.roles-page__table-toolbar,
.roles-page__table-toolbar-left,
.roles-page__table-toolbar-right,
.roles-page__detail-actions,
.roles-page__dialog-actions,
.roles-page__summary-row,
.roles-page__detail-footer {
  display: flex;
  align-items: center;
  gap: 10px;
}

.roles-page__filter-actions,
.roles-page__table-toolbar,
.roles-page__detail-footer {
  justify-content: space-between;
}

.roles-page__name-cell,
.roles-page__detail,
.roles-page__dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.roles-page__name-cell strong,
.roles-page__section-heading strong,
.roles-page__permission-copy strong {
  color: var(--text-primary);
}

.roles-page__name-cell small,
.roles-page__section-heading span,
.roles-page__permission-group-header span,
.roles-page__permission-copy span,
.roles-page__muted-text {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.roles-page__status-badge,
.roles-page__role-badge,
.roles-page__summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}

.roles-page__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.roles-page__status-badge.is-default {
  color: var(--success);
  background: var(--success-50);
  border-color: rgba(33, 129, 92, 0.18);
}

.roles-page__status-badge.is-customized {
  color: var(--warning);
  background: var(--warning-50);
  border-color: rgba(183, 121, 31, 0.18);
}

.roles-page__role-badge.is-admin {
  color: var(--brand);
  background: var(--brand-soft);
  border-color: rgba(36, 87, 197, 0.2);
}

.roles-page__role-badge.is-member {
  color: var(--warning);
  background: var(--warning-50);
  border-color: rgba(183, 121, 31, 0.18);
}

.roles-page__summary-chip {
  color: var(--text-secondary);
  background: var(--surface-3);
}

.roles-page__row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.roles-page__icon-button {
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

.roles-page__icon-button:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.roles-page__icon-button--danger:hover {
  color: var(--risk);
}

.roles-page__detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.roles-page__static-field {
  min-height: 36px;
  padding: 10px 12px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: var(--surface-2);
  color: var(--text-secondary);
  line-height: 1.5;
}

.roles-page__detail-section {
  display: grid;
  gap: 12px;
}

.roles-page__section-heading,
.roles-page__permission-group-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.roles-page__member-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.roles-page__permission-group {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.roles-page__permission-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.roles-page__permission-item {
  display: flex;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: var(--surface-1);
}

.roles-page__permission-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.roles-page__empty {
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.roles-page :deep(.admin-section-card) {
  padding: 18px 20px;
  border: 1px solid var(--line-strong);
  border-radius: 24px;
  background: var(--surface-1);
}

.roles-page :deep(.el-input__wrapper),
.roles-page :deep(.el-select__wrapper) {
  min-height: 36px;
  background: var(--surface-2);
  box-shadow: inset 0 0 0 1px var(--line-strong);
  border-radius: 12px;
}

.roles-page :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
}

.roles-page :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.roles-page :deep(.el-table th.el-table__cell) {
  height: 40px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: transparent;
}

.roles-page :deep(.el-table td.el-table__cell) {
  padding-block: 8px;
  border-bottom-color: var(--line-soft);
}

.roles-page :deep(.el-table .cell) {
  min-height: 24px;
  padding-inline: 14px;
}

.roles-page :deep(.el-tag) {
  border-radius: 999px;
}

.roles-page :deep(.el-checkbox) {
  align-items: flex-start;
  width: 100%;
  height: 100%;
  margin-right: 0;
}

.roles-page :deep(.el-checkbox__label) {
  display: block;
  width: 100%;
  min-width: 0;
  padding-left: 10px;
}

.roles-page :deep(.el-dialog) {
  overflow: hidden;
  border: 1px solid var(--line-strong);
  border-radius: 24px;
  background: var(--surface-1);
}

.roles-page :deep(.el-dialog__header),
.roles-page :deep(.el-dialog__footer) {
  padding-inline: 24px;
}

.roles-page :deep(.el-dialog__body) {
  padding: 12px 24px 8px;
}

@media (max-width: 1180px) {
  .roles-page__filters-grid,
  .roles-page__detail-grid,
  .roles-page__permission-grid {
    grid-template-columns: 1fr;
  }

  .roles-page__field--keyword {
    grid-column: span 1;
  }
}

@media (max-width: 900px) {
  .roles-page__filters {
    padding: 16px;
  }

  .roles-page__filters-grid {
    grid-template-columns: 1fr;
  }

  .roles-page__filter-actions,
  .roles-page__table-toolbar,
  .roles-page__detail-footer {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .roles-page__table-toolbar,
  .roles-page__permission-group-header,
  .roles-page__dialog-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .roles-page__filter-actions {
    justify-content: flex-start;
  }
}
</style>
