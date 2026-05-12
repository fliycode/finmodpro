import test from 'node:test';
import assert from 'node:assert/strict';

import { appRoutes } from '../routes.js';

test('admin route tree includes renamed model log and usage routes', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('llm/logs'));
  assert.ok(childPaths.includes('llm/usage'));
  assert.ok(childPaths.includes('llm/observability'));
  assert.ok(childPaths.includes('llm/costs'));
});

test('admin route tree no longer mounts graph management pages', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('graph'));
  assert.ok(!childPaths.includes('graph/documents'));
  assert.ok(!childPaths.includes('graph/knowledge'));
  assert.ok(!childPaths.includes('graph/search'));
});

test('admin route tree keeps governance pages mounted under admin shell', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('users'));
  assert.ok(childPaths.includes('roles'));
  assert.ok(childPaths.includes('notifications'));
});

test('admin role route uses the role-management title copy', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const rolesRoute = (adminRoute?.children || []).find((route) => route.path === 'roles');

  assert.equal(rolesRoute?.meta?.title, '角色管理');
  assert.deepEqual(rolesRoute?.meta?.breadcrumb, [{ label: '治理审阅' }, { label: '角色管理' }]);
});

test('admin route tree exposes knowledgebase management under admin shell', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('knowledge'));
});
