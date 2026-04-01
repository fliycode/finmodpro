import test from 'node:test';
import assert from 'node:assert/strict';

import { getTopbarActions } from '../navigation.js';

const adminProfile = { groups: ['admin'], permissions: ['admin'] };
const analystProfile = { groups: ['analyst'], permissions: [] };

test('workspace topbar includes admin switch and logout for admin profile', () => {
  const actions = getTopbarActions('workspace', adminProfile);
  assert.deepEqual(actions.map((item) => item.id), ['go-admin', 'logout']);
});

test('admin topbar includes workspace switch and logout for admin profile', () => {
  const actions = getTopbarActions('admin', adminProfile);
  assert.deepEqual(actions.map((item) => item.id), ['go-workspace', 'logout']);
});

test('workspace topbar only includes logout for non-admin profile', () => {
  const actions = getTopbarActions('workspace', analystProfile);
  assert.deepEqual(actions.map((item) => item.id), ['logout']);
});
