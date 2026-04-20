import test from 'node:test';
import assert from 'node:assert/strict';

import { getNavItems } from '../navigation.js';

test('workspace nav hides admin entries for analyst', () => {
  const items = getNavItems('workspace', { groups: ['analyst'], permissions: [] });

  assert.equal(items.some((item) => item.id === 'admin-overview'), false);
  assert.equal(items.some((item) => item.id === 'qa'), true);
  assert.equal(items.some((item) => item.id === 'sentiment'), true);
});

test('admin nav is available to admin profile', () => {
  const items = getNavItems('admin', { groups: ['admin'], permissions: ['admin'] });

  assert.equal(items.some((item) => item.id === 'admin-overview'), true);
  assert.deepEqual(
    items.filter((item) => item.group === 'admin-llm').map((item) => item.to),
    [
      '/admin/llm',
      '/admin/llm/models',
      '/admin/llm/observability',
      '/admin/llm/knowledge',
      '/admin/llm/fine-tunes',
    ],
  );
  assert.equal(items.some((item) => item.to === '/admin/models'), false);
});
