import { createApiConfig } from './config.js';
import {
  normalizeConsoleSummary,
  normalizeKnowledgeSummary,
  normalizeObservabilitySummary,
} from '../lib/llm-console.js';

export const createLlmConsoleApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async getSummary() {
      return normalizeConsoleSummary(
        await fetchJson('/api/ops/llm/summary/', {
          method: 'GET',
          auth: true,
        }),
      );
    },

    async getObservability() {
      return normalizeObservabilitySummary(
        await fetchJson('/api/ops/llm/observability/', {
          method: 'GET',
          auth: true,
        }),
      );
    },

    async getKnowledge() {
      return normalizeKnowledgeSummary(
        await fetchJson('/api/ops/llm/knowledge/', {
          method: 'GET',
          auth: true,
        }),
      );
    },
  };
};

export const llmConsoleApi = createLlmConsoleApi();
