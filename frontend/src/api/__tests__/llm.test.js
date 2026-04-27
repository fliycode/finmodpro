import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createLlmApi,
  normalizeModelConfigPayload,
} from '../llm.js';

test('normalizeModelConfigPayload exposes LiteLLM routing fields', () => {
  const rows = normalizeModelConfigPayload({
    model_configs: [
      {
        id: 7,
        name: 'chat-default',
        provider: 'litellm',
        model_name: 'chat-default',
        capability: 'chat',
        endpoint: 'http://localhost:4000',
        alias: 'chat-default',
        upstream_provider: 'openai',
        upstream_model: 'gpt-4o',
        fallback_aliases: ['chat-backup'],
        weight: 2,
        has_api_key: true,
        api_key_masked: 'sk-tes******3456',
      },
    ],
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].alias, 'chat-default');
  assert.equal(rows[0].upstream_provider, 'openai');
  assert.equal(rows[0].upstream_model, 'gpt-4o');
  assert.deepEqual(rows[0].fallback_aliases, ['chat-backup']);
  assert.equal(rows[0].weight, 2);
});

test('createLlmApi calls LiteLLM sync and migrate endpoints', async () => {
  const calls = [];
  const api = createLlmApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      return { code: 0, data: { ok: true } };
    },
  });

  await api.syncModelConfigToLiteLLM(12);
  await api.migrateToLiteLLM();

  assert.deepEqual(
    calls.map((call) => call.path),
    [
      '/api/ops/model-configs/12/sync-litellm/',
      '/api/ops/model-configs/migrate-to-litellm/',
    ],
  );
  assert.deepEqual(
    calls.map((call) => call.options.method),
    ['POST', 'POST'],
  );
});
