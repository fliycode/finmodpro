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

  assert.deepEqual(childPaths, ['qa', 'knowledge', 'history', 'risk', 'sentiment']);
});

test('admin branch exposes overview users models evaluation', () => {
  const admin = appRoutes.find((route) => route.path === '/admin');
  const childPaths = admin.children.map((child) => child.path);

  assert.deepEqual(childPaths, [
    'overview',
    'users',
    'llm',
    'llm/models',
    'llm/observability',
    'llm/knowledge',
    'llm/fine-tunes',
    'models',
    'evaluation',
  ]);
});

test('legacy admin models route redirects to llm models', () => {
  const admin = appRoutes.find((route) => route.path === '/admin');
  const legacyModelsRoute = admin.children.find((child) => child.path === 'models');

  assert.equal(legacyModelsRoute.redirect, '/admin/llm/models');
});

test('llm models and fine-tunes routes use dedicated admin views', () => {
  const admin = appRoutes.find((route) => route.path === '/admin');
  const modelsRoute = admin.children.find((child) => child.path === 'llm/models');
  const fineTunesRoute = admin.children.find((child) => child.path === 'llm/fine-tunes');

  assert.match(String(modelsRoute.component), /AdminLlmModelsView/);
  assert.match(String(fineTunesRoute.component), /AdminLlmFineTunesView/);
});

test('llm overview observability and knowledge routes use dedicated admin views', () => {
  const admin = appRoutes.find((route) => route.path === '/admin');
  const overviewRoute = admin.children.find((child) => child.path === 'llm');
  const observabilityRoute = admin.children.find((child) => child.path === 'llm/observability');
  const knowledgeRoute = admin.children.find((child) => child.path === 'llm/knowledge');

  assert.match(String(overviewRoute.component), /AdminLlmOverviewView/);
  assert.match(String(observabilityRoute.component), /AdminLlmObservabilityView/);
  assert.match(String(knowledgeRoute.component), /AdminLlmKnowledgeView/);
});
