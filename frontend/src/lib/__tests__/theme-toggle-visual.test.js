import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../../components/ui/ThemeToggle.vue');

const readThemeToggle = () => readFileSync(componentPath, 'utf8');

test('theme toggle uses sun for the active light state and moon for the active dark state', () => {
  const source = readThemeToggle();

  assert.match(source, /theme-toggle__sun/);
  assert.match(source, /theme-toggle__moon/);
  assert.doesNotMatch(source, /isDark\.value \? 'sun' : 'moon'/);
});
