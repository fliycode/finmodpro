import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../LlmGatewayObservability.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('llm gateway observability shows a second chart and uses call-record wording', () => {
  const source = readComponent();

  assert.match(source, /icon="data-usage"/);
  assert.match(source, /title="延迟区间"/);
  assert.match(source, /title="调用记录"/);
  assert.match(source, /icon="request-page"/);
  assert.match(source, /:eyebrow="''"/);
  assert.doesNotMatch(source, /title="请求摘要"/);
});
