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
    updateUserGroups(userId, groupNames) {
      return putJson(config, `/api/admin/users/${userId}/groups`, {
        groups: groupNames
      });
    }
  };
};

export const adminApi = createAdminApi();
