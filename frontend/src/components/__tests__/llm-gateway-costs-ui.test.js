import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../LlmGatewayCosts.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('llm gateway costs uses a stable summary grid and visualizes model share', () => {
  const source = readComponent();

  assert.match(source, /const summaryCards = computed/);
  assert.match(source, /class="cost-summary-grid"/);
  assert.match(source, /title="模型占比"/);
  assert.match(source, /modelShareChartOption/);
  assert.match(source, /<el-table :data="models\.models"/);
  assert.doesNotMatch(source, /<AdminDataTable/);
});
