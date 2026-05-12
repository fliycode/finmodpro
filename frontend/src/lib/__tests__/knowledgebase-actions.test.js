import test from 'node:test';
import assert from 'node:assert/strict';

import { getIngestionAction, isIngestionInFlight } from '../knowledgebase-actions.js';

test('isIngestionInFlight treats cleaning as an active process step', () => {
  const inFlight = isIngestionInFlight({
    processStep: { code: 'cleaning' },
    latestTask: { status: 'running' },
  });

  assert.equal(inFlight, true);
});

test('getIngestionAction hides reingest action while cleaning is active', () => {
  const action = getIngestionAction({
    processStep: { code: 'cleaning' },
    latestTask: { status: 'running' },
    status: 'cleaning',
  });

  assert.equal(action, null);
});
