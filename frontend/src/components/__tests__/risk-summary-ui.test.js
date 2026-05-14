import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../RiskSummary.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('risk summary centers the document-to-review workflow and removes retired utilities', () => {
  const source = readComponent();

  assert.match(source, /先选文档，再提取风险/);
  assert.match(source, /前往审核队列/);
  assert.doesNotMatch(source, /Risk Extraction/);
  assert.doesNotMatch(source, /更多工具/);
  assert.doesNotMatch(source, /生成报告/);
  assert.doesNotMatch(source, /导出 Markdown/);
  assert.doesNotMatch(source, /导出事件 JSON/);
});
