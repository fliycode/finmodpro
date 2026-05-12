import test from 'node:test';
import assert from 'node:assert/strict';

import { createAdminApi } from '../admin.js';
import { authStorage } from '../../lib/auth-storage.js';

test('createAdminApi targets the admin user management endpoints', async () => {
  const calls = [];
  authStorage.saveToken('test-token');
  const adminApi = createAdminApi({
    baseURL: 'http://example.test',
    fetchImpl: async (url, options) => {
      calls.push({ path: new URL(url).pathname, options });
      return {
        ok: true,
        json: async () => ({ ok: true }),
      };
    },
  });

  await adminApi.listUsers();
  await adminApi.listGroups();
  await adminApi.listRoles();
  await adminApi.listPermissions();
  await adminApi.getRole(3);
  await adminApi.createRole({
    name: 'ops_observer',
    permissions: ['view_dashboard', 'view_monitoring'],
  });
  await adminApi.updateRole(3, {
    name: 'ops_operator',
    permissions: ['view_dashboard'],
  });
  await adminApi.restoreRoleDefaults(3);
  await adminApi.deleteRole(3);
  await adminApi.createUser({
    username: 'alice',
    email: 'alice@example.com',
    password: 'secret123',
    groups: ['member'],
  });
  await adminApi.updateUser(8, {
    username: 'alice-updated',
    email: 'alice-updated@example.com',
    groups: ['admin'],
  });
  await adminApi.deleteUser(8);

  assert.deepEqual(
    calls.map((call) => ({ path: call.path, method: call.options.method })),
    [
      { path: '/api/admin/users', method: 'GET' },
      { path: '/api/admin/groups', method: 'GET' },
      { path: '/api/admin/roles', method: 'GET' },
      { path: '/api/admin/permissions', method: 'GET' },
      { path: '/api/admin/roles/3', method: 'GET' },
      { path: '/api/admin/roles/create', method: 'POST' },
      { path: '/api/admin/roles/3', method: 'PATCH' },
      { path: '/api/admin/roles/3/restore-defaults', method: 'POST' },
      { path: '/api/admin/roles/3', method: 'DELETE' },
      { path: '/api/admin/users', method: 'POST' },
      { path: '/api/admin/users/8', method: 'PATCH' },
      { path: '/api/admin/users/8', method: 'DELETE' },
    ],
  );

  authStorage.clear();
});
