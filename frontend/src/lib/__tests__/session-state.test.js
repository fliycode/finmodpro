import test from 'node:test';
import assert from 'node:assert/strict';

import {
  canAccessRoute,
  isAdminProfile,
  resolveHomeRoute,
} from '../session-state.js';

test('custom role with admin permissions is treated as admin profile', () => {
  const profile = {
    groups: ['ops_observer'],
    permissions: ['view_role'],
  };

  assert.equal(isAdminProfile(profile), true);
  assert.equal(resolveHomeRoute(profile), '/admin/roles');
});

test('canAccessRoute enforces requiredPermissions on admin routes', () => {
  const profile = {
    groups: ['ops_observer'],
    permissions: ['view_role'],
  };

  assert.equal(
    canAccessRoute(
      {
        meta: {
          requiresAdmin: true,
          requiredPermissions: ['view_role'],
        },
      },
      profile,
    ),
    true,
  );

  assert.equal(
    canAccessRoute(
      {
        meta: {
          requiresAdmin: true,
          requiredPermissions: ['view_monitoring'],
        },
      },
      profile,
    ),
    false,
  );
});
