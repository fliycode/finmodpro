import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../LlmGatewayObservability.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('llm gateway observability removes latency distribution copy and uses refreshed icons', () => {
  const source = readComponent();

  assert.match(source, /icon="data-usage"/);
  assert.match(source, /icon="frame-inspect"/);
  assert.match(source, /:eyebrow="''"/);
  assert.doesNotMatch(source, /title="延迟分布"/);
  assert.doesNotMatch(source, /当前窗口各延迟区间的请求数量/);
  assert.doesNotMatch(source, /按模型聚合当前窗口的输入\/输出 Token 消耗/);
  assert.doesNotMatch(source, /请求级别摘要，不暴露原始 prompt \/ response/);
});
