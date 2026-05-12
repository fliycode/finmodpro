import test from 'node:test';
import assert from 'node:assert/strict';

import { createCleaningApi, normalizeCleaningResult, normalizeCleaningSummary } from '../cleaning.js';

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

test('normalizeCleaningResult maps rules, issues and quality signals', () => {
  const result = normalizeCleaningResult({
    id: 5,
    document_id: 21,
    rules_applied: [{ id: 2, name: '默认：空白清理', type: 'clean_whitespace' }],
    issues_found: [{ rule: '默认：页码去除', type: 'page_number', detail: 'Removed page number: 12' }],
    quality_score: 81.6,
    quality_signals: {
      length: 70,
      symbol_density: 90,
    },
    original_length: 2300,
    cleaned_length: 2160,
    dedup_count: 1,
    quality_gate: {
      score: 81.6,
      status: 'passed',
      reason: '质量分通过当前门槛',
      should_block: false,
      min_quality_score: 60,
      warn_quality_score: 80,
    },
    cleaned_at: '2026-05-12T19:00:00+08:00',
  });

  assert.equal(result.documentId, 21);
  assert.equal(result.rulesApplied[0].name, '默认：空白清理');
  assert.equal(result.issuesFound[0].detail, 'Removed page number: 12');
  assert.equal(result.qualitySignals.length, 70);
  assert.equal(result.qualityGate.warnQualityScore, 80);
});

test('createCleaningApi normalizes document results and trigger response', async () => {
  const calls = [];
  const api = createCleaningApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      if (options.method === 'GET') {
        return {
          total: 1,
          results: [
            {
              id: 1,
              document_id: 9,
              rules_applied: [],
              issues_found: [],
              quality_score: 76.2,
              quality_signals: { sentence_integrity: 80 },
              original_length: 100,
              cleaned_length: 96,
              dedup_count: 0,
              quality_gate: {
                score: 76.2,
                status: 'warning',
                reason: '质量分低于建议阈值 80.0',
                should_block: false,
              },
              cleaned_at: '2026-05-12T19:00:00+08:00',
            },
          ],
        };
      }

      return {
        result: {
          id: 2,
          document_id: 9,
          rules_applied: [],
          issues_found: [],
          quality_score: 82.1,
          quality_signals: { length: 88 },
          original_length: 100,
          cleaned_length: 95,
          dedup_count: 0,
          quality_gate: {
            score: 82.1,
            status: 'passed',
            reason: '质量分通过当前门槛',
            should_block: false,
          },
          cleaned_at: '2026-05-12T19:05:00+08:00',
        },
      };
    },
  });

  const listing = await api.getDocumentResults(9);
  const trigger = await api.triggerCleaning(9);

  assert.equal(calls[0].path, '/api/knowledgebase/documents/9/cleaning');
  assert.equal(calls[1].options.method, 'POST');
  assert.equal(listing.total, 1);
  assert.equal(listing.results[0].qualitySignals.sentence_integrity, 80);
  assert.equal(trigger.result.qualityScore, 82.1);
  assert.equal(trigger.result.cleanedLength, 95);
});
