import test from 'node:test';
import assert from 'node:assert/strict';

import { createFlashStore, pushFlash } from '../flash.js';

test('pushFlash appends a visible message', () => {
  const store = createFlashStore();

  pushFlash(store, { type: 'error', message: '上传失败' });

  assert.equal(store.items.length, 1);
  assert.equal(store.items[0].message, '上传失败');
});

test('pushFlash can queue multiple messages', () => {
  const store = createFlashStore();

  pushFlash(store, { type: 'success', message: '保存成功' });
  pushFlash(store, { type: 'error', message: '上传失败' });

  assert.equal(store.items.length, 2);
});
