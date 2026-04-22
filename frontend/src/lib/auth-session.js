import { authApi } from '../api/auth.js';
import { registerAuthRefreshHandler } from '../api/config.js';
import { authStorage } from './auth-storage.js';

export const createAuthSession = ({
  authApi: api = authApi,
  authStorage: storage = authStorage,
  registerAuthRefreshHandler: registerRefreshHandler = registerAuthRefreshHandler,
} = {}) => {
  let bootstrapPromise = null;
  let refreshPromise = null;

  const syncProfile = async (options = {}) => {
    const profile = await api.me(options);
    storage.saveProfile(profile);
    return profile;
  };

  const refreshSession = async () => {
    if (refreshPromise) {
      return refreshPromise;
    }

    refreshPromise = (async () => {
      try {
        const response = await api.refresh();
        if (!response?.access_token) {
          throw new Error('Missing access token');
        }

        storage.saveToken(response.access_token);
        await syncProfile({ skipAuthRefresh: true });
        return true;
      } catch {
        storage.clear();
        return false;
      } finally {
        refreshPromise = null;
      }
    })();

    return refreshPromise;
  };

  const ensureSession = async () => {
    if (storage.getToken()) {
      return true;
    }

    if (bootstrapPromise) {
      return bootstrapPromise;
    }

    bootstrapPromise = (async () => {
      const refreshed = await refreshSession();
      return refreshed;
    })();

    try {
      return await bootstrapPromise;
    } finally {
      bootstrapPromise = null;
    }
  };

  const login = async (payload) => {
    const response = await api.login(payload);
    if (!response?.access_token) {
      throw new Error('登录失败，请重试');
    }

    storage.saveToken(response.access_token);
    const profile = await syncProfile({ skipAuthRefresh: true });
    return { response, profile };
  };

  const register = async (payload) => api.register(payload);

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      storage.clear();
    }
  };

  registerRefreshHandler(refreshSession);

  return {
    ensureSession,
    refreshSession,
    login,
    logout,
    register,
  };
};

export const authSession = createAuthSession();
