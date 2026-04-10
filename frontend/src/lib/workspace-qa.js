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
  }));
}
