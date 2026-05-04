import test from 'node:test';
import assert from 'node:assert/strict';

import { createFlashStore, FLASH_DURATION_MS, pushFlash } from '../flash.js';

test('pushFlash auto-dismisses page-level messages after the default duration', () => {
  const store = createFlashStore();
  const originalSetTimeout = globalThis.setTimeout;
  const timers = [];

  globalThis.setTimeout = (callback, delay) => {
    timers.push({ callback, delay });
    return timers.length;
  };

  try {
    pushFlash(store, { type: 'warning', message: '请先选择一个标签。' });

    assert.equal(store.items.length, 1);
    assert.equal(store.items[0].type, 'warning');
    assert.equal(timers.length, 1);
    assert.equal(timers[0].delay, FLASH_DURATION_MS);

    timers[0].callback();
    assert.equal(store.items.length, 0);
  } finally {
    globalThis.setTimeout = originalSetTimeout;
  }
});
