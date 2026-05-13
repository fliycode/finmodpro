<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { ElMessageBox } from 'element-plus';

import { adminApi } from '../../api/admin.js';
import {
  buildPermissionTreeOptions,
  decorateRole,
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
const roleDialogVisible = ref(false);
const rolePermissionTreeRef = ref(null);
const createForm = reactive({
  name: '',
  permissions: [],
});

const roleDraft = reactive({
  permissions: [],
});

const canManageRoles = computed(() => permissionHelper.hasPermission('assign_role'));
const groupedPermissions = computed(() => groupPermissionsCatalog(permissions.value));
const permissionTreeOptions = computed(() => buildPermissionTreeOptions(groupedPermissions.value));

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
})));

const isSelectedRoleDirty = computed(() => {
  if (!selectedRole.value) {
    return false;
  }

  const currentPermissions = [...(selectedRole.value.permissions ?? [])].sort();
  const draftPermissions = [...roleDraft.permissions].sort();

  return JSON.stringify(currentPermissions) !== JSON.stringify(draftPermissions);
});

const syncDraft = (role) => {
  roleDraft.permissions = [...(role?.permissions ?? [])];
};

const syncRolePermissionTree = async () => {
  await nextTick();
  rolePermissionTreeRef.value?.setCheckedKeys(roleDraft.permissions);
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
    if (roleDialogVisible.value) {
      await syncRolePermissionTree();
    }

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

    const preferredRoleId = roles.value.find((role) => role.id === selectedRoleId.value)?.id ?? null;
    selectedRoleId.value = preferredRoleId;

    if (roleDialogVisible.value && preferredRoleId) {
      await loadRoleDetail(preferredRoleId, { preserveError: true });
    } else if (!preferredRoleId) {
      selectedRole.value = null;
      syncDraft(null);
    }
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
    roleDialogVisible.value = false;
    syncDraft(null);
    return;
  }

  if (!nextRoles.some((role) => role.id === selectedRoleId.value)) {
    selectedRoleId.value = null;
  }
}, { immediate: true });

const openRoleDialog = async (roleId) => {
  selectedRoleId.value = roleId;
  await loadRoleDetail(roleId);
  if (selectedRole.value?.id === roleId) {
    roleDialogVisible.value = true;
    await syncRolePermissionTree();
  }
};

const handleRolePermissionTreeCheck = () => {
  roleDraft.permissions = rolePermissionTreeRef.value?.getCheckedKeys(true) ?? [];
};

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
  openRoleDialog(row.id);
};

const openCreateDialog = () => {
  createForm.name = '';
  createForm.permissions = [];
  createDialogVisible.value = true;
};

const handleCreateRole = async () => {
  if (!createForm.name.trim()) {
    flash.error('请先填写角色标识。');
    return;
  }

  isSaving.value = true;
  try {
    const createdRole = decorateRole(await adminApi.createRole({
      name: createForm.name.trim(),
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
    const updatedRole = decorateRole(await adminApi.updateRole(selectedRole.value.id, {
      permissions: [...roleDraft.permissions],
    }));
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
    if (selectedRole.value?.id === roleTarget.id) {
      roleDialogVisible.value = false;
      selectedRoleId.value = null;
      selectedRole.value = null;
      syncDraft(null);
    }
    flash.success('角色已删除。');
    await loadData();
  } catch (err) {
    flash.error(err.message || '删除角色失败。');
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
              <el-tooltip content="编辑权限" placement="top">
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

    <el-dialog
      v-model="createDialogVisible"
      title="新增角色"
      width="620px"
      class="roles-page__dialog-modal"
      destroy-on-close
    >
      <div class="roles-page__dialog">
        <label class="roles-page__field">
          <span class="roles-page__field-label"><em class="roles-page__required">*</em>角色标识</span>
          <el-input
            v-model="createForm.name"
            maxlength="150"
            placeholder="例如 ops_observer"
          />
        </label>

        <section class="roles-page__dialog-section">
          <div class="roles-page__section-heading">
            <strong>角色能力</strong>
            <span>按治理域展开，勾选父节点可整组选中。</span>
          </div>

          <el-tree-select
            v-model="createForm.permissions"
            class="roles-page__permission-tree"
            :data="permissionTreeOptions"
            node-key="value"
            value-key="value"
            multiple
            show-checkbox
            check-on-click-node
            clearable
            filterable
            collapse-tags
            collapse-tags-tooltip
            default-expand-all
            :render-after-expand="false"
            placeholder="请选择角色能力"
          />

          <div class="roles-page__selection-summary">
            <span class="roles-page__summary-chip">已选 {{ createForm.permissions.length }} 项权限</span>
            <span class="roles-page__muted-text">支持按权限编码或名称搜索</span>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="roles-page__dialog-actions">
          <el-button @click="createDialogVisible = false" :disabled="isSaving">取消</el-button>
          <el-button
            type="primary"
            :loading="isSaving"
            :disabled="!createForm.name.trim()"
            @click="handleCreateRole"
          >
            创建角色
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="roleDialogVisible"
      :title="selectedRole ? `角色权限 · ${selectedRole.label}` : '角色权限'"
      width="640px"
      class="roles-page__dialog-modal"
      destroy-on-close
    >
      <div v-if="selectedRole" class="roles-page__permission-editor">
        <div
          :class="[
            'roles-page__permission-tree-panel',
            !canManageRoles && 'is-readonly',
          ]"
        >
          <el-tree
            ref="rolePermissionTreeRef"
            :data="permissionTreeOptions"
            node-key="value"
            show-checkbox
            check-on-click-node
            default-expand-all
            :expand-on-click-node="false"
            :check-on-click-leaf="true"
            @check="handleRolePermissionTreeCheck"
          />
        </div>

        <div v-if="!canManageRoles" class="roles-page__muted-text">
          你当前只有查看权限，不能修改角色配置。
        </div>
      </div>

      <template #footer>
        <div class="roles-page__dialog-footer">
          <div class="roles-page__dialog-actions">
            <el-button @click="roleDialogVisible = false" :disabled="isSaving">关闭</el-button>
            <el-button
              v-if="canManageRoles"
              type="primary"
              :loading="isSaving"
              :disabled="!isSelectedRoleDirty"
              @click="handleSaveRole"
            >
              保存修改
            </el-button>
          </div>
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
.roles-page__dialog-footer,
.roles-page__dialog-actions,
.roles-page__selection-summary {
  display: flex;
  align-items: center;
  gap: 10px;
}

.roles-page__filter-actions,
.roles-page__table-toolbar,
.roles-page__dialog-footer {
  justify-content: space-between;
}

.roles-page__name-cell,
.roles-page__permission-editor,
.roles-page__dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.roles-page__name-cell strong,
.roles-page__section-heading strong {
  color: var(--text-primary);
}

.roles-page__name-cell small,
.roles-page__section-heading span,
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

.roles-page__dialog-section,
.roles-page__selection-summary {
  display: flex;
  align-items: center;
  gap: 10px;
}

.roles-page__dialog-section {
  flex-direction: column;
  align-items: stretch;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.roles-page__permission-tree-panel {
  min-height: 360px;
  padding: 8px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
  overflow: auto;
}

.roles-page__permission-tree-panel.is-readonly {
  pointer-events: none;
  opacity: 0.72;
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

.roles-page :deep(.el-tree-select__wrapper) {
  align-items: flex-start;
}

.roles-page :deep(.roles-page__permission-tree-panel .el-tree) {
  background: transparent;
}

.roles-page :deep(.roles-page__permission-tree-panel .el-tree-node__content) {
  min-height: 36px;
  border-radius: 10px;
}

.roles-page :deep(.roles-page__permission-tree-panel .el-tree-node__content:hover) {
  background: var(--surface-1);
}

.roles-page :deep(.roles-page__permission-tree-panel .el-tree-node__label) {
  color: var(--text-primary);
}

.roles-page :deep(.roles-page__permission-tree .el-select__wrapper) {
  min-height: 44px;
}

.roles-page :deep(.roles-page__permission-tree .el-select__tags) {
  max-width: calc(100% - 36px);
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
  .roles-page__filters-grid {
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
  .roles-page__dialog-footer,
  .roles-page__dialog-actions {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .roles-page__table-toolbar,
  .roles-page__dialog-footer,
  .roles-page__dialog-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .roles-page__filter-actions {
    justify-content: flex-start;
  }
}
</style>
