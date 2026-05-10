import { createApiConfig } from './config.js';

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (payload.code !== 0 && payload.code !== 200 && payload.code !== 201) {
      throw new Error(payload.message || '请求失败');
    }
    return payload.data;
  }
  return payload;
};

export const createRagEvalApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async runEvaluation(mode = 'all') {
      return unwrap(await fetchJson('/api/rag/evaluations/', {
        method: 'POST',
        auth: true,
        body: JSON.stringify({ mode }),
      }));
    },
  };
};

export const ragEvalApi = createRagEvalApi();
