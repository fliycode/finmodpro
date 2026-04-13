import test from 'node:test';
import assert from 'node:assert/strict';

import { createRiskApi } from '../risk.js';

const originalLocalStorage = globalThis.localStorage;

const createStorage = () => {
  const store = new Map();
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
  };
};

test.afterEach(() => {
  globalThis.localStorage = originalLocalStorage;
});

test('getAnalytics sends filtered GET request with auth header', async () => {
  globalThis.localStorage = createStorage();
  globalThis.localStorage.setItem('finmodpro_token', 'analytics-token');

  let request;
  const api = createRiskApi({
    baseURL: 'http://localhost:8000',
    fetchImpl: async (url, options) => {
      request = { url, options };
      return {
        ok: true,
        async json() {
          return { data: { summary: { total_events: 1 } } };
        },
      };
    },
  });

  await api.getAnalytics({
    review_status: 'approved',
    period_start: '2025-02-01',
  });

  assert.equal(request.url, 'http://localhost:8000/api/risk/analytics/overview?review_status=approved&period_start=2025-02-01');
  assert.equal(request.options.method, 'GET');
  assert.equal(request.options.headers.Authorization, 'Bearer analytics-token');
});

test('exportReport returns filename content type and text body from attachment response', async () => {
  globalThis.localStorage = createStorage();

  const api = createRiskApi({
    baseURL: 'http://localhost:8000',
    fetchImpl: async () => ({
      ok: true,
      headers: {
        get(name) {
          if (name === 'Content-Disposition') {
            return 'attachment; filename="risk-report-8.md"';
          }
          if (name === 'Content-Type') {
            return 'text/markdown; charset=utf-8';
          }
          return null;
        },
      },
      async text() {
        return '# 风险报告';
      },
    }),
  });

  const result = await api.exportReport(8);

  assert.deepEqual(result, {
    filename: 'risk-report-8.md',
    contentType: 'text/markdown; charset=utf-8',
    content: '# 风险报告',
  });
});
