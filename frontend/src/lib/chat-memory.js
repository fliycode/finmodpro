const MEMORY_TYPE_LABELS = {
  user_preference: '用户偏好',
  project_background: '项目背景',
  confirmed_fact: '确认事实',
  work_rule: '工作规则',
};

const MEMORY_SOURCE_LABELS = {
  auto: '自动提取',
  manual: '手动整理',
};

export function buildMemoryScopeLabel(scopeType, scopeKey = '') {
  if (scopeType === 'dataset') {
    return scopeKey ? `数据集 ${scopeKey}` : '数据集';
  }

  if (scopeType === 'project') {
    return scopeKey ? `项目 ${scopeKey}` : '项目';
  }

  if (scopeType === 'user_global') {
    return '全局记忆';
  }

  return '其他范围';
}

export function getMemoryTypeLabel(memoryType) {
  return MEMORY_TYPE_LABELS[memoryType] || '其他记忆';
}

export function getMemorySourceLabel(sourceKind) {
  return MEMORY_SOURCE_LABELS[sourceKind] || '未知来源';
}

export function normalizeMemoryItems(items = []) {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => {
    const memoryType = item.memoryType ?? item.memory_type ?? '';
    const scopeType = item.scopeType ?? item.scope_type ?? 'user_global';
    const scopeKey = item.scopeKey ?? item.scope_key ?? '';
    const sourceKind = item.sourceKind ?? item.source_kind ?? '';

    return {
      id: item.id ?? null,
      title: item.title || '未命名记忆',
      content: item.content || '',
      memoryType,
      memoryTypeLabel: getMemoryTypeLabel(memoryType),
      scopeType,
      scopeKey,
      scopeLabel: buildMemoryScopeLabel(scopeType, scopeKey),
      sourceKind,
      sourceLabel: getMemorySourceLabel(sourceKind),
      pinned: Boolean(item.pinned),
      updatedAt: item.updatedAt ?? item.updated_at ?? '',
    };
  });
}
