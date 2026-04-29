import test from 'node:test';
import assert from 'node:assert/strict';

import { getSidebarPresentation } from '../workspace-shell.js';

test('workspace sidebar uses editorial presentation', () => {
  assert.deepStrictEqual(getSidebarPresentation('workspace'), {
    mode: 'editorial',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  });
});

test('workspace presentation is no longer a rail', () => {
  const presentation = getSidebarPresentation('workspace');

  assert.strictEqual(presentation.mode, 'editorial');
  assert.notStrictEqual(presentation.mode, 'rail');
  assert.strictEqual(presentation.showItemLabels, true);
});

test('admin sidebar switches to dense war-room navigation', () => {
  assert.deepStrictEqual(getSidebarPresentation('admin'), {
    mode: 'dense',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  });
});
