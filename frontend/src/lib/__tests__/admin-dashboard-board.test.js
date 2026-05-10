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
    audit_operation_count_7d: 188,
    audit_operation_count_prev_7d: 160,
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
    '审计操作量',
    '知识文档总量',
    '已索引文档',
  ]);
  assert.equal(metrics[0].value, '2,843');
  assert.equal(metrics[0].delta, '较上周 +19.0%');
  assert.equal(metrics[1].value, '188');
  assert.equal(metrics[2].note, '近 7 天 +4');
  assert.equal(metrics[3].delta, '较上周 +50.0%');
});

test('dashboard trend chart uses real model invocation and audit operation series', () => {
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
    audit_operations_7d: [
      { date: '2026-05-01', value: 2 },
      { date: '2026-05-02', value: 1 },
      { date: '2026-05-03', value: 3 },
      { date: '2026-05-04', value: 4 },
      { date: '2026-05-05', value: 3 },
      { date: '2026-05-06', value: 5 },
      { date: '2026-05-07', value: 4 },
    ],
  });

  const option = buildDashboardTrendOption(stats);

  assert.deepEqual(option.legend.data, ['模型调用', '审计操作']);
  assert.deepEqual(option.xAxis.data, ['05-01', '05-02', '05-03', '05-04', '05-05', '05-06', '05-07']);
  assert.deepEqual(option.series[0].data, [10, 12, 8, 14, 16, 20, 18]);
  assert.deepEqual(option.series[1].data, [2, 1, 3, 4, 3, 5, 4]);
});
