import test from 'node:test';
import assert from 'node:assert/strict';

import { createApiConfig } from '../config.js';
import { authStorage } from '../../lib/auth-storage.js';

const originalWindow = globalThis.window;
const originalLocalStorage = globalThis.localStorage;

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

test.afterEach(() => {
  globalThis.window = originalWindow;
  globalThis.localStorage = originalLocalStorage;
});

test('401 protected response clears auth state and redirects to login', async () => {
  const localStorage = createStorage();
  globalThis.localStorage = localStorage;

  const browserWindow = {
    location: {
      pathname: '/admin/models',
      replaceCalls: [],
      replace(url) {
        this.replaceCalls.push(url);
      },
    },
    dispatchEvent(event) {
      this.lastEvent = event;
      return true;
    },
  };
  globalThis.window = browserWindow;
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, init = {}) {
      this.type = type;
      this.detail = init.detail;
    }
  };

  authStorage.saveToken('expired-token');
  authStorage.saveProfile({ id: 1, username: 'admin', groups: ['admin'], permissions: ['admin'] });

  const api = createApiConfig({
    fetchImpl: async () => ({
      ok: false,
      status: 401,
      async json() {
        return { message: '未认证。' };
      },
    }),
  });

  await assert.rejects(() => api.fetchJson('/api/ops/model-configs/', { auth: true }), /登录已过期，请重新登录/);
  assert.equal(authStorage.getToken(), null);
  assert.equal(authStorage.consumeFlashMessage(), '登录已过期，请重新登录');
  assert.deepEqual(browserWindow.location.replaceCalls, ['/login']);
  assert.equal(browserWindow.lastEvent.type, 'finmodpro:auth-expired');
  assert.equal(browserWindow.lastEvent.detail.message, '登录已过期，请重新登录');
});
