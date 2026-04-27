import { createApiConfig } from './config.js';
import { buildQueryPath } from './llm.js';
import {
  normalizeGatewayCostsModels,
  normalizeGatewayCostsSummary,
  normalizeGatewayCostsTimeseries,
  normalizeGatewayErrors,
  normalizeGatewayLogs,
  normalizeGatewayLogsSummary,
  normalizeGatewaySummary,
  normalizeGatewayTrace,
} from '../lib/llm-gateway.js';

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (payload.code !== 0 && payload.code !== 200 && payload.code !== 201) {
      throw new Error(payload.message || '请求失败');
    }

    return payload.data;
  }

  return payload;
};

export const createLlmGatewayApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async getSummary() {
      return normalizeGatewaySummary(unwrap(await fetchJson('/api/ops/llm/gateway/summary/', {
        method: 'GET',
        auth: true,
      })));
    },

    async getLogs(params = {}) {
      return normalizeGatewayLogs(unwrap(await fetchJson(buildQueryPath('/api/ops/llm/gateway/logs/', params), {
        method: 'GET',
        auth: true,
      })));
    },

    async getLogsSummary(params = {}) {
      return normalizeGatewayLogsSummary(unwrap(await fetchJson(buildQueryPath('/api/ops/llm/gateway/logs/summary/', params), {
        method: 'GET',
        auth: true,
      })));
    },

    async getTrace(traceId) {
      return normalizeGatewayTrace(unwrap(await fetchJson(`/api/ops/llm/gateway/traces/${traceId}/`, {
        method: 'GET',
        auth: true,
      })));
    },

    async getErrors(params = {}) {
      return normalizeGatewayErrors(unwrap(await fetchJson(buildQueryPath('/api/ops/llm/gateway/errors/', params), {
        method: 'GET',
        auth: true,
      })));
    },

    async getCostsSummary(params = {}) {
      return normalizeGatewayCostsSummary(unwrap(await fetchJson(buildQueryPath('/api/ops/llm/gateway/costs/summary/', params), {
        method: 'GET',
        auth: true,
      })));
    },

    async getCostsTimeseries(params = {}) {
      return normalizeGatewayCostsTimeseries(unwrap(await fetchJson(buildQueryPath('/api/ops/llm/gateway/costs/timeseries/', params), {
        method: 'GET',
        auth: true,
      })));
    },

    async getCostsModels(params = {}) {
      return normalizeGatewayCostsModels(unwrap(await fetchJson(buildQueryPath('/api/ops/llm/gateway/costs/models/', params), {
        method: 'GET',
        auth: true,
      })));
    },
  };
};

export const llmGatewayApi = createLlmGatewayApi();
