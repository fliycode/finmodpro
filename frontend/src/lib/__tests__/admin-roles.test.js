import test from 'node:test';
import assert from 'node:assert/strict';

import {
  decorateRole,
  groupPermissionsCatalog,
  roleMatchesQuery,
  sortRolesByPriority,
} from '../admin-roles.js';

test('sortRolesByPriority keeps system roles ahead of custom roles', () => {
  const roles = sortRolesByPriority([
    { name: 'ops_observer' },
    { name: 'member' },
    { name: 'admin' },
    { name: 'super_admin' },
  ]);

  assert.deepEqual(roles.map((role) => role.name), [
    'super_admin',
    'admin',
    'member',
    'ops_observer',
  ]);
});

test('groupPermissionsCatalog groups permissions by governance domain', () => {
  const groups = groupPermissionsCatalog([
    { codename: 'view_user', name: 'Can view user' },
    { codename: 'view_document', name: 'Can view document' },
    { codename: 'manage_model_config', name: 'Can manage model config' },
  ]);

  assert.deepEqual(groups.map((group) => group.label), [
    '治理与权限',
    '知识资产',
    '模型与评测',
  ]);
});

test('decorateRole applies custom-role fallback description', () => {
  const role = decorateRole({
    name: 'ops_observer',
    role_type: 'custom',
  });

  assert.match(role.description, /自定义角色/);
  assert.equal(role.member_count, 0);
});

test('roleMatchesQuery matches role metadata by keyword', () => {
  assert.equal(
    roleMatchesQuery(
      {
        name: 'ops_observer',
        label: '运维观察员',
        description: '只读监控角色',
        role_type: 'custom',
      },
      '观察',
    ),
    true,
  );
  assert.equal(
    roleMatchesQuery(
      {
        name: 'ops_observer',
        label: '运维观察员',
        description: '只读监控角色',
        role_type: 'custom',
      },
      '风控',
    ),
    false,
  );
});
