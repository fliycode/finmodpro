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

  assert.match(source, /上传文档/);
  assert.match(source, /从知识库选择/);
  assert.match(source, /直接上传/);
  assert.match(source, /导出结果/);
  assert.match(source, /风险信息/);
  assert.match(source, /风险分类/);
  assert.match(source, /风险判断/);
  assert.match(source, /后续监控点/);
  assert.match(source, /选择一份文档/);
  assert.match(source, /el-dialog/);
  assert.match(source, /openRiskEventDetail/);
  assert.match(source, /openRiskGroupDetail/);
  assert.doesNotMatch(source, /风险提取工作台/);
  assert.doesNotMatch(source, /围绕当前文档完成提取、判读、导出与报告生成/);
  assert.doesNotMatch(source, /前往审核队列/);
  assert.doesNotMatch(source, /审核队列/);
  assert.doesNotMatch(source, /复核留痕/);
  assert.doesNotMatch(source, /提取说明/);
});
