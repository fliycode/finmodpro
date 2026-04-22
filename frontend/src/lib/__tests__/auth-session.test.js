import test from 'node:test';
import assert from 'node:assert/strict';

import { createAuthSession } from '../auth-session.js';

const emptyProfile = () => ({
  user: {},
  groups: [],
  permissions: [],
});

const createStorage = () => {
  let token = null;
  let profile = emptyProfile();

  return {
    saveToken(value) {
      token = value;
    },
    getToken() {
      return token;
    },
    saveProfile(value) {
      profile = value;
    },
    getProfile() {
      return profile;
    },
    clear() {
      token = null;
      profile = emptyProfile();
    },
  };
};

test('ensureSession refreshes access token and loads profile when memory is empty', async () => {
  const storage = createStorage();
  const authSession = createAuthSession({
    authApi: {
      async refresh() {
        return { access_token: 'access-1' };
      },
      async me() {
        return {
          user: { id: 1, username: 'alice', email: 'alice@example.com' },
          groups: ['member'],
          permissions: ['view_dashboard'],
        };
      },
    },
    authStorage: storage,
    registerAuthRefreshHandler() {},
  });

  const authenticated = await authSession.ensureSession();

  assert.equal(authenticated, true);
  assert.equal(storage.getToken(), 'access-1');
  assert.deepEqual(storage.getProfile(), {
    user: { id: 1, username: 'alice', email: 'alice@example.com' },
    groups: ['member'],
    permissions: ['view_dashboard'],
  });
});

test('registered refresh handler reuses the same in-flight refresh request', async () => {
  const storage = createStorage();
  let refreshCalls = 0;
  let refreshHandler = null;
  const authSession = createAuthSession({
    authApi: {
      async refresh() {
        refreshCalls += 1;
        await new Promise((resolve) => setTimeout(resolve, 0));
        return { access_token: 'access-2' };
      },
      async me() {
        return {
          user: { id: 2, username: 'bob', email: 'bob@example.com' },
          groups: ['member'],
          permissions: [],
        };
      },
    },
    authStorage: storage,
    registerAuthRefreshHandler(handler) {
      refreshHandler = handler;
    },
  });

  assert.equal(typeof refreshHandler, 'function');
  const [first, second] = await Promise.all([refreshHandler(), refreshHandler()]);

  assert.equal(first, true);
  assert.equal(second, true);
  assert.equal(refreshCalls, 1);
  assert.equal(storage.getToken(), 'access-2');
  assert.ok(authSession);
});
