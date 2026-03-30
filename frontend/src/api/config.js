const FALLBACK_BASE_URL = 'http://localhost:8000';

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

  const defaultFallback = isProd ? '' : 'http://localhost:8000';
  const resolvedBaseURL = overrides.baseURL || envBaseUrl || defaultFallback;
  const baseURL = (
    !overrides.baseURL && isProd && shouldUseSameOriginProxy(resolvedBaseURL, browserLocation)
      ? ''
      : resolvedBaseURL
  ).replace(/\/+$/, '');
  
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
