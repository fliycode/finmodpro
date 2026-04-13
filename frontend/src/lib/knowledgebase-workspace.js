export const buildKnowledgebaseQuery = ({
  searchKeyword = '',
  statusFilter = 'all',
  timeRange = 'all',
  datasetId = '',
  page = 1,
  pageSize = 10,
} = {}) => {
  const query = {
    page,
    page_size: pageSize,
  };

  if (searchKeyword.trim()) {
    query.q = searchKeyword.trim();
  }

  if (statusFilter && statusFilter !== 'all') {
    query.status = statusFilter;
  }

  if (timeRange && timeRange !== 'all') {
    query.time_range = timeRange;
  }

  if (datasetId && datasetId !== 'all') {
    query.dataset_id = datasetId;
  }

  return query;
};

export const buildPreviewState = (document) => {
  const body = document?.extractedText || document?.parsedTextPreview || '';
  return {
    hasContent: body.trim().length > 0,
    body,
  };
};

export const summarizeBatchResult = (payload, label) => {
  const success = payload?.accepted_count ?? payload?.deleted_count ?? 0;
  const skippedOrFailed = payload?.skipped_count ?? payload?.failed_count ?? 0;
  return `${label}完成：成功 ${success} 项，跳过/失败 ${skippedOrFailed} 项。`;
};

export const buildNextSelection = ({ selectedIds = [], toggledId }) => (
  selectedIds.includes(toggledId)
    ? selectedIds.filter((id) => id !== toggledId)
    : [...selectedIds, toggledId]
);

export const buildSelectionAfterBatchDelete = (selectedIds = [], deletedIds = []) => (
  selectedIds.filter((id) => !deletedIds.includes(id))
);

export const buildEmptyDetailState = () => ({
  title: '请选择一个文档查看详情',
  detail: '左侧选择文档后，可查看处理进度、切块和错误信息。',
});

export const buildChunkExpansionState = (expandedIds = [], chunkId) => (
  expandedIds.includes(chunkId)
    ? expandedIds.filter((id) => id !== chunkId)
    : [...expandedIds, chunkId]
);
