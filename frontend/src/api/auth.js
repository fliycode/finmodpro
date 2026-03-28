import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.message || '请求失败，请稍后重试');
  }

  return data;
};

const postJson = async (config, path, payload) => {
  const response = await config.fetchImpl(joinUrl(config.baseURL, path), {
    method: 'POST',
    headers: config.headers,
    body: JSON.stringify(payload),
  });

  return parseResponse(response);
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

export const createAuthApi = (overrides = {}) => {
  const config = createApiConfig(overrides);

  return {
    login(payload) {
      return postJson(config, '/api/auth/login', {
        username: payload.username,
        password: payload.password,
      });
    },
    register(payload) {
      return postJson(config, '/api/auth/register', {
        username: payload.username,
        password: payload.password,
        email: payload.email,
      });
    },
    me() {
      return getJson(config, '/api/auth/me');
    }
  };
};

export const authApi = createAuthApi();
