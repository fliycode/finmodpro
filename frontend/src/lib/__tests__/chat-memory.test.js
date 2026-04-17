import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildMemoryScopeLabel,
  getMemorySourceLabel,
  getMemoryTypeLabel,
  normalizeMemoryItems,
} from '../chat-memory.js';

test('normalizeMemoryItems keeps memory scope and display labels stable', () => {
  const items = normalizeMemoryItems([
    {
      id: 8,
      memory_type: 'work_rule',
      scope_type: 'dataset',
      scope_key: '7',
      title: '数据集 7 长期关注点',
      content: '重点跟踪流动性恶化。',
      source_kind: 'manual',
      pinned: 1,
      updated_at: '2026-04-17T08:00:00Z',
    },
  ]);

  assert.deepEqual(items[0], {
    id: 8,
    title: '数据集 7 长期关注点',
    content: '重点跟踪流动性恶化。',
    memoryType: 'work_rule',
    memoryTypeLabel: '工作规则',
    scopeType: 'dataset',
    scopeKey: '7',
    scopeLabel: '数据集 7',
    sourceKind: 'manual',
    sourceLabel: '手动整理',
    pinned: true,
    updatedAt: '2026-04-17T08:00:00Z',
  });
});

test('memory label helpers keep unknown values safe', () => {
  assert.equal(buildMemoryScopeLabel('user_global', ''), '全局记忆');
  assert.equal(buildMemoryScopeLabel('project', 'alpha'), '项目 alpha');
  assert.equal(getMemoryTypeLabel('unknown_type'), '其他记忆');
  assert.equal(getMemorySourceLabel('unknown_source'), '未知来源');
});
