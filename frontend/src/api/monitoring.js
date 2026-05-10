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

export const monitoringApi = {
  async getStatus() {
    return unwrap(await apiConfig.fetchJson('/api/monitoring/monitoring/status/', {
      method: 'GET',
      auth: true,
    }));
  },

  async getMetricTimeSeries(metricName, hours = 24) {
    return unwrap(await apiConfig.fetchJson(
      buildQueryPath('/api/monitoring/monitoring/metrics/', { metric_name: metricName, hours }),
      { method: 'GET', auth: true },
    ));
  },

  async listAlertRules(enabledOnly = false) {
    return unwrap(await apiConfig.fetchJson(
      buildQueryPath('/api/monitoring/alerts/rules/', { enabled_only: enabledOnly ? 'true' : '' }),
      { method: 'GET', auth: true },
    ));
  },

  async createAlertRule(payload) {
    return unwrap(await apiConfig.fetchJson('/api/monitoring/alerts/rules/', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async updateAlertRule(ruleId, payload) {
    return unwrap(await apiConfig.fetchJson(`/api/monitoring/alerts/rules/${ruleId}/`, {
      method: 'PATCH',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async deleteAlertRule(ruleId) {
    return unwrap(await apiConfig.fetchJson(`/api/monitoring/alerts/rules/${ruleId}/`, {
      method: 'DELETE',
      auth: true,
    }));
  },

  async listAlertEvents(params = {}) {
    return unwrap(await apiConfig.fetchJson(
      buildQueryPath('/api/monitoring/alerts/events/', params),
      { method: 'GET', auth: true },
    ));
  },

  async acknowledgeAlertEvent(eventId) {
    return unwrap(await apiConfig.fetchJson(`/api/monitoring/alerts/events/${eventId}/acknowledge/`, {
      method: 'POST',
      auth: true,
    }));
  },
};
