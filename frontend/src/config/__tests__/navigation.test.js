import test from 'node:test';
import assert from 'node:assert/strict';

import { navigationMap } from '../navigation.js';

test('admin llm navigation exposes the approved four-page IA', () => {
  const llmItems = navigationMap.admin.filter((item) => item.group === 'admin-llm');

  assert.deepEqual(
    llmItems.map((item) => item.to),
    [
      '/admin/llm',
      '/admin/llm/models',
      '/admin/llm/observability',
      '/admin/llm/costs',
    ],
  );
});
