import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

const apiConfig = createApiConfig();

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || '请求失败，请稍后重试');
  }
  return data;
};

const getHeaders = () => {
  const token = authStorage.getToken();
  const headers = { ...apiConfig.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const riskApi = {
  // Get risk events
  async getEvents(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        query.append(key, value);
      }
    });
    
    const queryString = query.toString();
    const urlPath = queryString ? `/api/risk/events?${queryString}` : '/api/risk/events';

    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, urlPath), {
      method: 'GET',
      headers: getHeaders(),
    });
    
    return parseResponse(response);
  },

  // Review a risk event
  async reviewEvent(eventId, reviewStatus) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/risk/events/${eventId}/review`), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ review_status: reviewStatus }),
    });

    return parseResponse(response);
  }
};
