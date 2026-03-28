import test from 'node:test';
import assert from 'node:assert/strict';

import { createApiConfig, joinUrl } from '../config.js';
import { createAuthApi } from '../auth.js';

test('joinUrl joins baseURL and path cleanly', () => {
  assert.equal(joinUrl('http://localhost:8000/', '/api/auth/login'), 'http://localhost:8000/api/auth/login');
  assert.equal(joinUrl('http://localhost:8000', 'api/auth/register'), 'http://localhost:8000/api/auth/register');
});

test('createApiConfig prefers explicit baseURL and trims trailing slash', () => {
  const config = createApiConfig({
    baseURL: 'http://localhost:9000/',
  });

  assert.equal(config.baseURL, 'http://localhost:9000');
});

test('login sends username and password only', async () => {
  let request;
  const authApi = createAuthApi({
    baseURL: 'http://localhost:8000',
    fetchImpl: async (url, options) => {
      request = {
        url,
        options,
      };

      return {
        ok: true,
        async json() {
          return { message: 'ok' };
        },
      };
    },
  });

  await authApi.login({
    username: 'alice',
    password: 'secret123',
  });

  assert.equal(request.url, 'http://localhost:8000/api/auth/login');
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(request.options.body), {
    username: 'alice',
    password: 'secret123',
  });
});

test('register sends username, password and email', async () => {
  let request;
  const authApi = createAuthApi({
    baseURL: 'http://localhost:8000',
    fetchImpl: async (url, options) => {
      request = {
        url,
        options,
      };

      return {
        ok: true,
        async json() {
          return { message: 'ok' };
        },
      };
    },
  });

  await authApi.register({
    username: 'alice',
    password: 'secret123',
    email: 'alice@example.com',
  });

  assert.equal(request.url, 'http://localhost:8000/api/auth/register');
  assert.deepEqual(JSON.parse(request.options.body), {
    username: 'alice',
    password: 'secret123',
    email: 'alice@example.com',
  });
});

test('failed response throws backend message', async () => {
  const authApi = createAuthApi({
    baseURL: 'http://localhost:8000',
    fetchImpl: async () => ({
      ok: false,
      async json() {
        return { message: '用户名或密码错误' };
      },
    }),
  });

  await assert.rejects(
    () => authApi.login({ username: 'alice', password: 'bad' }),
    /用户名或密码错误/,
  );
});
