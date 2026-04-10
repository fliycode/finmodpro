import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatHistoryTimestamp,
  getActiveSessionLabel,
  normalizeHistoryItems,
} from '../workspace-qa.js';

test('getActiveSessionLabel returns 新对话 when no session is active', () => {
  assert.equal(getActiveSessionLabel([], null), '新对话');
});

test('getActiveSessionLabel returns matched session title', () => {
  const label = getActiveSessionLabel(
    [{ id: 12, title: '流动性风险讨论' }],
    12,
  );

  assert.equal(label, '流动性风险讨论');
});

test('normalizeHistoryItems keeps preview and timestamp fields display-safe', () => {
  const items = normalizeHistoryItems([
    {
      id: 3,
      title: '',
      lastMessagePreview: '最近一条消息',
      updatedAt: '2026-04-10T07:00:00Z',
    },
  ]);

  assert.equal(items[0].title, '未命名会话');
  assert.equal(items[0].preview, '最近一条消息');
  assert.ok(items[0].timestamp.length > 0);
});

test('formatHistoryTimestamp returns placeholder for empty values', () => {
  assert.equal(formatHistoryTimestamp(''), '最近无更新');
});
