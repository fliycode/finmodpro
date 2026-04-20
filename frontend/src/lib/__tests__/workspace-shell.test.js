import test from 'node:test';
import assert from 'node:assert/strict';

import { getSidebarPresentation } from '../workspace-shell.js';

const expectedPresentation = {
  mode: 'expanded',
  showBrandCopy: true,
  showGroupLabels: true,
  showItemLabels: true,
};

test('workspace sidebar uses expanded labels on desktop', () => {
  assert.deepStrictEqual(getSidebarPresentation('workspace'), expectedPresentation);
});

test('workspace presentation is no longer a rail', () => {
  const presentation = getSidebarPresentation('workspace');

  assert.equal(presentation.mode, 'expanded');
  assert.equal(presentation.showItemLabels, true);
});

test('admin sidebar keeps the default expanded presentation', () => {
  assert.deepStrictEqual(getSidebarPresentation('admin'), expectedPresentation);
});
