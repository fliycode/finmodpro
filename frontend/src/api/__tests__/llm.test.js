import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createLlmApi,
  normalizeFineTuneRun,
  normalizeModelConfigPayload,
} from '../llm.js';
import { createApiConfig } from '../config.js';

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
        input_price_per_million: 0.5,
        output_price_per_million: 2,
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
  assert.equal(rows[0].input_price_per_million, 0.5);
  assert.equal(rows[0].output_price_per_million, 2);
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

test('createLlmApi deletes model configs', async () => {
  const calls = [];
  const api = createLlmApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      return { code: 0, data: { ok: true } };
    },
  });

  await api.deleteModelConfig(18);

  assert.deepEqual(calls, [
    {
      path: '/api/ops/model-configs/18/',
      options: {
        method: 'DELETE',
        auth: true,
      },
    },
  ]);
});

test('normalizeFineTuneRun keeps runner server metadata', () => {
  const run = normalizeFineTuneRun({
    id: 12,
    run_key: 'ft-001',
    runner_server_id: 9,
    runner_server_name: 'gpu-runner-a',
  });

  assert.equal(run.runner_server_id, 9);
  assert.equal(run.runner_server_name, 'gpu-runner-a');
});

test('createLlmApi manages fine-tune runner servers and dispatch', async () => {
  const calls = [];
  const api = createLlmApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      return { code: 0, data: { fine_tune_server: { id: 1 }, fine_tune_run: { id: 8 }, dispatch: { job_id: 'gpu-job-001' } } };
    },
  });

  await api.getFineTuneRunnerServers();
  await api.createFineTuneRunnerServer({ name: 'gpu-a' });
  await api.updateFineTuneRunnerServer(1, { name: 'gpu-b' });
  await api.deleteFineTuneRunnerServer(1);
  await api.dispatchFineTuneRun(8);

  assert.deepEqual(
    calls.map((call) => ({ path: call.path, method: call.options.method })),
    [
      { path: '/api/ops/fine-tune-servers/', method: 'GET' },
      { path: '/api/ops/fine-tune-servers/', method: 'POST' },
      { path: '/api/ops/fine-tune-servers/1/', method: 'PATCH' },
      { path: '/api/ops/fine-tune-servers/1/', method: 'DELETE' },
      { path: '/api/ops/fine-tunes/8/dispatch/', method: 'POST' },
    ],
  );
});

test('createApiConfig surfaces field validation details from error payloads', async () => {
  const api = createApiConfig({
    baseURL: 'http://localhost:8000',
    fetchImpl: async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        code: 400,
        message: '请求参数错误。',
        data: {
          dataset_name: ['This field is required.'],
          training_config: {
            template: ['This field may not be blank.'],
          },
        },
      }),
    }),
  });

  await assert.rejects(
    () => api.fetchJson('/api/ops/fine-tunes/', {
      method: 'POST',
      auth: true,
      body: JSON.stringify({}),
    }),
    (error) => {
      assert.match(error.message, /请求参数错误/);
      assert.match(error.message, /dataset_name/);
      assert.match(error.message, /training_config\.template/);
      return true;
    },
  );
});
