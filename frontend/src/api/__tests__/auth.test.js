import test from 'node:test';
import assert from 'node:assert/strict';

import { createAuthApi } from '../auth.js';

test('login forwards remember_me to the auth endpoint payload', async () => {
  const requests = [];
  const authApi = createAuthApi({
    baseURL: 'http://example.test',
    fetchImpl: async (url, options) => {
      requests.push({
        url,
        options,
      });

      return {
        ok: true,
        json: async () => ({ access_token: 'token' }),
      };
    },
  });

  await authApi.login({
    username: 'alice',
    password: 'secret123',
    rememberMe: true,
  });

  assert.equal(requests.length, 2);
  assert.equal(requests[0].url, 'http://example.test/api/auth/csrf');
  assert.equal(requests[0].options.credentials, 'include');
  assert.equal(requests[1].url, 'http://example.test/api/auth/login');
  assert.equal(requests[1].options.credentials, 'include');
  assert.deepEqual(JSON.parse(requests[1].options.body), {
    username: 'alice',
    password: 'secret123',
    remember_me: true,
  });
});
