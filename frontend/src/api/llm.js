import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

const unwrap = (data) => {
  if (data && data.data !== undefined && data.code !== undefined) {
    if (data.code !== 0 && data.code !== 200 && data.code !== 201) {
      throw new Error(data.message || '操作失败');
    }
    return data.data;
  }
  return data;
};

export const llmApi = {
  async getModelConfigs() {
    return unwrap(await apiConfig.fetchJson('/api/ops/model-configs/', {
      method: 'GET',
      auth: true,
    }));
  },

  async activateModelConfig(id, isActive) {
    return unwrap(await apiConfig.fetchJson(`/api/ops/model-configs/${id}/activation/`, {
      method: 'PATCH',
      auth: true,
      body: JSON.stringify({ is_active: isActive }),
    }));
  },

  async getEvaluations() {
    return unwrap(await apiConfig.fetchJson('/api/ops/evaluations', {
      method: 'GET',
      auth: true,
    }));
  },

  async triggerEvaluation(data) {
    return unwrap(await apiConfig.fetchJson('/api/ops/evaluations', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(data),
    }));
  },
};
