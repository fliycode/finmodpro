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

export const normalizeGraphNode = (row = {}) => ({
  id: row.id || row.entity_id || row.entity_name || row.label || 'unknown',
  label: row.label || row.entity_name || row.id || '未命名节点',
  type: row.entity_type || row.type || '未分类',
  description: row.description || row.summary || '',
  raw: row,
});

export const normalizeGraphEdge = (row = {}) => ({
  id: row.id || `${row.source || row.source_id || row.source_entity || 'source'}-${row.target || row.target_id || row.target_entity || 'target'}`,
  source: row.source || row.source_id || row.source_entity || '未提供',
  target: row.target || row.target_id || row.target_entity || '未提供',
  label: row.label || row.relation || row.relation_type || '关联',
  description: row.description || '',
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
