import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getDefaultSessionFilters,
  buildHistoryQuery,
  buildSessionExportDownload,
  formatHistoryTimestamp,
  getActiveSessionLabel,
  normalizeDatasetId,
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

test('normalizeDatasetId and getDefaultSessionFilters normalize route-friendly dataset values', () => {
  assert.equal(normalizeDatasetId('7'), 7);
  assert.equal(normalizeDatasetId('dataset-alpha'), 'dataset-alpha');
  assert.equal(normalizeDatasetId(''), null);
  assert.deepEqual(getDefaultSessionFilters('8'), { dataset_id: 8 });
  assert.deepEqual(getDefaultSessionFilters(''), {});
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

test('buildHistoryQuery serializes dataset and keyword filters', () => {
  assert.equal(
    buildHistoryQuery({ datasetId: 7, keyword: '流动性 风险' }),
    'dataset_id=7&keyword=%E6%B5%81%E5%8A%A8%E6%80%A7+%E9%A3%8E%E9%99%A9',
  );
  assert.equal(buildHistoryQuery({ datasetId: '', keyword: '   ' }), '');
});

test('buildSessionExportDownload returns a stable filename and json body', () => {
  const download = buildSessionExportDownload({
    session: {
      id: 5,
      title: '流动性风险讨论',
      messages: [{ role: 'user', content: '有哪些风险？' }],
    },
    exported_at: '2026-04-13T12:00:00Z',
  });

  assert.equal(download.filename, 'chat-session-5.json');
  assert.match(download.content, /流动性风险讨论/);
  assert.match(download.content, /"exported_at": "2026-04-13T12:00:00Z"/);
});
