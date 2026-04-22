import test from 'node:test';
import assert from 'node:assert/strict';

import { authStorage } from '../auth-storage.js';

const createStorage = () => {
  const store = new Map();

  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
  };
};

const installStorages = () => {
  globalThis.localStorage = createStorage();
  globalThis.sessionStorage = createStorage();
};

test.beforeEach(() => {
  installStorages();
});

test('saveToken keeps access tokens in memory only', () => {
  authStorage.saveToken('session-token');

  assert.equal(sessionStorage.getItem('finmodpro_token'), null);
  assert.equal(localStorage.getItem('finmodpro_token'), null);
  assert.equal(authStorage.getToken(), 'session-token');
});

test('saveProfile keeps profile in memory only', () => {
  authStorage.saveProfile(
    {
      id: 1,
      username: 'alice',
      email: 'alice@example.com',
      groups: ['member'],
      permissions: ['view_dashboard'],
    },
  );

  assert.deepEqual(authStorage.getProfile(), {
    user: {
      id: 1,
      username: 'alice',
      email: 'alice@example.com',
    },
    groups: ['member'],
    permissions: ['view_dashboard'],
  });
  assert.equal(localStorage.getItem('finmodpro_user'), null);
  assert.equal(sessionStorage.getItem('finmodpro_user'), null);
});

test('clear removes in-memory auth data without touching flash storage', () => {
  authStorage.saveFlashMessage('flash');
  authStorage.saveToken('session-token');
  authStorage.saveProfile(
    {
      id: 1,
      username: 'alice',
      email: 'alice@example.com',
      groups: ['member'],
      permissions: ['view_dashboard'],
    },
  );
  authStorage.clear();

  assert.equal(localStorage.getItem('finmodpro_token'), null);
  assert.equal(sessionStorage.getItem('finmodpro_token'), null);
  assert.deepEqual(authStorage.getProfile(), {
    user: {},
    groups: [],
    permissions: [],
  });
  assert.equal(localStorage.getItem('finmodpro_flash_message'), 'flash');
});
