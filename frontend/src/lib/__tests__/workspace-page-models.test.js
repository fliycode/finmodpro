import test from 'node:test';
import assert from 'node:assert/strict';

import { getWorkspacePageModel } from '../workspace-page-models.js';

test('qa page uses conversation, dossier, and evidence regions in order', () => {
  const model = getWorkspacePageModel('qa');

  assert.deepEqual(model.regions.map((region) => region.id), [
    'conversation',
    'dossier',
    'evidence',
  ]);
});

test('mobile qa mode switches to chapter tabs instead of stacked cards', () => {
  const model = getWorkspacePageModel('qa');

  assert.equal(model.mobileMode, 'chapter-tabs');
});

test('qa page labels the mobile chapters in dossier order', () => {
  const model = getWorkspacePageModel('qa');

  assert.deepEqual(model.regions.map((region) => region.label), ['会话', '结论', '证据']);
});

test('knowledge page keeps filters before ledger before inspector', () => {
  const model = getWorkspacePageModel('knowledge');

  assert.deepEqual(model.regions.map((region) => region.id), ['filters', 'ledger', 'inspector']);
});

test('risk page leads with summary before evidence and actions', () => {
  const model = getWorkspacePageModel('risk');

  assert.deepEqual(model.regions.map((region) => region.id), ['summary', 'evidence', 'actions']);
});

test('history page remains a support surface with filters and records only', () => {
  const model = getWorkspacePageModel('history');

  assert.deepEqual(model.regions.map((region) => region.id), ['filters', 'records']);
});

test('profile page uses identity before access details', () => {
  const model = getWorkspacePageModel('profile');

  assert.deepEqual(model.regions.map((region) => region.id), ['identity', 'access']);
});
