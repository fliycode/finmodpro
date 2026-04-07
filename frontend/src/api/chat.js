import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

const normalizeSession = (payload, fallbackSessionId = null) => {
  const session = payload?.session ?? payload?.data?.session ?? payload?.data ?? payload ?? {};

  if (!session || typeof session !== 'object' || Array.isArray(session)) {
    return null;
  }

  return {
    ...session,
    id: session.id ?? session.session_id ?? session.sessionId ?? fallbackSessionId ?? null,
    title: session.title ?? session.name ?? '新会话',
    messages: Array.isArray(session.messages) ? session.messages : [],
  };
};

export const chatApi = {
  async listHistory() {
    const data = await apiConfig.fetchJson('/api/chat/sessions', {
      method: 'GET',
      auth: true,
    });

    const sessions = data?.data?.sessions ?? data?.sessions ?? [];
    return Array.isArray(sessions)
      ? sessions.map((session) => ({
          id: session.id ?? session.session_id ?? null,
          title: session.title ?? session.name ?? '新会话',
          lastMessagePreview: session.last_message_preview ?? '',
          updatedAt: session.updated_at ?? session.updatedAt ?? '',
        }))
      : [];
  },

  async createSession(title = '新会话') {
    const data = await apiConfig.fetchJson('/api/chat/sessions', {
      method: 'POST',
      auth: true,
      body: JSON.stringify({ title }),
    });

    return normalizeSession(data);
  },

  async getSession(sessionId) {
    const data = await apiConfig.fetchJson(`/api/chat/sessions/${sessionId}`, {
      method: 'GET',
      auth: true,
    });
    const session = normalizeSession(data, sessionId) || {
      id: sessionId,
      title: '未命名会话',
      messages: [],
    };

    return {
      id: session.id,
      title: session.title,
      messages: session.messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      })),
    };
  },
};
