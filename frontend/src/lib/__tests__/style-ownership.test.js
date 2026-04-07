import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const styleCss = readFileSync(resolve(process.cwd(), 'src/style.css'), 'utf8');
const authLayoutVue = readFileSync(resolve(process.cwd(), 'src/layouts/AuthLayout.vue'), 'utf8');
const authViewVue = readFileSync(resolve(process.cwd(), 'src/views/auth/AuthView.vue'), 'utf8');

test('shared stylesheet no longer owns auth-specific selectors', () => {
  assert.doesNotMatch(styleCss, /\.auth-layout(?:__|[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.auth-card(?:__|[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.auth-form(?:__|[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.page-hero--admin(?:[\s,{:])/);
  assert.doesNotMatch(styleCss, /\.ui-card--admin(?:[\s,{:])/);
});

test('auth layout keeps its styles local', () => {
  assert.match(authLayoutVue, /<style scoped>/);
  assert.match(authLayoutVue, /\.auth-layout\b/);
  assert.match(authLayoutVue, /\.auth-layout__brand\b/);
  assert.match(authLayoutVue, /\.auth-layout__panel\b/);
});

test('auth view keeps its card and form styles local', () => {
  assert.match(authViewVue, /<style scoped>/);
  assert.match(authViewVue, /\.auth-card\b/);
  assert.match(authViewVue, /\.auth-card__tab\b/);
  assert.match(authViewVue, /\.auth-form\b/);
  assert.match(authViewVue, /\.auth-form__submit\b/);
});
