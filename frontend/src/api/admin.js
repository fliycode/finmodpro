import { createApiConfig } from './config.js';

export const createAdminApi = (overrides = {}) => {
  const config = createApiConfig(overrides);

  return {
    listUsers() {
      return config.fetchJson('/api/admin/users', {
        method: 'GET',
        auth: true,
      });
    },
    listGroups() {
      return config.fetchJson('/api/admin/groups', {
        method: 'GET',
        auth: true,
      });
    },
    listRoles() {
      return config.fetchJson('/api/admin/roles', {
        method: 'GET',
        auth: true,
      });
    },
    listPermissions() {
      return config.fetchJson('/api/admin/permissions', {
        method: 'GET',
        auth: true,
      });
    },
    getRole(roleId) {
      return config.fetchJson(`/api/admin/roles/${roleId}`, {
        method: 'GET',
        auth: true,
      });
    },
    createRole(payload) {
      return config.fetchJson('/api/admin/roles/create', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      });
    },
    updateRole(roleId, payload) {
      return config.fetchJson(`/api/admin/roles/${roleId}`, {
        method: 'PATCH',
        auth: true,
        body: JSON.stringify(payload),
      });
    },
    deleteRole(roleId) {
      return config.fetchJson(`/api/admin/roles/${roleId}`, {
        method: 'DELETE',
        auth: true,
      });
    },
    restoreRoleDefaults(roleId) {
      return config.fetchJson(`/api/admin/roles/${roleId}/restore-defaults`, {
        method: 'POST',
        auth: true,
      });
    },
    createUser(payload) {
      return config.fetchJson('/api/admin/users', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      });
    },
    updateUser(userId, payload) {
      return config.fetchJson(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        auth: true,
        body: JSON.stringify(payload),
      });
    },
    deleteUser(userId) {
      return config.fetchJson(`/api/admin/users/${userId}`, {
        method: 'DELETE',
        auth: true,
      });
    },
    updateUserGroups(userId, groupNames) {
      return config.fetchJson(`/api/admin/users/${userId}/groups`, {
        method: 'PUT',
        auth: true,
        body: JSON.stringify({
          groups: groupNames,
        }),
      });
    }
  };
};

export const adminApi = createAdminApi();
