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

const normalizeQualityGate = (qualityGate = {}, fallbackScore = 0) => ({
  score: Number(qualityGate.score ?? fallbackScore ?? 0),
  status: qualityGate.status || 'warning',
  reason: qualityGate.reason || '',
  shouldBlock: Boolean(qualityGate.should_block),
  minQualityScore: Number(qualityGate.min_quality_score ?? 0),
  warnQualityScore: Number(qualityGate.warn_quality_score ?? 0),
});

export const normalizeCleaningResult = (result = {}) => ({
  id: result.id ?? null,
  documentId: result.document_id ?? null,
  rulesApplied: Array.isArray(result.rules_applied)
    ? result.rules_applied.map((rule) => ({
      id: rule.id ?? null,
      name: rule.name || '未命名规则',
      type: rule.type || '',
    }))
    : [],
  issuesFound: Array.isArray(result.issues_found)
    ? result.issues_found.map((issue, index) => ({
      id: `${result.id ?? 'result'}-${index}`,
      rule: issue.rule || '',
      type: issue.type || '',
      detail: issue.detail || '',
    }))
    : [],
  qualityScore: Number(result.quality_score ?? 0),
  qualitySignals: result.quality_signals && typeof result.quality_signals === 'object'
    ? Object.fromEntries(
      Object.entries(result.quality_signals).map(([key, value]) => [key, Number(value ?? 0)]),
    )
    : {},
  originalLength: Number(result.original_length ?? 0),
  cleanedLength: Number(result.cleaned_length ?? 0),
  dedupCount: Number(result.dedup_count ?? 0),
  qualityGate: normalizeQualityGate(result.quality_gate || {}, result.quality_score),
  cleanedAt: result.cleaned_at || '',
});

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
      qualityGate: normalizeQualityGate(result.quality_gate || {}, result.quality_score),
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
      const payload = unwrap(await fetchJson(`/api/knowledgebase/documents/${documentId}/cleaning`, {
        method: 'GET',
        auth: true,
      }));
      const results = Array.isArray(payload) ? payload : payload.results || [];
      return {
        results: results.map((result) => normalizeCleaningResult(result)),
        total: Number(payload.total ?? results.length),
      };
    },

    async triggerCleaning(documentId) {
      const payload = unwrap(await fetchJson(`/api/knowledgebase/documents/${documentId}/cleaning`, {
        method: 'POST',
        auth: true,
      }));
      return {
        ...payload,
        result: payload.result ? normalizeCleaningResult(payload.result) : null,
      };
    },
  };
};

export const cleaningApi = createCleaningApi();
