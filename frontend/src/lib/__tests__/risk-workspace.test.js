import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildRiskLevelChartOption,
  buildRiskTrendChartOption,
  normalizeRiskAnalytics,
} from '../risk-workspace.js';

test('normalizeRiskAnalytics unwraps nested API payload and preserves arrays', () => {
  assert.deepEqual(
    normalizeRiskAnalytics({
      data: {
        summary: { total_events: '3', high_risk_events: 2, pending_reviews: 1, unique_companies: 2, document_count: 1 },
        risk_level_distribution: [{ key: 'high', value: 2 }],
        trend: [{ date: '2025-02-01', value: 1 }],
      },
    }),
    {
      summary: {
        total_events: 3,
        high_risk_events: 2,
        pending_reviews: 1,
        unique_companies: 2,
        document_count: 1,
      },
      risk_level_distribution: [{ key: 'high', value: 2 }],
      risk_type_distribution: [],
      review_status_distribution: [],
      trend: [{ date: '2025-02-01', value: 1 }],
      top_companies: [],
    },
  );
});

test('buildRiskLevelChartOption maps backend distribution rows into chart slices', () => {
  const option = buildRiskLevelChartOption({
    risk_level_distribution: [
      { key: 'medium', value: 2 },
      { key: 'high', value: 1 },
    ],
  });

  assert.deepEqual(
    option.series[0].data,
    [
      { name: '中', value: 2 },
      { name: '高', value: 1 },
    ],
  );
});

test('buildRiskTrendChartOption uses backend dates and counts directly', () => {
  const option = buildRiskTrendChartOption({
    trend: [
      { date: '2025-02-10', value: 1 },
      { date: '2025-02-18', value: 3 },
    ],
  });

  assert.deepEqual(option.xAxis.data, ['02-10', '02-18']);
  assert.deepEqual(option.series[0].data, [1, 3]);
});
