import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDocumentStatusOption,
  buildRiskDistributionOption,
  buildTrendChartOption,
  normalizeDashboardPayload,
  summarizeOperationalPosture,
} from '../admin-dashboard.js';

test('normalizeDashboardPayload preserves real zero values', () => {
  const payload = normalizeDashboardPayload({
    data: {
      active_model_count: 0,
      chat_request_count_24h: 0,
      pending_risk_event_count: 0,
      recent_activity: [],
    },
  });

  assert.equal(payload.active_model_count, 0);
  assert.equal(payload.chat_request_count_24h, 0);
  assert.equal(payload.pending_risk_event_count, 0);
  assert.deepEqual(payload.recent_activity, []);
});

test('buildTrendChartOption uses backend dates and values', () => {
  const option = buildTrendChartOption({
    chat_requests_7d: [
      { date: '2026-04-04', value: 2 },
      { date: '2026-04-05', value: 5 },
    ],
    retrieval_hits_7d: [
      { date: '2026-04-04', value: 1 },
      { date: '2026-04-05', value: 3 },
    ],
  });

  assert.deepEqual(option.xAxis.data, ['04-04', '04-05']);
  assert.deepEqual(option.series[0].data, [2, 5]);
  assert.deepEqual(option.series[1].data, [1, 3]);
});

test('buildRiskDistributionOption maps risk counts into chart rows', () => {
  const option = buildRiskDistributionOption({
    risk_level_distribution: {
      low: 1,
      medium: 2,
      high: 3,
      critical: 4,
    },
  });

  assert.deepEqual(
    option.series[0].data.map((item) => item.value),
    [1, 2, 3, 4],
  );
});

test('buildDocumentStatusOption maps document status counts into chart rows', () => {
  const option = buildDocumentStatusOption({
    document_status_distribution: {
      uploaded: 2,
      parsed: 1,
      chunked: 3,
      indexed: 7,
      failed: 1,
    },
  });

  assert.deepEqual(option.yAxis.data, ['上传', '解析', '切块', '已索引', '失败']);
  assert.deepEqual(option.series[0].data, [2, 1, 3, 7, 1]);
});

test('summarizeOperationalPosture prioritizes pending risk and failed documents', () => {
  const summary = summarizeOperationalPosture({
    pending_risk_event_count: 3,
    failed_document_count: 2,
    retrieval_hit_rate_7d: '50.0%',
  });

  assert.equal(summary.tone, 'risk');
  assert.match(summary.label, /优先处理|重点/);
});
