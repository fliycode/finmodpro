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

export const chatApi = {
  // List chat history
  async listHistory() {
    // TODO: Backend does not have GET /api/chat/sessions yet.
    // Return empty array for now instead of fake data.
    return [];
  },

  // Create a new session
  async createSession(title = '新会话') {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/chat/sessions`), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ title }),
    });
    const data = await parseResponse(response);
    return data.session;
  },
  
  // Get a single chat session
  async getSession(sessionId) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/chat/sessions/${sessionId}`), {
      method: 'GET',
      headers: getHeaders(),
    });
    const data = await parseResponse(response);
    const session = data.session || {};
    
    const rawMessages = session.messages || [];
    return {
      id: session.id || sessionId,
      title: session.title,
      messages: rawMessages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    };
  }
};
