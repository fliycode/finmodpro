import { createApiConfig } from './config.js';
import { buildKnowledgebaseQuery } from '../lib/knowledgebase-workspace.js';

const apiConfig = createApiConfig();

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || '请求失败，请稍后重试');
  }
  return data;
};

const formatDateTime = (value) => {
  if (!value) {
    return 'N/A';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'N/A';
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date).replace(/\//g, '-');
};

const normalizeSize = (size, fallbackFileSize) => {
  const numericSize = Number(size ?? fallbackFileSize);
  if (!Number.isFinite(numericSize) || numericSize <= 0) {
    return 'N/A';
  }
  if (numericSize >= 1024 * 1024) {
    return `${(numericSize / 1024 / 1024).toFixed(2)} MB`;
  }
  if (numericSize >= 1024) {
    return `${(numericSize / 1024).toFixed(2)} KB`;
  }
  return `${numericSize} B`;
};

const normalizePerson = (person) => {
  if (!person || typeof person !== 'object') {
    return null;
  }
  return {
    id: person.id ?? null,
    username: person.username || '',
    email: person.email || '',
    displayName: person.username || person.email || '未设置',
  };
};

const normalizeDataset = (dataset) => {
  if (!dataset || typeof dataset !== 'object') {
    return null;
  }

  return {
    id: dataset.id ?? null,
    name: dataset.name || '',
    description: dataset.description || '',
    owner: normalizePerson(dataset.owner),
    documentCount: Number(dataset.document_count ?? 0),
    createdAt: dataset.created_at || null,
    updatedAt: dataset.updated_at || null,
    createdAtText: formatDateTime(dataset.created_at),
    updatedAtText: formatDateTime(dataset.updated_at),
  };
};

const normalizeProvenance = (provenance = {}) => ({
  sourceType: provenance.source_type || '',
  sourceLabel: provenance.source_label || '',
  sourceMetadata: provenance.source_metadata || {},
  processingNotes: provenance.processing_notes || '',
});

const buildProcessStep = (document, task) => {
  const status = String(document.status || '').toLowerCase();
  const step = String(task?.current_step || '').toLowerCase();
  const taskStatus = String(task?.status || '').toLowerCase();

  if (status === 'indexed' || step === 'completed' || taskStatus === 'succeeded') {
    return {
      code: 'indexed',
      label: '已入库',
      detail: '文档已完成切块和向量写入，可用于问答检索。',
      progress: 100,
      isTerminal: true,
      isSearchReady: true,
    };
  }

  if (status === 'failed' || step === 'failed' || taskStatus === 'failed') {
    return {
      code: 'failed',
      label: '处理失败',
      detail: task?.error_message || document.error_message || '处理链路中断，请查看失败原因。',
      progress: 100,
      isTerminal: true,
      isSearchReady: false,
    };
  }

  if (step === 'indexing') {
    return {
      code: 'indexing',
      label: '向量化中',
      detail: '正在写入 Milvus 向量库。',
      progress: 85,
      isTerminal: false,
      isSearchReady: false,
    };
  }

  if (status === 'chunked' || step === 'chunking') {
    return {
      code: 'chunking',
      label: '切块中',
      detail: '正在切分文档片段。',
      progress: 60,
      isTerminal: false,
      isSearchReady: false,
    };
  }

  if (status === 'parsed' || step === 'parsing' || taskStatus === 'running') {
    return {
      code: 'parsing',
      label: '解析中',
      detail: '正在抽取正文和元数据。',
      progress: 35,
      isTerminal: false,
      isSearchReady: false,
    };
  }

  if (taskStatus === 'queued' || step === 'queued') {
    return {
      code: 'queued',
      label: '待处理',
      detail: '文件已保存，等待处理任务执行。',
      progress: 10,
      isTerminal: false,
      isSearchReady: false,
    };
  }

  return {
    code: 'uploaded',
    label: '已上传',
    detail: '文件已保存，尚未开始处理。',
    progress: 5,
    isTerminal: false,
    isSearchReady: false,
  };
};

export const normalizeDocumentVersion = (version) => ({
  documentId: version.document_id ?? null,
  versionNumber: Number(version.version_number || 0),
  isCurrent: Boolean(version.is_current),
  sourceType: version.source_type || '',
  sourceLabel: version.source_label || '',
  sourceMetadata: version.source_metadata || {},
  processingNotes: version.processing_notes || '',
  createdAt: version.created_at || null,
  createdAtText: formatDateTime(version.created_at),
});

export const normalizeDocument = (doc, fallback = {}) => {
  const uploader = normalizePerson(doc.uploader || doc.uploaded_by);
  const owner = normalizePerson(doc.owner);
  const latestTask = doc.latest_ingestion_task || null;
  const processStep = buildProcessStep(doc, latestTask);
  const dataset = normalizeDataset(doc.dataset);
  const provenance = normalizeProvenance(doc.provenance || doc);

  return {
    id: doc.id || fallback.id || '',
    title: doc.title || doc.filename || fallback.title || '未命名文档',
    filename: doc.filename || doc.title || fallback.filename || '未命名文档',
    status: String(doc.status || fallback.status || 'uploaded').toLowerCase(),
    visibility: doc.visibility || 'internal',
    dataset,
    datasetName: dataset?.name || '未分组',
    uploader,
    owner,
    uploaderName: uploader?.displayName || '未设置',
    ownerName: owner?.displayName || '未设置',
    rootDocumentId: Number(doc.root_document_id || doc.id || fallback.id || 0),
    versionNumber: Number(doc.version_number || 1),
    currentVersion: Number(doc.current_version || doc.version_number || 1),
    versionCount: Number(doc.version_count || 1),
    isCurrentVersion: doc.is_current_version !== false,
    provenance,
    sourceType: provenance.sourceType,
    sourceLabel: provenance.sourceLabel,
    sourceMetadata: provenance.sourceMetadata,
    processingNotes: provenance.processingNotes,
    uploadTime: formatDateTime(doc.created_at || fallback.created_at),
    updateTime: formatDateTime(doc.updated_at || fallback.updated_at),
    sourceDate: doc.source_date || 'N/A',
    size: normalizeSize(doc.size || doc.file_size, fallback.fileSize),
    processStep,
    processResult: doc.process_result || processStep.detail,
    processError: doc.error_message || latestTask?.error_message || '',
    latestTask: latestTask ? {
      ...latestTask,
      createdAtText: formatDateTime(latestTask.created_at),
      updatedAtText: formatDateTime(latestTask.updated_at),
      startedAtText: formatDateTime(latestTask.started_at),
      finishedAtText: formatDateTime(latestTask.finished_at),
    } : null,
    chunkCount: Number(doc.chunk_count || 0),
    vectorCount: Number(doc.vector_count || 0),
    isSearchReady: processStep.isSearchReady,
    originalUrl: doc.original_url || '',
    previewUrl: doc.preview_url || doc.original_url || '',
    extractedText: doc.extracted_text || doc.parsed_text || '',
    parsedTextPreview: doc.parsed_text_preview || doc.preview_text || '',
  };
};

export const kbApi = {
  async listDatasets() {
    const data = await apiConfig.fetchJson('/api/knowledgebase/datasets', {
      method: 'GET',
      auth: true,
    });
    const datasets = Array.isArray(data.datasets) ? data.datasets : [];
    return {
      datasets: datasets.map((dataset) => normalizeDataset(dataset)),
      total: Number(data.total ?? datasets.length ?? 0),
    };
  },

  async createDataset(payload = {}) {
    const data = await apiConfig.fetchJson('/api/knowledgebase/datasets', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(payload),
    });
    return normalizeDataset(data.dataset || data);
  },

  async listDocuments(params = {}) {
    const query = new URLSearchParams(buildKnowledgebaseQuery(params));
    const path = query.toString()
      ? `/api/knowledgebase/documents?${query.toString()}`
      : '/api/knowledgebase/documents';
    const data = await apiConfig.fetchJson(path, {
      method: 'GET',
      auth: true,
    });
    const docs = Array.isArray(data.documents)
      ? data.documents
      : Array.isArray(data)
        ? data
        : (data.data || []);
    return {
      documents: docs.map((doc) => normalizeDocument(doc)),
      total: Number(data.total ?? docs.length ?? 0),
      page: Number(data.page || 1),
      pageSize: Number(data.page_size || 10),
      totalPages: Number(data.total_pages || 0),
    };
  },

  async uploadDocument(file, options = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);
    formData.append('source_date', new Date().toISOString().split('T')[0]);
    if (options.datasetId && options.datasetId !== 'all') {
      formData.append('dataset_id', options.datasetId);
    }

    const headers = apiConfig.getAuthHeaders();
    delete headers['Content-Type'];

    const response = await apiConfig.fetchWithAuth('/api/knowledgebase/documents', {
      method: 'POST',
      headers,
      body: formData,
      auth: true,
    });

    const data = await parseResponse(response);
    return {
      success: true,
      document: normalizeDocument(data.document || data, {
        title: file.name,
        fileSize: file.size,
      }),
    };
  },

  async listDocumentVersions(documentId) {
    const data = await apiConfig.fetchJson(`/api/knowledgebase/documents/${documentId}/versions`, {
      method: 'GET',
      auth: true,
    });
    return {
      documentId: Number(data.document_id || documentId),
      currentVersion: Number(data.current_version || 1),
      versions: Array.isArray(data.versions)
        ? data.versions.map((version) => normalizeDocumentVersion(version))
        : [],
    };
  },

  async uploadNewVersion(documentId, file, metadata = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', metadata.title || file.name);
    formData.append('source_date', metadata.sourceDate || new Date().toISOString().split('T')[0]);
    formData.append('source_type', metadata.sourceType || 'upload');
    formData.append('source_label', metadata.sourceLabel || file.name);
    formData.append(
      'source_metadata',
      JSON.stringify(metadata.sourceMetadata || {}),
    );
    formData.append('processing_notes', metadata.processingNotes || '');

    const headers = apiConfig.getAuthHeaders();
    delete headers['Content-Type'];

    const response = await apiConfig.fetchWithAuth(`/api/knowledgebase/documents/${documentId}/versions`, {
      method: 'POST',
      headers,
      body: formData,
      auth: true,
    });
    const data = await parseResponse(response);
    return {
      ...data,
      document: data.document ? normalizeDocument(data.document) : null,
    };
  },

  async ingestDocument(documentId) {
    const data = await apiConfig.fetchJson(`/api/knowledgebase/documents/${documentId}/ingest`, {
      method: 'POST',
      auth: true,
    });
    return {
      ...data,
      document: data.document ? normalizeDocument(data.document) : null,
    };
  },

  async getDocumentDetail(documentId) {
    const data = await apiConfig.fetchJson(`/api/knowledgebase/documents/${documentId}`, {
      method: 'GET',
      auth: true,
    });
    const doc = data.document || data.data || data;
    return normalizeDocument(doc);
  },

  async getDocumentChunks(documentId) {
    const data = await apiConfig.fetchJson(`/api/knowledgebase/documents/${documentId}/chunks`, {
      method: 'GET',
      auth: true,
    });
    return (data.chunks || []).map((chunk) => ({
      id: chunk.id,
      chunkIndex: Number(chunk.chunk_index || 0),
      pageLabel: chunk.page_label || `chunk-${Number(chunk.chunk_index || 0) + 1}`,
      content: chunk.content || '',
      vectorId: chunk.vector_id || '',
      metadata: chunk.metadata || {},
    }));
  },

  async batchIngestDocuments(documentIds) {
    return apiConfig.fetchJson('/api/knowledgebase/documents/batch/ingest', {
      method: 'POST',
      auth: true,
      body: JSON.stringify({ document_ids: documentIds }),
    });
  },

  async batchDeleteDocuments(documentIds) {
    return apiConfig.fetchJson('/api/knowledgebase/documents/batch/delete', {
      method: 'POST',
      auth: true,
      body: JSON.stringify({ document_ids: documentIds }),
    });
  },

  isProcessingStatus(status) {
    return ['queued', 'parsing', 'chunking', 'indexing', 'running'].includes(
      String(status || '').toLowerCase(),
    );
  },
};
