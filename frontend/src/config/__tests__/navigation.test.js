import test from 'node:test';
import assert from 'node:assert/strict';

import { getNavItems } from '../navigation.js';

test('workspace nav hides admin entries for analyst', () => {
  const items = getNavItems('workspace', { groups: ['analyst'], permissions: [] });

  assert.equal(items.some((item) => item.id === 'admin-overview'), false);
  assert.equal(items.some((item) => item.id === 'qa'), true);
});

test('admin nav is available to admin profile', () => {
  const items = getNavItems('admin', { groups: ['admin'], permissions: ['admin'] });

  assert.equal(items.some((item) => item.id === 'admin-overview'), true);
});
