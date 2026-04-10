import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AUTH_BRAND_STATEMENT,
  buildBrandStatementSegments,
  getPasswordToggleLabel,
} from '../auth-landing.js';

test('buildBrandStatementSegments highlights 文档 问答 模型 in order', () => {
  const segments = buildBrandStatementSegments(AUTH_BRAND_STATEMENT);

  assert.deepEqual(
    segments.filter((item) => item.emphasis).map((item) => item.text),
    ['文档', '问答', '模型'],
  );
});

test('buildBrandStatementSegments preserves the original statement when joined', () => {
  const segments = buildBrandStatementSegments(AUTH_BRAND_STATEMENT);

  assert.equal(segments.map((item) => item.text).join(''), AUTH_BRAND_STATEMENT);
});

test('getPasswordToggleLabel returns accessible text for both states', () => {
  assert.equal(getPasswordToggleLabel(false), '显示密码');
  assert.equal(getPasswordToggleLabel(true), '隐藏密码');
});
