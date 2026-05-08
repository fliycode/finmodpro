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

test('admin route tree splits graph management into child pages', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('graph/documents'));
  assert.ok(childPaths.includes('graph/knowledge'));
  assert.ok(childPaths.includes('graph/search'));
});

test('admin route tree keeps governance pages mounted under admin shell', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('users'));
});

test('admin route tree exposes knowledgebase management under admin shell', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('knowledge'));
});
