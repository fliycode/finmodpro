const FALLBACK_BASE_URL = 'http://localhost:8000';

export const joinUrl = (baseURL, path) => {
  const normalizedBase = String(baseURL || '').replace(/\/+$/, '');
  const normalizedPath = String(path || '').replace(/^\/+/, '');

  return `${normalizedBase}/${normalizedPath}`;
};

export const createApiConfig = (overrides = {}) => {
  const isProd = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.PROD;
  const envBaseUrl =
    typeof import.meta !== 'undefined' &&
    import.meta.env &&
    typeof import.meta.env.VITE_API_BASE_URL === 'string'
      ? import.meta.env.VITE_API_BASE_URL
      : '';

  const defaultFallback = isProd ? '' : 'http://localhost:8000';
  const baseURL = (overrides.baseURL || envBaseUrl || defaultFallback).replace(/\/+$/, '');
  
  const selectedFetch = overrides.fetchImpl || fetch;

  return {
    baseURL,
    headers: {
      'Content-Type': 'application/json',
      ...(overrides.headers || {}),
    },
    // Wrap fetch to avoid "Illegal invocation" due to incorrect `this` context
    fetchImpl: (url, options) => selectedFetch(url, options),
  };
};
