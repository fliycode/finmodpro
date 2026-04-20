import test from 'node:test';
import assert from 'node:assert/strict';

import { getSidebarPresentation } from '../workspace-shell.js';

test('workspace sidebar uses expanded labels on desktop', () => {
  assert.deepEqual(getSidebarPresentation('workspace'), {
    mode: 'expanded',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  });
});

test('admin sidebar keeps the default expanded presentation', () => {
  assert.deepEqual(getSidebarPresentation('admin'), {
    mode: 'expanded',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  });
});
