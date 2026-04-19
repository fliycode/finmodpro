import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildKnowledgePipeline,
  buildProviderTone,
  normalizeConsoleSummary,
  normalizeKnowledgeSummary,
  normalizeObservabilitySummary,
} from '../llm-console.js';

test('normalizeConsoleSummary provides stable provider and quick-link defaults', () => {
  const payload = normalizeConsoleSummary({
    providers: [{ key: 'litellm', label: 'LiteLLM', status: 'connected', active_count: 2 }],
    active_models: {
      chat: { provider: 'litellm', model_name: 'chat-default', endpoint: 'http://localhost:4000' },
    },
    quick_links: [{ label: '模型配置', to: '/admin/llm/models' }],
  });

  assert.equal(payload.providers[0].key, 'litellm');
  assert.equal(payload.active_models.chat.model_name, 'chat-default');
  assert.equal(payload.quick_links[0].to, '/admin/llm/models');
});

test('normalizeConsoleSummary accepts alias-style provider and model fields', () => {
  const payload = normalizeConsoleSummary({
    providers: [
      {
        name: 'LiteLLM',
        activeCount: 4,
        lastActiveAt: '2026-04-18T10:00:00Z',
        base_url: 'http://localhost:4000',
        modelName: 'qwen-max',
        detail: '在线',
      },
    ],
    active_models: {
      chat: {
        provider: 'litellm',
        modelName: 'qwen-max',
        base_url: 'http://localhost:4000',
        alias: 'chat-default',
      },
    },
  });

  assert.equal(payload.providers[0].key, 'LiteLLM');
  assert.equal(payload.providers[0].active_count, 4);
  assert.equal(payload.providers[0].endpoint, 'http://localhost:4000');
  assert.equal(payload.providers[0].model_name, 'qwen-max');
  assert.equal(payload.providers[0].summary, '在线');
  assert.equal(payload.active_models.chat.model_name, 'qwen-max');
  assert.equal(payload.active_models.chat.endpoint, 'http://localhost:4000');
  assert.equal(payload.active_models.chat.alias, 'chat-default');
});

test('normalizeObservabilitySummary keeps langfuse status and failure list', () => {
  const payload = normalizeObservabilitySummary({
    overview: { chat_request_count_24h: 3, avg_duration_ms_24h: 120 },
    recent_failures: [{ kind: 'ingestion', document_title: '年报' }],
    langfuse: { configured: true, host: 'https://langfuse.example' },
  });

  assert.equal(payload.overview.chat_request_count_24h, 3);
  assert.equal(payload.recent_failures[0].document_title, '年报');
  assert.equal(payload.langfuse.configured, true);
});

test('normalizeKnowledgeSummary preserves parser capabilities and pipeline steps', () => {
  const payload = normalizeKnowledgeSummary({
    parser_capabilities: {
      pdf: { parser: 'unstructured', fallback: true },
    },
    pipeline_steps: ['解析', '切块', '向量化', '索引'],
  });

  assert.equal(payload.parser_capabilities.pdf.parser, 'unstructured');
  assert.deepEqual(payload.pipeline_steps, ['解析', '切块', '向量化', '索引']);
});

test('normalizeKnowledgeSummary accepts parser capability aliases', () => {
  const payload = normalizeKnowledgeSummary({
    parser_capabilities: {
      pdf: { parser: 'unstructured', fallback: true, summary: '备用解析' },
    },
  });

  assert.equal(payload.parser_capabilities.pdf.detail, '备用解析');
});

test('buildProviderTone marks missing integrations as warning', () => {
  assert.equal(buildProviderTone({ status: 'missing' }), 'warning');
  assert.equal(buildProviderTone({ status: 'connected' }), 'success');
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
