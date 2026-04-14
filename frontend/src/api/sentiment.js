import { createApiConfig } from './config.js';

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (payload.code !== 0 && payload.code !== 200 && payload.code !== 201) {
      throw new Error(payload.message || '请求失败，请稍后重试');
    }
    return payload.data ?? {};
  }
  return payload ?? {};
};

export const createSentimentApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async analyze(payload = {}) {
      return unwrap(await fetchJson('/api/risk/sentiment/analyze', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      }));
    },
  };
};

export const sentimentApi = createSentimentApi();
