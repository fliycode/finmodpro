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
      const user = value?.user || value;
      const id = user?.id ?? value?.id;
      if (id === undefined || id === null) {
        return;
      }
      profile = {
        user: {
          id,
          username: user?.username ?? value?.username ?? '',
          email: user?.email ?? value?.email ?? '',
          avatar_url: user?.avatar_url ?? value?.avatar_url ?? null,
        },
        groups: value?.groups || [],
        permissions: value?.permissions || [],
      };
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
    user: { id: 1, username: 'alice', email: 'alice@example.com', avatar_url: null },
    groups: ['member'],
    permissions: ['view_dashboard'],
  });
});

test('ensureSession reuses the embedded refresh profile when available', async () => {
  const storage = createStorage();
  const authSession = createAuthSession({
    authApi: {
      async refresh() {
        return {
          access_token: 'access-embedded',
          profile: {
            id: 3,
            username: 'carol',
            email: 'carol@example.com',
            groups: ['admin'],
            permissions: ['view_dashboard', 'manage_model_config'],
          },
        };
      },
      async me() {
        throw new Error('refresh should not call me when profile is embedded');
      },
    },
    authStorage: storage,
    registerAuthRefreshHandler() {},
  });

  const authenticated = await authSession.ensureSession();

  assert.equal(authenticated, true);
  assert.equal(storage.getToken(), 'access-embedded');
  assert.deepEqual(storage.getProfile(), {
    user: { id: 3, username: 'carol', email: 'carol@example.com', avatar_url: null },
    groups: ['admin'],
    permissions: ['view_dashboard', 'manage_model_config'],
  });
  assert.ok(authSession);
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

test('login reuses the embedded auth profile when available', async () => {
  const storage = createStorage();
  const authSession = createAuthSession({
    authApi: {
      async login() {
        return {
          access_token: 'login-token',
          profile: {
            id: 4,
            username: 'dave',
            email: 'dave@example.com',
            avatar_url: '/media/avatar.png',
            groups: ['member'],
            permissions: ['ask_financial_qa'],
          },
        };
      },
      async me() {
        throw new Error('login should not call me when profile is embedded');
      },
    },
    authStorage: storage,
    registerAuthRefreshHandler() {},
  });

  const { profile, response } = await authSession.login({
    username: 'dave',
    password: 'secret123',
  });

  assert.equal(response.access_token, 'login-token');
  assert.equal(storage.getToken(), 'login-token');
  assert.deepEqual(profile, {
    id: 4,
    username: 'dave',
    email: 'dave@example.com',
    avatar_url: '/media/avatar.png',
    groups: ['member'],
    permissions: ['ask_financial_qa'],
  });
  assert.deepEqual(storage.getProfile(), {
    user: {
      id: 4,
      username: 'dave',
      email: 'dave@example.com',
      avatar_url: '/media/avatar.png',
    },
    groups: ['member'],
    permissions: ['ask_financial_qa'],
  });
});
