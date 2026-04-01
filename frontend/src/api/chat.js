import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

export const chatApi = {
  async listHistory() {
    return [];
  },

  async createSession(title = '新会话') {
    const data = await apiConfig.fetchJson('/api/chat/sessions', {
      method: 'POST',
      auth: true,
      body: JSON.stringify({ title }),
    });
    return data.session;
  },

  async getSession(sessionId) {
    const data = await apiConfig.fetchJson(`/api/chat/sessions/${sessionId}`, {
      method: 'GET',
      auth: true,
    });
    const session = data.session || {};
    const rawMessages = session.messages || [];

    return {
      id: session.id || sessionId,
      title: session.title,
      messages: rawMessages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      })),
    };
  },
};
