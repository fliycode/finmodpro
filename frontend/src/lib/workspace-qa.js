export function normalizeDatasetId(value) {
  if (value === null || value === undefined || String(value).trim() === '') {
    return null;
  }

  const numericValue = Number(value);
  return Number.isNaN(numericValue) ? String(value).trim() : numericValue;
}

export function getDefaultSessionFilters(datasetQueryValue) {
  const datasetId = normalizeDatasetId(datasetQueryValue);
  return datasetId === null ? {} : { dataset_id: datasetId };
}

const SESSION_TITLE_STATUS_LABELS = {
  pending: '标题生成中',
  ready: '标题已生成',
  failed: '标题生成失败',
};

const SESSION_TITLE_SOURCE_LABELS = {
  ai: 'AI 标题',
  manual: '手动标题',
  legacy: '历史标题',
  system: '系统标题',
};

const normalizeCount = (value) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : 0;
};

export function formatHistoryTimestamp(value) {
  if (!value) {
    return '最近无更新';
  }

  try {
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(value));
  } catch {
    return '最近无更新';
  }
}

function getActiveSessionLabel(sessionOptions, currentSessionId) {
  if (!currentSessionId) {
    return '新对话';
  }

  const matched = Array.isArray(sessionOptions)
    ? sessionOptions.find((item) => String(item.id) === String(currentSessionId))
    : null;

  return matched?.title || '当前会话';
}

export function getSessionTitleStatusLabel(status) {
  return SESSION_TITLE_STATUS_LABELS[status] || '标题状态未知';
}

export function getSessionTitleSourceLabel(source) {
  return SESSION_TITLE_SOURCE_LABELS[source] || '未知标题来源';
}

export function normalizeHistoryItems(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => {
    const rollingSummary = item.rollingSummary ?? item.rolling_summary ?? '';
    const lastMessagePreview = item.lastMessagePreview ?? item.last_message_preview ?? '';
    const lastMessageAt = item.lastMessageAt ?? item.last_message_at ?? '';
    const updatedAt = item.updatedAt ?? item.updated_at ?? item.timestamp ?? lastMessageAt ?? '';

    return {
      id: item.id ?? item.session_id ?? null,
      title: item.title || '未命名会话',
      preview: lastMessagePreview || rollingSummary || item.lastMessage || '暂无会话内容',
      summaryPreview: rollingSummary || lastMessagePreview || item.lastMessage || '',
      timestamp: formatHistoryTimestamp(lastMessageAt || updatedAt),
      rawTimestamp: lastMessageAt || updatedAt || '',
      updatedAt: updatedAt || '',
      titleStatus: item.titleStatus ?? item.title_status ?? 'pending',
      titleSource: item.titleSource ?? item.title_source ?? 'ai',
      rollingSummary,
      messageCount: normalizeCount(item.messageCount ?? item.message_count ?? 0),
      lastMessageAt: lastMessageAt || null,
      contextFilters: item.contextFilters || item.context_filters || {},
    };
  });
}

export function buildHistoryQuery({ datasetId = null, keyword = '' } = {}) {
  const params = new URLSearchParams();

  if (datasetId !== null && datasetId !== undefined && String(datasetId).trim() !== '') {
    params.set('dataset_id', String(datasetId).trim());
  }

  const normalizedKeyword = String(keyword || '').trim();
  if (normalizedKeyword) {
    params.set('keyword', normalizedKeyword);
  }

  return params.toString();
}

export function buildSessionExportDownload(payload = {}) {
  const sessionId = payload?.session?.id ?? 'session';
  return {
    filename: `chat-session-${sessionId}.json`,
    content: JSON.stringify(payload, null, 2),
  };
}

// NOTE: The boolean flags below describe chrome elements that were removed from the UI.
// They are intentionally retained to preserve the returned shape (tests/specs rely on it)
// and to document reserved flags for future toolbar expansion.
export function getQaChromeState() {
  return {
    showEyebrow: false,
    showSessionState: false,
    showSessionMeta: false,
    showSessionSummary: false,
    actions: ['history', 'memory', 'new'],
  };
}

export function shouldShowQaEmptyState(messages) {
  if (!Array.isArray(messages)) {
    return true;
  }

  return !messages.some((message) => message?.role === 'user' || message?.role === 'assistant');
}

export function shouldShowFinancialQaEmptyState({ currentSessionId = null, messages } = {}) {
  return !currentSessionId && shouldShowQaEmptyState(messages);
}

export function getSessionLoadFailureNotice(activeSessionLoadFailed) {
  return activeSessionLoadFailed
    ? '会话加载失败，当前仅显示系统状态。请刷新页面后重试。'
    : '';
}

export function updateMessageAt(messages, index, patch = {}) {
  if (!Array.isArray(messages) || index < 0 || index >= messages.length) {
    return Array.isArray(messages) ? [...messages] : [];
  }

  return messages.map((message, messageIndex) => (
    messageIndex === index ? { ...message, ...patch } : message
  ));
}

export function getCitationDisclosureLabel(citations = []) {
  const count = Array.isArray(citations) ? citations.length : 0;
  return count > 0 ? `引用依据（${count} 条）` : '引用依据';
}
