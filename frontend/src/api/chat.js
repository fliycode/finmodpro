import { createApiConfig } from './config.js';
import { buildHistoryQuery, normalizeHistoryItems } from '../lib/workspace-qa.js';

const normalizeMessage = (message) => {
  if (!message || typeof message !== 'object' || Array.isArray(message)) {
    return null;
  }

  return {
    id: message.id ?? null,
    sequence: message.sequence ?? null,
    role: message.role ?? 'assistant',
    messageType: message.messageType ?? message.message_type ?? 'text',
    status: message.status ?? 'complete',
    citationsJson: Array.isArray(message.citationsJson ?? message.citations_json)
      ? (message.citationsJson ?? message.citations_json)
      : [],
    modelMetadataJson:
      message.modelMetadataJson && typeof message.modelMetadataJson === 'object'
        ? message.modelMetadataJson
        : (message.model_metadata_json && typeof message.model_metadata_json === 'object'
            ? message.model_metadata_json
            : {}),
    clientMessageId: message.clientMessageId ?? message.client_message_id ?? '',
    content: message.content ?? '',
    createdAt: message.createdAt ?? message.created_at ?? '',
    updatedAt: message.updatedAt ?? message.updated_at ?? '',
  };
};

export const normalizeSession = (payload, fallbackSessionId = null) => {
  const session = payload?.session ?? payload?.data?.session ?? payload?.data ?? payload ?? {};

  if (!session || typeof session !== 'object' || Array.isArray(session)) {
    return null;
  }

  const messageCount = Number(session.messageCount ?? session.message_count ?? 0);

  return {
    id: session.id ?? session.session_id ?? session.sessionId ?? fallbackSessionId ?? null,
    title: session.title ?? session.name ?? '新会话',
    titleStatus: session.titleStatus ?? session.title_status ?? 'pending',
    titleSource: session.titleSource ?? session.title_source ?? 'ai',
    rollingSummary: session.rollingSummary ?? session.rolling_summary ?? '',
    messageCount: Number.isFinite(messageCount) ? messageCount : 0,
    lastMessageAt: session.lastMessageAt ?? session.last_message_at ?? null,
    createdAt: session.createdAt ?? session.created_at ?? '',
    updatedAt: session.updatedAt ?? session.updated_at ?? '',
    messages: Array.isArray(session.messages)
      ? session.messages.map(normalizeMessage).filter(Boolean)
      : [],
    contextFilters: session.contextFilters ?? session.context_filters ?? {},
  };
};

export const createChatApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async listHistory({ datasetId = null, keyword = '' } = {}) {
      const query = buildHistoryQuery({ datasetId, keyword });
      const data = await fetchJson(
        query ? `/api/chat/sessions?${query}` : '/api/chat/sessions',
        {
          method: 'GET',
          auth: true,
        },
      );

      const sessions = data?.data?.sessions ?? data?.sessions ?? [];
      return normalizeHistoryItems(sessions);
    },

    async createSession(options = '新会话') {
      const payload = typeof options === 'string'
        ? { title: options }
        : {
            title: options?.title ?? '新会话',
            context_filters: options?.contextFilters ?? options?.context_filters ?? {},
          };
      const data = await fetchJson('/api/chat/sessions', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      });

      return normalizeSession(data);
    },

    async getSession(sessionId) {
      const data = await fetchJson(`/api/chat/sessions/${sessionId}`, {
        method: 'GET',
        auth: true,
      });
      return normalizeSession(data, sessionId) || {
        id: sessionId,
        title: '新会话',
        titleStatus: 'pending',
        titleSource: 'ai',
        rollingSummary: '',
        messageCount: 0,
        lastMessageAt: null,
        createdAt: '',
        updatedAt: '',
        contextFilters: {},
        messages: [],
      };
    },

    async exportSession(sessionId) {
      return fetchJson(`/api/chat/sessions/${sessionId}/export`, {
        method: 'GET',
        auth: true,
      });
    },
  };
};

export const chatApi = createChatApi();
