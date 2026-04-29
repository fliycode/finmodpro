import test from 'node:test';
import assert from 'node:assert/strict';

import { navigationMap } from '../navigation.js';

test('admin llm navigation exposes the approved five-page IA', () => {
  const llmItems = navigationMap.admin.filter((item) => item.group === 'admin-llm');

  assert.deepEqual(
    llmItems.map((item) => item.to),
    [
      '/admin/llm',
      '/admin/llm/models',
      '/admin/llm/observability',
      '/admin/llm/costs',
      '/admin/llm/fine-tunes',
    ],
  );
});

test('workspace and admin navigation keep separate grouping vocabularies', () => {
  const workspaceLabels = navigationMap.workspace.map((item) => item.label);
  const adminLabels = navigationMap.admin.map((item) => item.label);
  const workspaceGroups = [...new Set(navigationMap.workspace.map((item) => item.group))];
  const adminGroups = [...new Set(navigationMap.admin.map((item) => item.group))];

  assert.ok(workspaceLabels.includes('智能问答'));
  assert.ok(adminLabels.includes('Gateway'));
  assert.deepEqual(workspaceGroups, ['workspace-core', 'workspace-support']);
  assert.ok(adminGroups.includes('admin-llm'));
  assert.notDeepEqual(workspaceLabels, adminLabels);
});

test('admin navigation still exposes governance pages after the redesign', () => {
  const governanceItems = navigationMap.admin.filter((item) => item.group === 'admin-governance');

  assert.deepEqual(
    governanceItems.map((item) => item.to),
    ['/admin/users', '/admin/evaluation'],
  );
});
