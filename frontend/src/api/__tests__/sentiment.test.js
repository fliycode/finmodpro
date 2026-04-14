import test from 'node:test';
import assert from 'node:assert/strict';

import { createSentimentApi } from '../sentiment.js';

test('analyze posts dataset and document scope to sentiment endpoint', async () => {
  let request;

  const api = createSentimentApi({
    fetchJson: async (path, options) => {
      request = { path, options };
      return {
        code: 0,
        data: {
          summary: { overall_sentiment: 'negative' },
          distribution: [],
          items: [],
        },
      };
    },
  });

  const result = await api.analyze({
    dataset_id: 3,
    document_ids: [4, 5],
  });

  assert.equal(request.path, '/api/risk/sentiment/analyze');
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.auth, true);
  assert.deepEqual(JSON.parse(request.options.body), {
    dataset_id: 3,
    document_ids: [4, 5],
  });
  assert.equal(result.summary.overall_sentiment, 'negative');
});
