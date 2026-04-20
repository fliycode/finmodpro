import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getQaChromeState,
  shouldShowQaEmptyState,
} from '../workspace-qa.js';

test('qa chrome only keeps the three primary actions', () => {
  assert.deepEqual(getQaChromeState(), {
    showEyebrow: false,
    showSessionState: false,
    showSessionMeta: false,
    showSessionSummary: false,
    actions: ['history', 'memory', 'new'],
  });
});

test('empty state disappears after the first real user or assistant message', () => {
  assert.equal(shouldShowQaEmptyState([{ role: 'system', content: '欢迎' }]), true);
  assert.equal(
    shouldShowQaEmptyState([
      { role: 'system', content: '欢迎' },
      { role: 'user', content: '帮我分析财报' },
    ]),
    false,
  );
});

test('shouldShowQaEmptyState handles non-array and empty inputs', () => {
  assert.equal(shouldShowQaEmptyState(null), true);
  assert.equal(shouldShowQaEmptyState(undefined), true);
  assert.equal(shouldShowQaEmptyState([]), true);
});

test('empty state disappears after assistant message', () => {
  assert.equal(
    shouldShowQaEmptyState([
      { role: 'system', content: '欢迎' },
      { role: 'assistant', content: '这里是分析' },
    ]),
    false,
  );
});
