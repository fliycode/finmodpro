import test from 'node:test';
import assert from 'node:assert/strict';

import { appRoutes, getDefaultRouteForRole } from '../routes.js';
import { resolveEntryRoute } from '../../lib/session-state.js';

test('business user lands on workspace qa', () => {
  assert.equal(
    getDefaultRouteForRole({ groups: ['analyst'], permissions: [] }),
    '/workspace/qa',
  );
});

test('admin lands on admin overview', () => {
  assert.equal(
    getDefaultRouteForRole({ groups: ['admin'], permissions: ['admin'] }),
    '/admin/overview',
  );
});

test('entry route sends anonymous users to login', () => {
  assert.equal(resolveEntryRoute(null, { groups: ['admin'], permissions: ['admin'] }), '/login');
});

test('entry route sends authenticated admins to admin overview', () => {
  assert.equal(resolveEntryRoute('token', { groups: ['admin'], permissions: ['admin'] }), '/admin/overview');
});

test('route table exposes login workspace and admin branches', () => {
  const paths = appRoutes.map((route) => route.path);
  assert.deepEqual(paths, ['/login', '/', '/workspace', '/admin', '/:pathMatch(.*)*']);
});

test('workspace branch exposes qa knowledge history and risk', () => {
  const workspace = appRoutes.find((route) => route.path === '/workspace');
  const childPaths = workspace.children.map((child) => child.path);

  assert.deepEqual(childPaths, ['qa', 'knowledge', 'history', 'risk']);
});

test('admin branch exposes overview users models evaluation', () => {
  const admin = appRoutes.find((route) => route.path === '/admin');
  const childPaths = admin.children.map((child) => child.path);

  assert.deepEqual(childPaths, ['overview', 'users', 'models', 'evaluation']);
});
