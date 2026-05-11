import test from 'node:test';
import assert from 'node:assert/strict';

import { createCleaningApi, normalizeCleaningSummary } from '../cleaning.js';

test('normalizeCleaningSummary maps quality gate and recent results', () => {
  const summary = normalizeCleaningSummary({
    total_rules: 7,
    enabled_rule_count: 6,
    default_rule_total: 7,
    default_rule_count: 5,
    enabled_default_rule_count: 4,
    default_rules_initialized: false,
    missing_default_rule_names: ['默认：页码去除'],
    average_quality_score: 72.4,
    recent_result_count: 1,
    last_cleaned_at: '2026-05-11T12:00:00+08:00',
    quality_gate: {
      min_quality_score: 60,
      warn_quality_score: 80,
      block_below_threshold: true,
    },
    recent_results: [
      {
        id: 1,
        document_id: 11,
        document_title: '2025Q1 风险纪要',
        quality_score: 58.2,
        cleaned_at: '2026-05-11T12:00:00+08:00',
        quality_gate: {
          score: 58.2,
          status: 'blocked',
          reason: '质量分低于最低阈值 60.0',
          should_block: true,
        },
      },
    ],
  });

  assert.equal(summary.totalRules, 7);
  assert.equal(summary.enabledRuleCount, 6);
  assert.equal(summary.defaultRulesInitialized, false);
  assert.deepStrictEqual(summary.missingDefaultRuleNames, ['默认：页码去除']);
  assert.equal(summary.qualityGate.minQualityScore, 60);
  assert.equal(summary.recentResults[0].qualityGate.status, 'blocked');
  assert.equal(summary.recentResults[0].documentTitle, '2025Q1 风险纪要');
});

test('createCleaningApi bootstraps default rules and normalizes summary payload', async () => {
  const calls = [];
  const api = createCleaningApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      return {
        created_count: 2,
        existing_count: 5,
        summary: {
          total_rules: 7,
          enabled_rule_count: 7,
          default_rule_total: 7,
          default_rule_count: 7,
          enabled_default_rule_count: 7,
          default_rules_initialized: true,
          missing_default_rule_names: [],
          average_quality_score: null,
          recent_result_count: 0,
          last_cleaned_at: '',
          quality_gate: {
            min_quality_score: 60,
            warn_quality_score: 80,
            block_below_threshold: true,
          },
          recent_results: [],
        },
      };
    },
  });

  const result = await api.bootstrapDefaultRules();

  assert.equal(calls[0].path, '/api/knowledgebase/cleaning/rules/bootstrap');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(result.created_count, 2);
  assert.equal(result.summary.defaultRulesInitialized, true);
  assert.equal(result.summary.qualityGate.blockBelowThreshold, true);
});
