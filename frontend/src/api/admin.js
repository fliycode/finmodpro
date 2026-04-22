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
