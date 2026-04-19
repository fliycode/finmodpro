import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildKnowledgePipeline,
  buildProviderTone,
  normalizeConsoleSummary,
  normalizeKnowledgeSummary,
  normalizeObservabilitySummary,
} from '../llm-console.js';

test('normalizeConsoleSummary fills stable summary defaults for partial payloads', () => {
  const payload = normalizeConsoleSummary({
    data: {
      active_models: {
        chat: { provider: 'litellm' },
      },
      recent_activity: {
        chat_request_count_24h: 7,
      },
      quick_links: [{ label: '模型配置', to: '/admin/llm/models' }],
    },
  });

  assert.deepEqual(payload.active_models, {
    chat: {
      provider: 'litellm',
      model_name: '',
      endpoint: '',
      alias: '',
      status: '',
      raw: { provider: 'litellm' },
    },
    embedding: {
      provider: '',
      model_name: '',
      endpoint: '',
      alias: '',
      status: '',
      raw: {},
    },
  });
  assert.deepEqual(payload.recent_activity, {
    chat_request_count_24h: 7,
    failed_ingestion_count: 0,
    running_fine_tune_count: 0,
    latest_fine_tune_status: '',
  });
  assert.equal(payload.quick_links[0].to, '/admin/llm/models');
});

test('normalizeObservabilitySummary fills stable overview and langfuse defaults', () => {
  const payload = normalizeObservabilitySummary({
    overview: { avg_duration_ms_24h: 120 },
    recent_failures: [{ kind: 'ingestion', document_title: '年报' }],
    langfuse: { host: 'https://langfuse.example' },
  });

  assert.deepEqual(payload.overview, {
    chat_request_count_24h: 0,
    retrieval_hit_count_24h: 0,
    avg_duration_ms_24h: 120,
    failed_ingestion_count: 0,
  });
  assert.equal(payload.recent_failures[0].document_title, '年报');
  assert.deepEqual(payload.langfuse, {
    configured: false,
    host: 'https://langfuse.example',
    has_public_key: false,
    has_secret_key: false,
  });
});

test('normalizeKnowledgeSummary fills stable ingestion summary defaults', () => {
  const payload = normalizeKnowledgeSummary({
    ingestion_summary: { failed: 2 },
  });

  assert.deepEqual(payload.ingestion_summary, {
    total_documents: 0,
    queued: 0,
    running: 0,
    succeeded: 0,
    failed: 2,
  });
});

test('buildProviderTone maps configured providers to info', () => {
  assert.equal(buildProviderTone({ status: 'configured' }), 'info');
  assert.equal(buildProviderTone({ status: 'missing' }), 'warning');
  assert.equal(buildProviderTone({ status: 'connected' }), 'success');
  assert.equal(buildProviderTone({ status: 'idle' }), 'warning');
  assert.equal(buildProviderTone({ status: 'unknown' }), 'warning');
});

test('buildKnowledgePipeline returns step cards in fixed order', () => {
  assert.deepEqual(
    buildKnowledgePipeline(['解析', '切块', '向量化']),
    [
      { label: '解析', index: 1 },
      { label: '切块', index: 2 },
      { label: '向量化', index: 3 },
    ],
  );
});
