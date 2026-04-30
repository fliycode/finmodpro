import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyTheme,
  getStoredTheme,
  initializeTheme,
  persistTheme,
} from '../theme.js';

const createStorage = () => {
  const store = new Map();

  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
  };
};

test.beforeEach(() => {
  globalThis.localStorage = createStorage();
  globalThis.matchMedia = () => ({ matches: false });
  globalThis.document = {
    documentElement: {
      dataset: {},
      style: {},
      classList: {
        classes: new Set(),
        toggle(className, force) {
          if (force) {
            this.classes.add(className);
            return true;
          }
          this.classes.delete(className);
          return false;
        },
        contains(className) {
          return this.classes.has(className);
        },
      },
    },
  };
});

test('persistTheme stores the selected theme', () => {
  persistTheme('dark');

  assert.equal(localStorage.getItem('finmodpro_theme'), 'dark');
  assert.equal(getStoredTheme(), 'dark');
});

test('applyTheme updates the document root', () => {
  applyTheme('dark');

  assert.equal(document.documentElement.dataset.theme, 'dark');
  assert.equal(document.documentElement.style.colorScheme, 'dark');
  assert.equal(document.documentElement.classList.contains('dark'), true);
});

test('initializeTheme prefers the stored theme', () => {
  localStorage.setItem('finmodpro_theme', 'dark');

  initializeTheme();

  assert.equal(document.documentElement.dataset.theme, 'dark');
});

test('initializeTheme defaults to light without a stored preference', () => {
  globalThis.matchMedia = () => ({ matches: true });

  initializeTheme();

  assert.equal(document.documentElement.dataset.theme, 'light');
  assert.equal(document.documentElement.classList.contains('dark'), false);
});
