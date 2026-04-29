import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getAuthenticatedShellSpec,
  getDestructiveAuditRows,
} from '../authenticated-shell.js';

test('workspace and admin use intentionally different shell personas', () => {
  const workspace = getAuthenticatedShellSpec('workspace');
  const admin = getAuthenticatedShellSpec('admin');

  assert.equal(workspace.persona, 'dossier');
  assert.equal(admin.persona, 'war-room');
  assert.notDeepEqual(workspace.layout, admin.layout);
});

test('destructive audit covers at least six redesign dimensions', () => {
  const rows = getDestructiveAuditRows();

  assert.ok(rows.length >= 6);
  assert.ok(rows.every((row) => row.before && row.after && row.dimension));
});
