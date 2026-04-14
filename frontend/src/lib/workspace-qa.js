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

export function getActiveSessionLabel(sessionOptions, currentSessionId) {
  if (!currentSessionId) {
    return '新对话';
  }

  const matched = Array.isArray(sessionOptions)
    ? sessionOptions.find((item) => String(item.id) === String(currentSessionId))
    : null;

  return matched?.title || '当前会话';
}

export function normalizeHistoryItems(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => ({
    id: item.id,
      title: item.title || '未命名会话',
      preview: item.lastMessagePreview || item.lastMessage || '暂无会话内容',
      timestamp: formatHistoryTimestamp(item.updatedAt || item.timestamp || item.updated_at),
      rawTimestamp: item.updatedAt || item.timestamp || item.updated_at || '',
      contextFilters: item.contextFilters || item.context_filters || {},
    }));
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
