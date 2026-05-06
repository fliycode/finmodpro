import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeDocument } from '../knowledgebase.js';

test('normalizeDocument does not mark parsed documents without ingestion task as parsing', () => {
  const document = normalizeDocument({
    id: 3,
    title: 'annual-report.pdf',
    status: 'parsed',
    latest_ingestion_task: null,
  });

  assert.equal(document.processStep.code, 'uploaded');
  assert.equal(document.processStep.label, '已上传');
});

test('normalizeDocument exposes graph sync progress and errors', () => {
  const document = normalizeDocument({
    id: 4,
    title: 'graph-sync-report.pdf',
    status: 'indexed',
    latest_ingestion_task: {
      status: 'running',
      current_step: 'graph_sync',
      graph_sync_status: 'running',
      graph_sync_error_message: '',
    },
  });

  assert.equal(document.processStep.code, 'graph-sync');
  assert.equal(document.processStep.label, '图谱同步中');
});
