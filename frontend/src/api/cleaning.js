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

export const normalizeCleaningSummary = (summary = {}) => {
  const qualityGate = summary.quality_gate || {};
  const recentResults = Array.isArray(summary.recent_results) ? summary.recent_results : [];
  return {
    totalRules: Number(summary.total_rules ?? 0),
    enabledRuleCount: Number(summary.enabled_rule_count ?? 0),
    defaultRuleTotal: Number(summary.default_rule_total ?? 0),
    defaultRuleCount: Number(summary.default_rule_count ?? 0),
    enabledDefaultRuleCount: Number(summary.enabled_default_rule_count ?? 0),
    defaultRulesInitialized: Boolean(summary.default_rules_initialized),
    missingDefaultRuleNames: Array.isArray(summary.missing_default_rule_names)
      ? summary.missing_default_rule_names
      : [],
    averageQualityScore: summary.average_quality_score == null
      ? null
      : Number(summary.average_quality_score),
    recentResultCount: Number(summary.recent_result_count ?? recentResults.length),
    lastCleanedAt: summary.last_cleaned_at || '',
    qualityGate: {
      minQualityScore: Number(qualityGate.min_quality_score ?? 0),
      warnQualityScore: Number(qualityGate.warn_quality_score ?? 0),
      blockBelowThreshold: Boolean(qualityGate.block_below_threshold),
    },
    recentResults: recentResults.map((result) => ({
      id: result.id ?? null,
      documentId: result.document_id ?? null,
      documentTitle: result.document_title || '未命名文档',
      qualityScore: Number(result.quality_score ?? 0),
      cleanedAt: result.cleaned_at || '',
      qualityGate: {
        score: Number(result.quality_gate?.score ?? result.quality_score ?? 0),
        status: result.quality_gate?.status || 'warning',
        reason: result.quality_gate?.reason || '',
        shouldBlock: Boolean(result.quality_gate?.should_block),
      },
    })),
  };
};

export const createCleaningApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async listRules() {
      return unwrap(await fetchJson('/api/knowledgebase/cleaning/rules', {
        method: 'GET',
        auth: true,
      }));
    },

    async createRule(payload) {
      return unwrap(await fetchJson('/api/knowledgebase/cleaning/rules', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      }));
    },

    async updateRule(ruleId, payload) {
      return unwrap(await fetchJson(`/api/knowledgebase/cleaning/rules/${ruleId}`, {
        method: 'PATCH',
        auth: true,
        body: JSON.stringify(payload),
      }));
    },

    async deleteRule(ruleId) {
      return unwrap(await fetchJson(`/api/knowledgebase/cleaning/rules/${ruleId}`, {
        method: 'DELETE',
        auth: true,
      }));
    },

    async getSummary() {
      const payload = unwrap(await fetchJson('/api/knowledgebase/cleaning/summary', {
        method: 'GET',
        auth: true,
      }));
      return normalizeCleaningSummary(payload.summary || payload);
    },

    async bootstrapDefaultRules() {
      const payload = unwrap(await fetchJson('/api/knowledgebase/cleaning/rules/bootstrap', {
        method: 'POST',
        auth: true,
      }));
      return {
        ...payload,
        summary: normalizeCleaningSummary(payload.summary || {}),
      };
    },

    async getDocumentResults(documentId) {
      return unwrap(await fetchJson(`/api/knowledgebase/documents/${documentId}/cleaning`, {
        method: 'GET',
        auth: true,
      }));
    },

    async triggerCleaning(documentId) {
      return unwrap(await fetchJson(`/api/knowledgebase/documents/${documentId}/cleaning`, {
        method: 'POST',
        auth: true,
      }));
    },
  };
};

export const cleaningApi = createCleaningApi();
