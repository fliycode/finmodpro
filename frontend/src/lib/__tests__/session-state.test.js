import test from 'node:test';
import assert from 'node:assert/strict';

import { canAccessRoute, resolveHomeRoute, isAdminProfile } from '../session-state.js';

const admin = { groups: ['admin'], permissions: ['admin'] };
const analyst = { groups: ['analyst'], permissions: [] };

test('resolveHomeRoute returns admin overview for admin', () => {
  assert.equal(resolveHomeRoute(admin), '/admin/overview');
});

test('resolveHomeRoute returns workspace qa for analyst', () => {
  assert.equal(resolveHomeRoute(analyst), '/workspace/qa');
});

test('analyst cannot access admin route', () => {
  assert.equal(canAccessRoute({ meta: { requiresAdmin: true } }, analyst), false);
});

test('admin profile is recognized', () => {
  assert.equal(isAdminProfile(admin), true);
});
