import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDashboardSummaryMetrics,
  buildDashboardTrendOption,
  normalizeDashboardPayload,
} from '../admin-dashboard.js';

test('dashboard board exposes four headline metrics backed by real week-over-week aggregates', () => {
  const stats = normalizeDashboardPayload({
    model_invocation_count_7d: 2843,
    model_invocation_count_prev_7d: 2390,
    total_token_count: 1894200,
    total_request_token_count: 1123000,
    total_response_token_count: 771200,
    token_count_7d: 451200,
    token_count_prev_7d: 401000,
    document_count: 15,
    document_added_count_7d: 4,
    document_added_count_prev_7d: 2,
    indexed_document_count: 10,
    indexed_document_completed_count_7d: 3,
    indexed_document_completed_count_prev_7d: 2,
  });

  const metrics = buildDashboardSummaryMetrics(stats);

  assert.deepEqual(metrics.map((item) => item.label), [
    '模型调用量',
    '系统 Token 用量',
    '知识文档总量',
    '已索引文档',
  ]);
  assert.equal(metrics[0].value, '2,843');
  assert.equal(metrics[0].delta, '较上周 +19.0%');
  assert.equal(metrics[1].value, '1,894,200');
  assert.equal(metrics[1].note, '输入 1,123,000 · 输出 771,200');
  assert.equal(metrics[2].note, '近 7 天 +4');
  assert.equal(metrics[3].delta, '较上周 +50.0%');
});

test('dashboard trend chart uses real model invocation and token usage series', () => {
  const stats = normalizeDashboardPayload({
    model_invocations_7d: [
      { date: '2026-05-01', value: 10 },
      { date: '2026-05-02', value: 12 },
      { date: '2026-05-03', value: 8 },
      { date: '2026-05-04', value: 14 },
      { date: '2026-05-05', value: 16 },
      { date: '2026-05-06', value: 20 },
      { date: '2026-05-07', value: 18 },
    ],
    token_usage_7d: [
      { date: '2026-05-01', value: 2200 },
      { date: '2026-05-02', value: 1850 },
      { date: '2026-05-03', value: 2410 },
      { date: '2026-05-04', value: 2980 },
      { date: '2026-05-05', value: 2640 },
      { date: '2026-05-06', value: 3160 },
      { date: '2026-05-07', value: 2875 },
    ],
  });

  const option = buildDashboardTrendOption(stats);

  assert.deepEqual(option.legend.data, ['模型调用', 'Token 用量']);
  assert.deepEqual(option.xAxis.data, ['05-01', '05-02', '05-03', '05-04', '05-05', '05-06', '05-07']);
  assert.deepEqual(option.series[0].data, [10, 12, 8, 14, 16, 20, 18]);
  assert.deepEqual(option.series[1].data, [2200, 1850, 2410, 2980, 2640, 3160, 2875]);
});
