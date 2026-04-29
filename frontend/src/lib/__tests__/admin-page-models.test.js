import test from 'node:test';
import assert from 'node:assert/strict';

import { getAdminPageModel } from '../admin-page-models.js';

test('llm overview page uses status band, command deck, and inspector regions', () => {
  const model = getAdminPageModel('llm-overview');

  assert.deepEqual(model.regions.map((region) => region.id), [
    'status-band',
    'command-deck',
    'inspector',
  ]);
});

test('admin mobile mode is triage-stack rather than full dashboard carryover', () => {
  const model = getAdminPageModel('overview');

  assert.equal(model.mobileMode, 'triage-stack');
});

test('governance pages do not reuse the llm operations region order', () => {
  const llm = getAdminPageModel('llm-overview');
  const governance = getAdminPageModel('governance');

  assert.notDeepEqual(llm.regions, governance.regions);
});
