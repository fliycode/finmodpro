import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../RiskSummary.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('risk summary reduces the page to upload button and results panel', () => {
  const source = readComponent();

  assert.match(source, /上传文档/);
  assert.match(source, /提取结果/);
  assert.doesNotMatch(source, /前往审核队列/);
  assert.doesNotMatch(source, /审核队列/);
  assert.doesNotMatch(source, /知识库文档/);
  assert.doesNotMatch(source, /生成报告/);
});
