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

export const cleaningApi = {
  async listRules() {
    return unwrap(await apiConfig.fetchJson('/api/knowledgebase/cleaning/rules', {
      method: 'GET',
      auth: true,
    }));
  },

  async createRule(payload) {
    return unwrap(await apiConfig.fetchJson('/api/knowledgebase/cleaning/rules', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async updateRule(ruleId, payload) {
    return unwrap(await apiConfig.fetchJson(`/api/knowledgebase/cleaning/rules/${ruleId}`, {
      method: 'PATCH',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async deleteRule(ruleId) {
    return unwrap(await apiConfig.fetchJson(`/api/knowledgebase/cleaning/rules/${ruleId}`, {
      method: 'DELETE',
      auth: true,
    }));
  },

  async getDocumentResults(documentId) {
    return unwrap(await apiConfig.fetchJson(`/api/knowledgebase/documents/${documentId}/cleaning`, {
      method: 'GET',
      auth: true,
    }));
  },

  async triggerCleaning(documentId) {
    return unwrap(await apiConfig.fetchJson(`/api/knowledgebase/documents/${documentId}/cleaning`, {
      method: 'POST',
      auth: true,
    }));
  },
};
