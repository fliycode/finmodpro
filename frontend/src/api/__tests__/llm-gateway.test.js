import test from 'node:test';
import assert from 'node:assert/strict';

import { createLlmGatewayApi } from '../llm-gateway.js';
import { getRouteDeleteBlockReason } from '../../lib/llm-gateway.js';

test('createLlmGatewayApi normalizes summary payload', async () => {
  const api = createLlmGatewayApi({
    fetchJson: async () => ({
      code: 0,
      data: {
        gateway: {
          status: 'healthy',
          active_model_count: 2,
          total_model_count: 3,
        },
        recent_sync: {
          status: 'success',
          message: 'ok',
          created_at: '2026-04-25T08:00:00Z',
        },
        traffic: {
          request_count: 18,
          failed_count: 2,
          error_rate_pct: 11.11,
        },
        top_models: [
          { alias: 'chat-default', request_count: 12 },
        ],
        recent_errors: [
          {
            time: '2026-04-25T07:40:00Z',
            alias: 'chat-default',
            status: 'failed',
            error_code: 'rate_limit',
            trace_id: 'trace-1',
          },
        ],
      },
    }),
  });

  const summary = await api.getSummary();

  assert.equal(summary.gateway.status, 'healthy');
  assert.equal(summary.traffic.request_count, 18);
  assert.equal(summary.top_models[0].alias, 'chat-default');
  assert.equal(summary.recent_errors[0].trace_id, 'trace-1');
});

test('createLlmGatewayApi builds query params for logs and costs', async () => {
  const calls = [];
  const api = createLlmGatewayApi({
    fetchJson: async (path) => {
      calls.push(path);
      return { code: 0, data: { total: 0, logs: [], points: [], models: [] } };
    },
  });

  await api.getLogs({ model: 'chat-default', status: 'failed', time: '7d', page: 2, page_size: 20 });
  await api.getCostsTimeseries({ time: '1h' });

  assert.deepEqual(calls, [
    '/api/ops/llm/gateway/logs/?model=chat-default&status=failed&time=7d&page=2&page_size=20',
    '/api/ops/llm/gateway/costs/timeseries/?time=1h',
  ]);
});

test('createLlmGatewayApi normalizes logs summary and timeseries granularity', async () => {
  const api = createLlmGatewayApi({
    fetchJson: async (path) => {
      if (path.includes('/logs/summary/')) {
        return {
          code: 0,
          data: {
            total_requests: 9,
            error_rate_pct: 22.22,
            avg_latency_ms: 540,
            error_breakdown: [{ error_code: 'timeout', count: 2 }],
            latency_buckets: [{ label: '100–500ms', count: 5 }],
          },
        };
      }
      return {
        code: 0,
        data: {
          granularity_hours: null,
          granularity_minutes: 1,
          points: [{ bucket: '2026-04-25T08:10', request_count: 2, estimated_cost: 0.12 }],
        },
      };
    },
  });

  const logsSummary = await api.getLogsSummary({ time: '24h' });
  const timeseries = await api.getCostsTimeseries({ time: '1h' });

  assert.equal(logsSummary.total_requests, 9);
  assert.equal(logsSummary.error_breakdown[0].error_code, 'timeout');
  assert.equal(timeseries.granularity_minutes, 1);
  assert.equal(timeseries.granularity_hours, null);
  assert.equal(timeseries.points[0].bucket, '2026-04-25T08:10');
});

test('getRouteDeleteBlockReason explains why active routes cannot be deleted', () => {
  assert.equal(
    getRouteDeleteBlockReason({ is_active: true }),
    '当前默认路由不能直接删除，请先切换默认链路或在编辑抽屉里取消默认状态。',
  );
  assert.equal(getRouteDeleteBlockReason({ is_active: false }), '');
});
