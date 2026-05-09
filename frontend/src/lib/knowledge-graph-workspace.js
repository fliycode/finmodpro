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

const buildNodeSearchText = (node = {}) => [
  node.label,
  node.id,
  node.type,
  node.description,
]
  .filter(Boolean)
  .join(' ')
  .toLowerCase();

const normalizeSearchTokens = (query = '') => String(query || '')
  .trim()
  .toLowerCase()
  .split(/\s+/)
  .filter(Boolean);

const compareSearchMatches = (left, right) => {
  if (right.score !== left.score) {
    return right.score - left.score;
  }
  return (left.label || '').localeCompare(right.label || '', 'zh-CN');
};

export const getKnowledgeGraphStatusTone = (status) => {
  const normalized = String(status || '').trim().toLowerCase();
  return statusToneMap[normalized] || 'muted';
};

export const buildKnowledgeGraphFacets = (nodes = [], edges = []) => {
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

export const filterKnowledgeGraph = (
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

export const filterKnowledgeGraphLabels = (labels = [], query = '') => {
  const normalizedQuery = String(query || '').trim().toLowerCase();
  if (!normalizedQuery) {
    return [...labels];
  }

  return labels.filter((label) => String(label || '').toLowerCase().includes(normalizedQuery));
};

export const findKnowledgeGraphMatches = (nodes = [], query = '', limit = 12) => {
  const tokens = normalizeSearchTokens(query);
  if (!tokens.length) {
    return [];
  }

  return nodes
    .map((node) => {
      const searchText = buildNodeSearchText(node);
      if (!tokens.every((token) => searchText.includes(token))) {
        return null;
      }

      const label = String(node.label || '').toLowerCase();
      const type = String(node.type || '').toLowerCase();
      const description = String(node.description || '').toLowerCase();

      const score = tokens.reduce((total, token) => {
        let tokenScore = 1;
        if (label === token) {
          tokenScore += 6;
        } else if (label.startsWith(token)) {
          tokenScore += 4;
        } else if (label.includes(token)) {
          tokenScore += 3;
        }

        if (type.includes(token)) {
          tokenScore += 2;
        }

        if (description.includes(token)) {
          tokenScore += 1;
        }

        return total + tokenScore;
      }, 0);

      return {
        ...node,
        score,
      };
    })
    .filter(Boolean)
    .sort(compareSearchMatches)
    .slice(0, limit);
};

export const searchKnowledgeGraphNodes = (nodes = [], query = '') => {
  return findKnowledgeGraphMatches(nodes, query).map((node) => node.id);
};

export const buildKnowledgeGraphNeighbors = (
  graph = { nodes: [], edges: [] },
  nodeId = '',
  limit = 8,
) => {
  if (!nodeId) {
    return [];
  }

  const nodeById = new Map((graph.nodes || []).map((node) => [node.id, node]));

  return (graph.edges || [])
    .filter((edge) => edge.source === nodeId || edge.target === nodeId)
    .map((edge) => {
      const isOutgoing = edge.source === nodeId;
      const relatedNode = nodeById.get(isOutgoing ? edge.target : edge.source);

      return {
        id: relatedNode?.id || `${edge.id}-neighbor`,
        label: relatedNode?.label || (isOutgoing ? edge.target : edge.source),
        type: relatedNode?.type || '未分类',
        description: relatedNode?.description || '',
        edgeId: edge.id,
        edgeLabel: edge.label || '关联',
        direction: isOutgoing ? 'outgoing' : 'incoming',
      };
    })
    .slice(0, limit);
};
