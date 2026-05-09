import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createLlmApi,
  normalizeFineTuneRun,
  normalizeModelConfigOverviewSummary,
  normalizeModelConfigPayload,
} from '../llm.js';
import { createApiConfig } from '../config.js';

test('normalizeModelConfigPayload exposes direct provider pricing fields', () => {
  const rows = normalizeModelConfigPayload({
    model_configs: [
      {
        id: 7,
        name: 'chat-default',
        provider: 'deepseek',
        model_name: 'deepseek-chat',
        parameter_scale: '32B',
        capability: 'chat',
        endpoint: 'https://api.deepseek.com',
        description: '财报风控主力模型',
        input_price_per_million: 0.5,
        output_price_per_million: 2,
        request_price: 0.02,
        price_currency: 'USD',
        pricing_notes: '2026-05 official',
        has_api_key: true,
        api_key_masked: 'sk-tes******3456',
        invocation_count: 128,
      },
    ],
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].alias, 'deepseek-chat');
  assert.equal(rows[0].parameter_scale, '32B');
  assert.equal(rows[0].description, '财报风控主力模型');
  assert.equal(rows[0].upstream_provider, 'deepseek');
  assert.equal(rows[0].upstream_model, 'deepseek-chat');
  assert.equal(rows[0].input_price_per_million, 0.5);
  assert.equal(rows[0].output_price_per_million, 2);
  assert.equal(rows[0].request_price, 0.02);
  assert.equal(rows[0].price_currency, 'USD');
  assert.equal(rows[0].pricing_notes, '2026-05 official');
  assert.equal(rows[0].invocation_count, 128);
});

test('normalizeModelConfigOverviewSummary keeps overview metrics and nullable delta', () => {
  const overview = normalizeModelConfigOverviewSummary({
    overview: {
      total_models: 9,
      enabled_models: 3,
      total_invocation_count: 5600,
      today_invocation_count: 180,
      yesterday_invocation_count: 120,
      invocation_change_pct: 50,
    },
  });

  assert.deepEqual(overview, {
    total_models: 9,
    enabled_models: 3,
    total_invocation_count: 5600,
    today_invocation_count: 180,
    yesterday_invocation_count: 120,
    invocation_change_pct: 50,
  });
});

test('createLlmApi tests model config connections', async () => {
  const calls = [];
  const api = createLlmApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      return { code: 0, data: { ok: true } };
    },
  });

  await api.testModelConfigConnection({
    capability: 'chat',
    provider: 'deepseek',
    model_name: 'deepseek-chat',
    endpoint: 'https://api.deepseek.com',
    options: { api_key: 'secret' },
  });

  assert.deepEqual(
    calls.map((call) => call.path),
    ['/api/ops/model-configs/test-connection/'],
  );
  assert.deepEqual(
    calls.map((call) => call.options.method),
    ['POST'],
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
