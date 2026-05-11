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
    async uploadAvatar(file) {
      await ensureCsrfCookie(config);
      const formData = new FormData();
      formData.append('avatar', file);
      return config.fetchJson('/api/auth/me/avatar/', {
        method: 'POST',
        auth: true,
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: formData,
      });
    },
    async updateProfile(payload) {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/me', {
        method: 'PATCH',
        auth: true,
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: JSON.stringify({
          username: payload.username,
          email: payload.email,
        }),
      });
    },
    async changePassword(payload) {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/me/password/', {
        method: 'POST',
        auth: true,
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: JSON.stringify({
          old_password: payload.oldPassword,
          new_password: payload.newPassword,
        }),
      });
    },
    async forgotPassword(payload) {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/forgot-password', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: JSON.stringify({
          username: payload.username,
        }),
      });
    },
    async resetPassword(payload) {
      await ensureCsrfCookie(config);
      return config.fetchJson('/api/auth/reset-password', {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders(),
        body: JSON.stringify({
          token: payload.token,
          new_password: payload.newPassword,
        }),
      });
    },
  };
};

export const authApi = createAuthApi();
