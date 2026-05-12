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
const keyword = ref('');
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
const filteredRoles = computed(() => sortRolesByPriority(roles.value).filter((role) => roleMatchesQuery(role, keyword.value)));

const stats = computed(() => {
  const systemRoles = roles.value.filter((role) => role.is_system).length;
  const customRoles = roles.value.filter((role) => !role.is_system).length;
  const customizedSystemRoles = roles.value.filter((role) => role.is_system && role.has_customized_permissions).length;

  return [
    {
      key: 'roles',
      label: '角色总数',
      value: roles.value.length,
      hint: `${systemRoles} 个系统角色 · ${customRoles} 个自定义角色`,
      icon: 'shield',
    },
    {
      key: 'permissions',
      label: '权限能力',
      value: permissions.value.length,
      hint: '所有权限均直接映射到 Django Permission',
      icon: 'sliders',
    },
    {
      key: 'customized',
      label: '已偏离默认',
      value: customizedSystemRoles,
      hint: '用于识别被在线编辑过的系统角色',
      icon: 'alert-triangle',
    },
  ];
});

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

    const preferredRoleId = roles.value.find((role) => role.id === selectedRoleId.value)?.id ?? roles.value[0]?.id ?? null;
    selectedRoleId.value = preferredRoleId;
    await loadRoleDetail(preferredRoleId, { preserveError: true });
  } catch (err) {
    error.value = err.message || '加载权限治理数据失败。';
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
    flash.success('角色权限已更新。');
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

const handleDeleteRole = async () => {
  if (!selectedRole.value || selectedRole.value.is_system || !canManageRoles.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `删除角色「${selectedRole.value.name}」后，原有权限配置将不可恢复。`,
      '删除角色',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
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
    await adminApi.deleteRole(selectedRole.value.id);
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
      `恢复默认会用系统基线覆盖角色「${selectedRole.value.name}」当前权限。`,
      '恢复默认权限',
      {
        type: 'warning',
        confirmButtonText: '恢复默认',
        cancelButtonText: '取消',
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

onMounted(async () => {
  await loadData();
});
</script>

<template>
  <div class="roles-page">
    <section class="roles-page__hero">
      <div class="roles-page__hero-copy">
        <span class="roles-page__eyebrow">Governance Control</span>
        <h2>角色与权限治理</h2>
        <p>用统一的角色目录、权限矩阵和自定义角色管理，把 RBAC 从“能运行”提升到“能运营”。</p>
      </div>
      <button
        v-if="canManageRoles"
        type="button"
        class="roles-page__primary-action"
        @click="openCreateDialog"
      >
        <AppIcon name="plus" />
        新建角色
      </button>
    </section>

    <div class="roles-page__stats">
      <article v-for="item in stats" :key="item.key" class="roles-page__stat-card">
        <span class="roles-page__stat-icon">
          <AppIcon :name="item.icon" />
        </span>
        <div class="roles-page__stat-copy">
          <small>{{ item.label }}</small>
          <strong>{{ item.value }}</strong>
          <p>{{ item.hint }}</p>
        </div>
      </article>
    </div>

    <div v-if="error" class="roles-page__error">
      <AppIcon name="alert-triangle" />
      <span>{{ error }}</span>
    </div>

    <div class="roles-page__layout">
      <AppSectionCard
        title="角色目录"
        desc="先选角色，再查看权限矩阵、成员归属与是否偏离默认基线。"
        admin
      >
        <template #header>
          <button
            type="button"
            class="roles-page__ghost-action"
            :disabled="isLoading"
            @click="loadData"
          >
            <AppIcon name="refresh" />
            刷新
          </button>
        </template>

        <label class="roles-page__search">
          <AppIcon name="search" />
          <input v-model="keyword" type="search" placeholder="搜索角色名称、说明或类型" />
        </label>

        <div v-if="isLoading" class="roles-page__empty">
          <AppIcon name="refresh" />
          <span>正在加载角色目录…</span>
        </div>

        <div v-else-if="!filteredRoles.length" class="roles-page__empty">
          <AppIcon name="shield" />
          <span>没有匹配的角色。</span>
        </div>

        <div v-else class="roles-page__role-list">
          <button
            v-for="role in filteredRoles"
            :key="role.id"
            type="button"
            :class="['roles-page__role-item', { 'is-active': role.id === selectedRoleId }]"
            @click="selectedRoleId = role.id"
          >
            <div class="roles-page__role-topline">
              <strong>{{ role.label }}</strong>
              <span :class="['roles-page__role-badge', role.is_system ? 'is-system' : 'is-custom']">
                {{ role.is_system ? '系统角色' : '自定义角色' }}
              </span>
            </div>
            <p>{{ getRoleDescription(role) }}</p>
            <div class="roles-page__role-meta">
              <span>{{ role.member_count }} 名成员</span>
              <span>{{ role.permissions.length }} 项权限</span>
              <span v-if="role.has_customized_permissions" class="is-warning">已偏离默认</span>
            </div>
          </button>
        </div>
      </AppSectionCard>

      <AppSectionCard
        title="角色详情"
        desc="支持查看成员、编辑自定义角色名、调整权限并恢复系统默认。"
        admin
      >
        <template #header>
          <div v-if="selectedRole" class="roles-page__detail-header-actions">
            <button
              v-if="canRestoreDefaults"
              type="button"
              class="roles-page__ghost-action"
              :disabled="isSaving"
              @click="handleRestoreDefaults"
            >
              <AppIcon name="refresh" />
              恢复默认
            </button>
            <button
              v-if="canManageRoles && !selectedRole.is_system"
              type="button"
              class="roles-page__danger-action"
              :disabled="isSaving || selectedRole.member_count > 0"
              @click="handleDeleteRole"
            >
              <AppIcon name="trash" />
              删除角色
            </button>
          </div>
        </template>

        <div v-if="!selectedRole" class="roles-page__empty is-large">
          <AppIcon name="shield" />
          <span>选择一个角色以查看权限矩阵。</span>
        </div>

        <div v-else class="roles-page__detail">
          <div class="roles-page__detail-summary">
            <div>
              <div class="roles-page__detail-topline">
                <h3>{{ selectedRole.label }}</h3>
                <span :class="['roles-page__role-badge', selectedRole.is_system ? 'is-system' : 'is-custom']">
                  {{ selectedRole.is_system ? '系统角色' : '自定义角色' }}
                </span>
                <span
                  v-if="selectedRole.has_customized_permissions"
                  class="roles-page__role-badge is-warning"
                >
                  已偏离默认
                </span>
              </div>
              <p>{{ selectedRole.description }}</p>
            </div>
            <div class="roles-page__detail-metrics">
              <div>
                <small>成员数</small>
                <strong>{{ selectedRole.member_count }}</strong>
              </div>
              <div>
                <small>已授予权限</small>
                <strong>{{ roleDraft.permissions.length }}</strong>
              </div>
              <div>
                <small>默认基线</small>
                <strong>{{ selectedRole.default_permissions.length }}</strong>
              </div>
            </div>
          </div>

          <div class="roles-page__form-grid">
            <label class="roles-page__field">
              <span>角色标识</span>
              <input
                v-model="roleDraft.name"
                :disabled="!canManageRoles || selectedRole.is_system || isSaving"
                type="text"
                placeholder="例如 ops_observer"
              />
              <small v-if="selectedRole.is_system">系统角色名称已锁定，避免破坏默认落组逻辑。</small>
              <small v-else>自定义角色名称会直接写入 Django Group。</small>
            </label>
          </div>

          <div class="roles-page__member-panel">
            <div class="roles-page__section-caption">
              <strong>关联成员</strong>
              <span>用于判断删除角色前是否还有用户绑定。</span>
            </div>
            <div v-if="selectedRole.assigned_users?.length" class="roles-page__member-list">
              <article
                v-for="member in selectedRole.assigned_users"
                :key="member.id"
                class="roles-page__member-card"
              >
                <strong>{{ member.username }}</strong>
                <span>{{ member.email || '未设置邮箱' }}</span>
              </article>
            </div>
            <div v-else class="roles-page__empty">
              <AppIcon name="users" />
              <span>当前没有用户绑定这个角色。</span>
            </div>
          </div>

          <div class="roles-page__permission-panel">
            <div class="roles-page__section-caption">
              <strong>权限矩阵</strong>
              <span>按治理域分组展示，勾选即表示该角色拥有对应能力。</span>
            </div>

            <section
              v-for="group in groupedPermissions"
              :key="group.key"
              class="roles-page__permission-group"
            >
              <header class="roles-page__permission-group-header">
                <div>
                  <strong>{{ group.label }}</strong>
                  <span>{{ group.items.length }} 项能力</span>
                </div>
              </header>

              <div class="roles-page__permission-grid">
                <label
                  v-for="permission in group.items"
                  :key="permission.codename"
                  class="roles-page__permission-card"
                >
                  <input
                    v-model="roleDraft.permissions"
                    :value="permission.codename"
                    :disabled="!canManageRoles || isSaving"
                    type="checkbox"
                  />
                  <div>
                    <strong>{{ permission.codename }}</strong>
                    <p>{{ permission.name }}</p>
                  </div>
                </label>
              </div>
            </section>
          </div>

          <div class="roles-page__footer">
            <p v-if="!canManageRoles">
              你当前只有只读权限，可查看角色矩阵，但不能修改。
            </p>
            <button
              v-else
              type="button"
              class="roles-page__primary-action"
              :disabled="isSaving || !isSelectedRoleDirty"
              @click="handleSaveRole"
            >
              <AppIcon name="check" />
              保存角色
            </button>
          </div>
        </div>
      </AppSectionCard>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      title="新建自定义角色"
      width="780px"
      destroy-on-close
    >
      <div class="roles-page__dialog">
        <label class="roles-page__field">
          <span>角色标识</span>
          <input v-model="createForm.name" type="text" placeholder="例如 ops_observer" />
          <small>会直接作为 Django Group 名称写入数据库。</small>
        </label>

        <section
          v-for="group in groupedPermissions"
          :key="`create-${group.key}`"
          class="roles-page__permission-group"
        >
          <header class="roles-page__permission-group-header">
            <div>
              <strong>{{ group.label }}</strong>
              <span>{{ group.items.length }} 项能力</span>
            </div>
          </header>

          <div class="roles-page__permission-grid">
            <label
              v-for="permission in group.items"
              :key="`create-${permission.codename}`"
              class="roles-page__permission-card"
            >
              <input
                v-model="createForm.permissions"
                :value="permission.codename"
                type="checkbox"
              />
              <div>
                <strong>{{ permission.codename }}</strong>
                <p>{{ permission.name }}</p>
              </div>
            </label>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="roles-page__dialog-footer">
          <button type="button" class="roles-page__ghost-action" @click="createDialogVisible = false">
            取消
          </button>
          <button
            type="button"
            class="roles-page__primary-action"
            :disabled="isSaving"
            @click="handleCreateRole"
          >
            <AppIcon name="plus" />
            创建角色
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.roles-page,
.roles-page__detail,
.roles-page__dialog {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.roles-page__hero,
.roles-page__stats,
.roles-page__layout,
.roles-page__detail-summary,
.roles-page__detail-metrics,
.roles-page__detail-header-actions,
.roles-page__role-topline,
.roles-page__role-meta,
.roles-page__permission-group-header,
.roles-page__footer,
.roles-page__dialog-footer {
  display: flex;
  gap: 16px;
}

.roles-page__hero,
.roles-page__detail-summary,
.roles-page__footer,
.roles-page__dialog-footer {
  justify-content: space-between;
  align-items: flex-start;
}

.roles-page__hero-copy {
  max-width: 720px;
}

.roles-page__eyebrow {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.roles-page__hero h2,
.roles-page__detail-topline h3 {
  margin: 0;
  color: var(--text-primary);
}

.roles-page__hero p,
.roles-page__detail-summary p,
.roles-page__role-item p,
.roles-page__permission-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.roles-page__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.roles-page__stat-card,
.roles-page__role-item,
.roles-page__member-card,
.roles-page__permission-card,
.roles-page__error {
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-1);
}

.roles-page__stat-card {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 20px 22px;
}

.roles-page__stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: rgba(36, 87, 197, 0.1);
  color: var(--brand);
}

.roles-page__stat-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.roles-page__stat-copy small,
.roles-page__section-caption span,
.roles-page__permission-group-header span,
.roles-page__field small,
.roles-page__role-meta,
.roles-page__member-card span {
  color: var(--text-muted);
  font-size: 13px;
}

.roles-page__stat-copy strong {
  font-size: 28px;
  color: var(--text-primary);
}

.roles-page__layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.5fr);
  align-items: start;
}

.roles-page__search {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  color: var(--text-muted);
}

.roles-page__search input,
.roles-page__field input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text-primary);
}

.roles-page__role-list,
.roles-page__member-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.roles-page__role-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  padding: 16px 18px;
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
}

.roles-page__role-item:hover,
.roles-page__role-item.is-active {
  border-color: rgba(36, 87, 197, 0.28);
  background: rgba(36, 87, 197, 0.06);
  transform: translateY(-1px);
}

.roles-page__role-topline,
.roles-page__role-meta,
.roles-page__detail-topline,
.roles-page__permission-group-header,
.roles-page__footer,
.roles-page__dialog-footer {
  justify-content: space-between;
  align-items: center;
}

.roles-page__role-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.roles-page__role-badge.is-system {
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
}

.roles-page__role-badge.is-custom {
  background: rgba(15, 23, 42, 0.08);
  color: var(--text-secondary);
}

.roles-page__role-badge.is-warning,
.roles-page__role-meta .is-warning {
  color: var(--warning);
}

.roles-page__detail-summary {
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(36, 87, 197, 0.08), rgba(36, 87, 197, 0.02));
}

.roles-page__detail-metrics {
  min-width: 280px;
  justify-content: flex-end;
}

.roles-page__detail-metrics > div {
  min-width: 84px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.62);
}

.roles-page__detail-metrics strong {
  display: block;
  margin-top: 4px;
  font-size: 20px;
  color: var(--text-primary);
}

.roles-page__form-grid,
.roles-page__member-panel,
.roles-page__permission-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.roles-page__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.roles-page__field span,
.roles-page__section-caption strong,
.roles-page__permission-group-header strong,
.roles-page__permission-card strong,
.roles-page__member-card strong {
  color: var(--text-primary);
}

.roles-page__field input {
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: var(--surface-2);
}

.roles-page__member-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.roles-page__member-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
}

.roles-page__permission-group {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-2);
}

.roles-page__permission-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.roles-page__permission-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
}

.roles-page__permission-card input {
  margin-top: 3px;
}

.roles-page__primary-action,
.roles-page__ghost-action,
.roles-page__danger-action {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  font-weight: 600;
  cursor: pointer;
}

.roles-page__primary-action {
  background: var(--brand);
  color: var(--color-white);
}

.roles-page__primary-action:disabled,
.roles-page__ghost-action:disabled,
.roles-page__danger-action:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.roles-page__ghost-action {
  background: transparent;
  border-color: var(--line-soft);
  color: var(--text-primary);
}

.roles-page__danger-action {
  background: rgba(196, 73, 61, 0.1);
  color: var(--risk);
}

.roles-page__empty,
.roles-page__error {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  padding: 18px;
  color: var(--text-secondary);
}

.roles-page__empty.is-large {
  min-height: 320px;
}

.roles-page__error {
  justify-content: flex-start;
  min-height: auto;
  color: var(--risk);
  background: rgba(196, 73, 61, 0.08);
}

@media (max-width: 1200px) {
  .roles-page__layout,
  .roles-page__stats,
  .roles-page__permission-grid {
    grid-template-columns: 1fr;
  }

  .roles-page__detail-summary,
  .roles-page__hero {
    flex-direction: column;
  }

  .roles-page__detail-metrics {
    width: 100%;
    min-width: 0;
  }
}
</style>
