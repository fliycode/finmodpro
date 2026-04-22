import { createApiConfig } from './config.js';

const getCookieValue = (name) => {
  if (typeof document === 'undefined') {
    return '';
  }

  return document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith(`${name}=`))
    ?.slice(name.length + 1) || '';
};

const withCsrfHeaders = (headers = {}) => {
  const csrfToken = getCookieValue('csrftoken');
  return csrfToken
    ? {
        ...headers,
        'X-CSRFToken': decodeURIComponent(csrfToken),
      }
    : headers;
};

const ensureCsrfCookie = async (config) => {
  if (getCookieValue('csrftoken')) {
    return;
  }

  await config.fetchJson('/api/auth/csrf', {
    method: 'GET',
    credentials: 'include',
  });
};

export const createAuthApi = (overrides = {}) => {
  const config = createApiConfig(overrides);

  return {
    async login(payload) {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: JSON.stringify({
          username: payload.username,
          password: payload.password,
          remember_me: Boolean(payload.rememberMe),
        }),
      });
    },
    async register(payload) {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/register', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: JSON.stringify({
          username: payload.username,
          password: payload.password,
          email: payload.email,
        }),
      });
    },
    me(options = {}) {
      return config.fetchJson('/api/auth/me', {
        method: 'GET',
        auth: true,
        skipAuthRefresh: options.skipAuthRefresh,
      });
    },
    async refresh() {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(),
      });
    },
    async logout() {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(),
      });
    },
  };
};

export const authApi = createAuthApi();
