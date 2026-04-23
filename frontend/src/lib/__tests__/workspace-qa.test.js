import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getSessionLoadFailureNotice,
  getQaChromeState,
  getCitationDisclosureLabel,
  updateMessageAt,
  shouldShowFinancialQaEmptyState,
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

test('qa chrome action order matches the simplified toolbar', () => {
  assert.deepEqual(getQaChromeState().actions, ['history', 'memory', 'new']);
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

test('financial qa empty state only shows for fresh conversations', () => {
  assert.equal(
    shouldShowFinancialQaEmptyState({
      currentSessionId: null,
      messages: [{ role: 'system', content: '欢迎' }],
    }),
    true,
  );
  assert.equal(
    shouldShowFinancialQaEmptyState({
      currentSessionId: 'session-1',
      messages: [{ role: 'system', content: '已加载会话：空会话' }],
    }),
    false,
  );
});

test('session load failure notice is only surfaced when a load fails', () => {
  assert.equal(getSessionLoadFailureNotice(false), '');
  assert.equal(getSessionLoadFailureNotice(true), '会话加载失败，当前仅显示系统状态。请刷新页面后重试。');
});

test('streaming message updates replace the array item to trigger reactivity', () => {
  const original = [
    { role: 'user', content: 'Q' },
    { role: 'assistant', content: '', isStreaming: true },
  ];

  const updated = updateMessageAt(original, 1, { content: 'partial answer' });

  assert.notEqual(updated, original);
  assert.notEqual(updated[1], original[1]);
  assert.deepEqual(updated[1], {
    role: 'assistant',
    content: 'partial answer',
    isStreaming: true,
  });
});

test('citation disclosure label summarizes hidden evidence', () => {
  assert.equal(getCitationDisclosureLabel([]), '引用依据');
  assert.equal(getCitationDisclosureLabel([{ document_title: 'A' }]), '引用依据（1 条）');
  assert.equal(
    getCitationDisclosureLabel([{ document_title: 'A' }, { document_title: 'B' }]),
    '引用依据（2 条）',
  );
});
