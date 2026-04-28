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
