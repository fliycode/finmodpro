const statusToneMap = {
  processed: 'success',
  complete: 'success',
  completed: 'success',
  success: 'success',
  processing: 'brand',
  running: 'brand',
  scanning: 'brand',
  uploading: 'brand',
  pending: 'warning',
  queued: 'warning',
  waiting: 'warning',
  failed: 'risk',
  error: 'risk',
  cancelled: 'muted',
  canceled: 'muted',
};

const compareFacetRows = (left, right) => {
  if (right.count !== left.count) {
    return right.count - left.count;
  }
  return left.label.localeCompare(right.label, 'zh-CN');
};

export const getLightragStatusTone = (status) => {
  const normalized = String(status || '').trim().toLowerCase();
  return statusToneMap[normalized] || 'muted';
};

export const buildLightragGraphFacets = (nodes = [], edges = []) => {
  const nodeTypeCounts = new Map();
  const relationCounts = new Map();

  nodes.forEach((node) => {
    const key = node.type || '未分类';
    nodeTypeCounts.set(key, (nodeTypeCounts.get(key) || 0) + 1);
  });

  edges.forEach((edge) => {
    const key = edge.label || '关联';
    relationCounts.set(key, (relationCounts.get(key) || 0) + 1);
  });

  return {
    nodeTypes: [...nodeTypeCounts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort(compareFacetRows),
    relationLabels: [...relationCounts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort(compareFacetRows),
  };
};

export const filterLightragGraph = (
  graph = { nodes: [], edges: [] },
  filters = { activeNodeTypes: [], activeRelationLabels: [] },
) => {
  const nodeWhitelist = new Set(filters.activeNodeTypes || []);
  const edgeWhitelist = new Set(filters.activeRelationLabels || []);

  const nodes = (graph.nodes || []).filter((node) => {
    if (!nodeWhitelist.size) {
      return true;
    }
    return nodeWhitelist.has(node.type || '未分类');
  });

  const visibleNodeIds = new Set(nodes.map((node) => node.id));
  const edges = (graph.edges || []).filter((edge) => {
    if (edgeWhitelist.size && !edgeWhitelist.has(edge.label || '关联')) {
      return false;
    }
    return visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target);
  });

  return { nodes, edges };
};

export const searchLightragGraphNodes = (nodes = [], query = '') => {
  const normalizedQuery = String(query || '').trim().toLowerCase();
  if (!normalizedQuery) {
    return [];
  }

  return nodes
    .filter((node) => {
      const haystack = [
        node.label,
        node.id,
        node.type,
        node.description,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    })
    .map((node) => node.id);
};
