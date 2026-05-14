import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../RiskSummary.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('risk summary exposes single-document workflow, priority risk, and trace export surfaces', () => {
  const source = readComponent();

  assert.match(source, /单文档判读链路/);
  assert.match(source, /上传文档/);
  assert.match(source, /最高优先风险/);
  assert.match(source, /复核留痕/);
  assert.match(source, /导出结果/);
  assert.doesNotMatch(source, /前往审核队列/);
  assert.doesNotMatch(source, /审核队列/);
  assert.doesNotMatch(source, /知识库文档/);
  assert.doesNotMatch(source, /生成报告/);
  assert.doesNotMatch(source, /提取说明/);
});
