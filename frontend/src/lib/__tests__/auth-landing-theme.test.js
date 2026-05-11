import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const currentDir = dirname(fileURLToPath(import.meta.url));
const componentPath = resolve(currentDir, '../../components/AuthLanding.vue');

const readComponent = () => readFileSync(componentPath, 'utf8');

test('auth landing defines a dedicated dark theme contract', () => {
  const source = readComponent();

  assert.match(source, /:global\(:root\[data-theme='dark'\]\)\s+\.auth-entry/);
  assert.match(source, /--entry-bg-top:\s*#131c2d/);
  assert.match(source, /--entry-panel-strong:\s*rgba\(24,\s*34,\s*53,\s*0\.96\)/);
  assert.match(source, /linear-gradient\(180deg,\s*var\(--entry-bg-top\)\s*0%,\s*var\(--entry-bg\)\s*100%\)/);
});

test('auth landing action controls do not hard-code light-only neutral fills', () => {
  const source = readComponent();

  assert.match(source, /\.auth-entry \.tab-btn\.active\s*\{\s*background:\s*var\(--entry-tab-active-bg\)/);
  assert.match(source, /\.auth-entry \.primary-button\s*\{[\s\S]*background:\s*var\(--entry-button-bg\)/);
  assert.doesNotMatch(source, /\.tab-btn\.active\s*\{\s*background:\s*#111111/);
  assert.doesNotMatch(source, /\.primary-button\s*\{[\s\S]*background:\s*#111111/);
});
