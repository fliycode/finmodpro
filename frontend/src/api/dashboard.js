import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (payload.code !== 0 && payload.code !== 200 && payload.code !== 201) {
      throw new Error(payload.message || '请求失败，请稍后重试');
    }
    return payload.data ?? {};
  }
  return payload ?? {};
};

const buildQueryPath = (path, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    query.set(key, String(value));
  });
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
};

export const dashboardApi = {
  async getStats() {
    return unwrap(await apiConfig.fetchJson('/api/dashboard/stats/', {
      method: 'GET',
      auth: true,
    }));
  },

  async getAudits(params = {}) {
    return unwrap(await apiConfig.fetchJson(buildQueryPath('/api/systemcheck/audits/', params), {
      method: 'GET',
      auth: true,
    }));
  },
};
