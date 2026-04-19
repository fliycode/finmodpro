import test from 'node:test';
import assert from 'node:assert/strict';

import { createLlmConsoleApi } from '../llm-console.js';

test('createLlmConsoleApi calls llm console summary endpoints', async () => {
  const requests = [];
  const api = createLlmConsoleApi({
    baseURL: 'http://localhost:8000',
    fetchJson: async (path, options) => {
      requests.push({ path, options });
      return { providers: [], active_models: {}, quick_links: [] };
    },
  });

  await api.getSummary();
  await api.getObservability();
  await api.getKnowledge();

  assert.deepEqual(
    requests.map((request) => request.path),
    [
      '/api/ops/llm/summary/',
      '/api/ops/llm/observability/',
      '/api/ops/llm/knowledge/',
    ],
  );
  assert.deepEqual(requests.map((request) => request.options.method), ['GET', 'GET', 'GET']);
  assert.deepEqual(requests.map((request) => request.options.auth), [true, true, true]);
});
