import test from 'node:test';
import assert from 'node:assert/strict';

import { getDocumentRowActions, getIngestionAction } from '../knowledgebase-actions.js';

test('uploaded document exposes start ingestion action', () => {
  const action = getIngestionAction({
    status: 'uploaded',
    processStep: { code: 'uploaded' },
    latestTask: null,
    isSearchReady: false,
  });

  assert.deepEqual(action, {
    label: '启动入库',
    emphasis: 'primary',
  });
});

test('failed document exposes retry ingestion action', () => {
  const action = getIngestionAction({
    status: 'failed',
    processStep: { code: 'failed' },
    latestTask: { status: 'failed' },
    isSearchReady: false,
  });

  assert.deepEqual(action, {
    label: '重新入库',
    emphasis: 'primary',
  });
});

test('indexed document exposes reindex action', () => {
  const action = getIngestionAction({
    status: 'indexed',
    processStep: { code: 'indexed' },
    latestTask: { status: 'succeeded' },
    isSearchReady: true,
  });

  assert.deepEqual(action, {
    label: '重新入库',
    emphasis: 'secondary',
  });
});

test('processing document does not expose action', () => {
  const action = getIngestionAction({
    status: 'parsed',
    processStep: { code: 'parsing' },
    latestTask: { status: 'running' },
    isSearchReady: false,
  });

  assert.equal(action, null);
});

test('failed document exposes retry and error row actions', () => {
  const actions = getDocumentRowActions({
    status: 'failed',
    processStep: { code: 'failed' },
    latestTask: { status: 'failed' },
    isSearchReady: false,
    processError: '解析失败',
  });

  assert.deepEqual(
    actions.map((item) => item.id),
    ['retry', 'view-error'],
  );
});
