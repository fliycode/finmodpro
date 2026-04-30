import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDashboardIndustryRows,
  buildDashboardRegionRows,
  buildDashboardSourceRows,
  buildDashboardSummaryMetrics,
  normalizeDashboardPayload,
} from '../admin-dashboard.js';

test('dashboard board exposes six headline metrics from real admin aggregates', () => {
  const stats = normalizeDashboardPayload({
    document_count: 126580,
    indexed_document_count: 8432,
    risk_event_count: 32812,
    pending_risk_event_count: 128,
    high_risk_event_count: 128,
    active_model_count: 3,
    chat_request_count_24h: 2843,
    retrieval_hit_rate_7d: '86.4%',
  });

  const metrics = buildDashboardSummaryMetrics(stats);

  assert.deepEqual(metrics.map((item) => item.label), [
    '风险信息总数',
    '高风险事件',
    '知识文档总量',
    '已索引文档',
    '近 24h 问答',
    '启用模型',
  ]);
  assert.equal(metrics[0].value, '32,812');
  assert.equal(metrics[1].value, '128');
  assert.equal(metrics[3].value, '8,432');
});

test('dashboard board provides stable placeholder dimensions for future industry and region data', () => {
  const stats = normalizeDashboardPayload({
    risk_event_count: 1000,
    high_risk_event_count: 100,
    pending_risk_event_count: 80,
    document_count: 500,
    indexed_document_count: 420,
    chat_request_count_24h: 60,
  });

  const industries = buildDashboardIndustryRows(stats);
  const regions = buildDashboardRegionRows(stats);
  const sources = buildDashboardSourceRows(stats);

  assert.equal(industries.length, 6);
  assert.equal(regions.length, 8);
  assert.equal(sources.length, 4);
  assert.ok(industries.every((item) => item.value > 0));
  assert.ok(regions[0].value >= regions.at(-1).value);
  assert.equal(sources[0].label, '知识文档');
});
