import { createApiConfig } from './config.js';
import {
  normalizeConsoleSummary,
  normalizeKnowledgeSummary,
  normalizeObservabilitySummary,
} from '../lib/llm-console.js';

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (payload.code !== 0 && payload.code !== 200 && payload.code !== 201) {
      throw new Error(payload.message || '请求失败');
    }

    return payload.data;
  }

  return payload;
};

export const createLlmConsoleApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async getSummary() {
      return normalizeConsoleSummary(unwrap(await fetchJson('/api/ops/llm/summary/', {
        method: 'GET',
        auth: true,
      })));
    },

    async getObservability() {
      return normalizeObservabilitySummary(unwrap(await fetchJson('/api/ops/llm/observability/', {
        method: 'GET',
        auth: true,
      })));
    },

    async getKnowledge() {
      return normalizeKnowledgeSummary(unwrap(await fetchJson('/api/ops/llm/knowledge/', {
        method: 'GET',
        auth: true,
      })));
    },
  };
};

export const llmConsoleApi = createLlmConsoleApi();
