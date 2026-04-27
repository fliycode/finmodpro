import test from 'node:test';
import assert from 'node:assert/strict';

import { appRoutes } from '../routes.js';

test('admin route tree includes the LiteLLM cost page route', () => {
  const adminRoute = appRoutes.find((route) => route.path === '/admin');
  const childPaths = (adminRoute?.children || []).map((route) => route.path);

  assert.ok(childPaths.includes('llm/costs'));
});
