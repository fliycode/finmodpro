import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const styleCss = readFileSync(resolve(process.cwd(), 'src/style.css'), 'utf8');
const authLayoutVue = readFileSync(resolve(process.cwd(), 'src/layouts/AuthLayout.vue'), 'utf8');
const authLandingVue = readFileSync(resolve(process.cwd(), 'src/components/AuthLanding.vue'), 'utf8');

test('shared stylesheet no longer owns auth-specific selectors', () => {
  assert.doesNotMatch(styleCss, /\.auth-layout(?:__|[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.auth-card(?:__|[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.auth-form(?:__|[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.page-hero--admin(?:[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.ui-card--admin(?:[\s,{:])/);
});

test('auth layout stays a thin router shell', () => {
  assert.match(authLayoutVue, /<RouterView \/>/);
  assert.doesNotMatch(authLayoutVue, /<style scoped>/);
});

test('auth landing keeps auth-specific shell and form styles local', () => {
  assert.match(authLandingVue, /<style scoped>/);
  assert.match(authLandingVue, /\.auth-entry\b/);
  assert.match(authLandingVue, /\.brand-column\b/);
  assert.match(authLandingVue, /\.form-card\b/);
  assert.match(authLandingVue, /\.auth-form\b/);
});
