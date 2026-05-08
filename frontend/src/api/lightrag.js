import { createApiConfig } from './config.js';

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (![0, 200, 201].includes(payload.code)) {
      throw new Error(payload.message || '请求失败');
    }
    return payload.data;
  }
  return payload;
};

const buildQuery = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    query.set(key, String(value));
  });
  const queryString = query.toString();
  return queryString ? `?${queryString}` : '';
};

export const normalizeLightragDocument = (row = {}) => ({
  id: row.id || row.doc_id || row.track_id || row.file_path || row.file_name || row.title || 'unknown',
  docId: row.doc_id || row.id || '',
  title: row.title || row.file_name || row.file_path || '未命名文档',
  status: row.status || row.doc_status || 'unknown',
  trackId: row.track_id || '',
  summary: row.summary || row.message || row.error_msg || '',
  createdAt: row.created_at || '',
  updatedAt: row.updated_at || row.modified_at || row.created_at || '',
  raw: row,
});

const readGraphText = (value) => {
  if (value === undefined || value === null) {
    return '';
  }

  if (typeof value === 'string') {
    return value.trim();
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => readGraphText(item)).find(Boolean) || '';
  }

  if (typeof value === 'object') {
    for (const key of ['label', 'name', 'title', 'entity_name', 'entity_id', 'id', 'value']) {
      const nested = readGraphText(value[key]);
      if (nested) {
        return nested;
      }
    }
  }

  return '';
};

export const normalizeGraphNode = (row = {}) => ({
  id: readGraphText(row.id)
    || readGraphText(row.entity_id)
    || readGraphText(row.properties?.entity_id)
    || readGraphText(row.properties?.id)
    || readGraphText(row.label)
    || readGraphText(row.entity_name)
    || 'unknown',
  label: readGraphText(row.label)
    || readGraphText(row.entity_name)
    || readGraphText(row.name)
    || readGraphText(row.title)
    || readGraphText(row.labels)
    || readGraphText(row.properties?.label)
    || readGraphText(row.properties?.entity_name)
    || readGraphText(row.properties?.entity_id)
    || readGraphText(row.id)
    || '未命名节点',
  type: readGraphText(row.entity_type)
    || readGraphText(row.type)
    || readGraphText(row.properties?.entity_type)
    || readGraphText(row.properties?.type)
    || '未分类',
  description: readGraphText(row.description)
    || readGraphText(row.summary)
    || readGraphText(row.properties?.description)
    || readGraphText(row.properties?.summary)
    || '',
  properties: row.properties || {},
  raw: row,
});

export const normalizeGraphEdge = (row = {}) => ({
  id: readGraphText(row.id)
    || `${readGraphText(row.source) || readGraphText(row.source_id) || readGraphText(row.source_entity) || 'source'}-${readGraphText(row.target) || readGraphText(row.target_id) || readGraphText(row.target_entity) || 'target'}`,
  source: readGraphText(row.source)
    || readGraphText(row.source_id)
    || readGraphText(row.source_entity)
    || '未提供',
  target: readGraphText(row.target)
    || readGraphText(row.target_id)
    || readGraphText(row.target_entity)
    || '未提供',
  label: readGraphText(row.label)
    || readGraphText(row.relation)
    || readGraphText(row.relation_type)
    || readGraphText(row.properties?.label)
    || readGraphText(row.properties?.relation)
    || readGraphText(row.properties?.relation_type)
    || (readGraphText(row.type) === 'DIRECTED' ? '' : readGraphText(row.type))
    || '关联',
  description: readGraphText(row.description)
    || readGraphText(row.properties?.description)
    || '',
  properties: row.properties || {},
  raw: row,
});

export const createLightragApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  const postJson = (path, payload = {}) => fetchJson(path, {
    method: 'POST',
    auth: true,
    body: JSON.stringify(payload),
  });

  return {
    async getOverview() {
      return unwrap(await fetchJson('/api/ops/lightrag/', {
        method: 'GET',
        auth: true,
      }));
    },

    async query(payload) {
      return unwrap(await postJson('/api/ops/lightrag/query/', payload));
    },

    async getGraph(label, options = {}) {
      const query = buildQuery({
        label,
        max_depth: options.maxDepth,
        max_nodes: options.maxNodes,
      });
      const payload = unwrap(await fetchJson(`/api/ops/lightrag/graphs/${query}`, {
        method: 'GET',
        auth: true,
      }));
      return {
        nodes: Array.isArray(payload.nodes) ? payload.nodes.map((node) => normalizeGraphNode(node)) : [],
        edges: Array.isArray(payload.edges) ? payload.edges.map((edge) => normalizeGraphEdge(edge)) : [],
        isTruncated: Boolean(payload.is_truncated),
        raw: payload,
      };
    },

    async getPopularLabels(limit = 8) {
      const payload = unwrap(await fetchJson(`/api/ops/lightrag/graph/label/popular/${buildQuery({ limit })}`, {
        method: 'GET',
        auth: true,
      }));
      return Array.isArray(payload) ? payload : [];
    },

    async getLabelList() {
      const payload = unwrap(await fetchJson('/api/ops/lightrag/graph/label/list/', {
        method: 'GET',
        auth: true,
      }));
      return Array.isArray(payload) ? payload : [];
    },

    async searchLabels(q, limit = 10) {
      const payload = unwrap(await fetchJson(`/api/ops/lightrag/graph/label/search/${buildQuery({ q, limit })}`, {
        method: 'GET',
        auth: true,
      }));
      return Array.isArray(payload) ? payload : [];
    },

    async listDocuments(params = {}) {
      const payload = unwrap(await postJson('/api/ops/lightrag/documents/paginated/', {
        status_filter: params.statusFilter || null,
        page: params.page || 1,
        page_size: params.pageSize || 12,
        sort_field: params.sortField || 'updated_at',
        sort_direction: params.sortDirection || 'desc',
      }));

      return {
        documents: Array.isArray(payload.documents)
          ? payload.documents.map((row) => normalizeLightragDocument(row))
          : [],
        pagination: payload.pagination || {},
        statusCounts: payload.status_counts || {},
      };
    },

    async getStatusCounts() {
      return unwrap(await fetchJson('/api/ops/lightrag/documents/status_counts/', {
        method: 'GET',
        auth: true,
      }));
    },

    async uploadDocument(file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers = apiConfig.getAuthHeaders();
      delete headers['Content-Type'];
      return unwrap(await apiConfig.fetchJson('/api/ops/lightrag/documents/upload/', {
        method: 'POST',
        headers,
        body: formData,
        auth: true,
      }));
    },

    async scanDocuments() {
      return unwrap(await postJson('/api/ops/lightrag/documents/scan/', {}));
    },

    async reprocessFailedDocuments() {
      return unwrap(await postJson('/api/ops/lightrag/documents/reprocess_failed/', {}));
    },

    async cancelPipeline() {
      return unwrap(await postJson('/api/ops/lightrag/documents/cancel_pipeline/', {}));
    },

    async clearCache() {
      return unwrap(await postJson('/api/ops/lightrag/documents/clear_cache/', {}));
    },

    async getTrackStatus(trackId) {
      return unwrap(await fetchJson(`/api/ops/lightrag/documents/track_status/${encodeURIComponent(trackId)}/`, {
        method: 'GET',
        auth: true,
      }));
    },

    async deleteDocument(docIds, options = {}) {
      return unwrap(await fetchJson('/api/ops/lightrag/documents/delete_document/', {
        method: 'DELETE',
        auth: true,
        body: JSON.stringify({
          doc_ids: Array.isArray(docIds) ? docIds : [docIds],
          delete_file: Boolean(options.deleteFile),
          delete_llm_cache: Boolean(options.deleteLlmCache),
        }),
      }));
    },
  };
};

export const lightragApi = createLightragApi();
