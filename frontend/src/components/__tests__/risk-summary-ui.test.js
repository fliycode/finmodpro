import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../RiskSummary.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('risk summary exposes reference-style workbench actions and removes side analytics surfaces', () => {
  const source = readComponent();

  assert.match(source, /风险信息提取/);
  assert.match(source, /文档来源/);
  assert.match(source, /文档判读/);
  assert.match(source, /提取结果/);
  assert.match(source, /导出结果/);
  assert.match(source, /生成风险报告/);
  assert.doesNotMatch(source, /前往审核队列/);
  assert.doesNotMatch(source, /审核队列/);
  assert.doesNotMatch(source, /知识库文档/);
  assert.doesNotMatch(source, /复核留痕/);
  assert.doesNotMatch(source, /提取说明/);
});
