import { AUTH_EXPIRED_MESSAGE, authStorage } from '../lib/auth-storage.js';

const FALLBACK_BASE_URL = 'http://localhost:8000';
let authRefreshHandler = null;

const isPrivateIpv4Host = (host) => {
  const parts = String(host || '').split('.').map(Number);
  if (parts.length !== 4 || parts.some((part) => Number.isNaN(part) || part < 0 || part > 255)) {
    return false;
  }

  if (parts[0] === 10 || parts[0] === 127) {
    return true;
  }

  if (parts[0] === 192 && parts[1] === 168) {
    return true;
  }

  return parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31;
};

const isPrivateOrLoopbackHost = (host) => {
  const normalizedHost = String(host || '').trim().toLowerCase();

  if (!normalizedHost) {
    return false;
  }

  return normalizedHost === 'localhost' || normalizedHost === '::1' || isPrivateIpv4Host(normalizedHost);
};

const shouldUseSameOriginProxy = (baseURL, browserLocation) => {
  if (!baseURL || !browserLocation || !browserLocation.hostname) {
    return false;
  }

  try {
    const resolvedUrl = new URL(baseURL, browserLocation.origin);
    return (
      resolvedUrl.hostname !== browserLocation.hostname &&
      isPrivateOrLoopbackHost(resolvedUrl.hostname)
    );
  } catch {
    return false;
  }
};

export const joinUrl = (baseURL, path) => {
  const normalizedBase = String(baseURL || '').replace(/\/+$/, '');
  const normalizedPath = String(path || '').replace(/^\/+/, '');

  return `${normalizedBase}/${normalizedPath}`;
};

const handleUnauthorized = (browserWindow) => {
  authStorage.clear();
  authStorage.saveFlashMessage(AUTH_EXPIRED_MESSAGE);

  if (!browserWindow) {
    return;
  }

  if (typeof browserWindow.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
    browserWindow.dispatchEvent(new CustomEvent('finmodpro:auth-expired', {
      detail: { message: AUTH_EXPIRED_MESSAGE },
    }));
  }

  if (browserWindow.location && browserWindow.location.pathname !== '/login' && typeof browserWindow.location.replace === 'function') {
    browserWindow.location.replace('/login');
  }
};

export const registerAuthRefreshHandler = (handler) => {
  authRefreshHandler = handler;
};

export const createApiConfig = (overrides = {}) => {
  const isProd =
    overrides.isProd ??
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.PROD);
  const envBaseUrl =
    overrides.envBaseUrl ??
    (typeof import.meta !== 'undefined' &&
    import.meta.env &&
    typeof import.meta.env.VITE_API_BASE_URL === 'string'
      ? import.meta.env.VITE_API_BASE_URL
      : '');
  const browserLocation =
    overrides.browserLocation ??
    (typeof window !== 'undefined' && window.location ? window.location : null);
  const browserWindow =
    overrides.browserWindow ??
    (typeof window !== 'undefined' ? window : null);

  const defaultFallback = isProd ? '' : 'http://localhost:8000';
  const resolvedBaseURL = overrides.baseURL || envBaseUrl || defaultFallback;
  const baseURL = (
    !overrides.baseURL && isProd && shouldUseSameOriginProxy(resolvedBaseURL, browserLocation)
      ? ''
      : resolvedBaseURL
  ).replace(/\/+$/, '');

  const selectedFetch = overrides.fetchImpl || fetch;

  const getAuthHeaders = (headers = {}) => {
    const token = authStorage.getToken();
    const resolvedHeaders = {
      'Content-Type': 'application/json',
      ...(overrides.headers || {}),
      ...headers,
    };

    if (token) {
      resolvedHeaders.Authorization = `Bearer ${token}`;
    }

    return resolvedHeaders;
  };

  const buildRequestOptions = (options = {}) => {
    const requestHeaders = options.auth
      ? getAuthHeaders(options.headers)
      : {
          'Content-Type': 'application/json',
          ...(overrides.headers || {}),
          ...(options.headers || {}),
        };

    // For FormData bodies, let the browser set Content-Type with boundary.
    if (options.body instanceof FormData) {
      delete requestHeaders['Content-Type'];
    }

    return {
      ...options,
      headers: requestHeaders,
      credentials: options.credentials,
    };
  };

  const request = async (path, options = {}) => {
    const url = joinUrl(baseURL, path);
    let response = await selectedFetch(url, buildRequestOptions(options));

    if (
      response.status === 401
      && options.auth
      && !options.skipAuthRefresh
      && typeof authRefreshHandler === 'function'
    ) {
      const refreshed = await authRefreshHandler();
      if (refreshed) {
        response = await selectedFetch(
          url,
          buildRequestOptions({ ...options, skipAuthRefresh: true }),
        );
      }
    }

    if (response.status === 401 && options.auth) {
      handleUnauthorized(browserWindow);
    }

    return response;
  };

const parseJson = async (response) => response.json().catch(() => ({}));

  const collectErrorDetails = (value, path = '') => {
    if (Array.isArray(value)) {
      return value.flatMap((item) => collectErrorDetails(item, path));
    }

    if (value && typeof value === 'object') {
      return Object.entries(value).flatMap(([key, nestedValue]) => {
        const nextPath = path ? `${path}.${key}` : key;
        return collectErrorDetails(nestedValue, nextPath);
      });
    }

    if (value === null || value === undefined || value === '') {
      return [];
    }

    return [path ? `${path}: ${String(value)}` : String(value)];
  };

  const buildErrorMessage = (data, fallbackMessage) => {
    const baseMessage = data?.message || data?.error || fallbackMessage;
    const details = collectErrorDetails(data?.data);
    if (details.length === 0) {
      return baseMessage;
    }
    return `${baseMessage} ${details.join(' ; ')}`;
  };

  const fetchJson = async (path, options = {}) => {
    const response = await request(path, options);
    const data = await parseJson(response);

    if (!response.ok) {
      if (response.status === 401 && options.auth) {
        throw new Error(AUTH_EXPIRED_MESSAGE);
      }
      throw new Error(buildErrorMessage(data, '请求失败，请稍后重试'));
    }

    return data;
  };

  return {
    baseURL,
    headers: {
      'Content-Type': 'application/json',
      ...(overrides.headers || {}),
    },
    fetchImpl: selectedFetch,
    fetchWithAuth: request,
    fetchJson,
    getAuthHeaders,
  };
};
