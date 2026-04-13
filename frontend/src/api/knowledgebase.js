import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';
import { buildKnowledgebaseQuery } from '../lib/knowledgebase-workspace.js';

const apiConfig = createApiConfig();

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || '请求失败，请稍后重试');
  }
  return data;
};

const getHeaders = () => {
  const token = authStorage.getToken();
  const headers = { ...apiConfig.headers };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
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

const normalizeDocument = (doc, fallback = {}) => {
  const uploader = normalizePerson(doc.uploader || doc.uploaded_by);
  const owner = normalizePerson(doc.owner);
  const latestTask = doc.latest_ingestion_task || null;
  const processStep = buildProcessStep(doc, latestTask);

  return {
    id: doc.id || fallback.id || '',
    title: doc.title || doc.filename || fallback.title || '未命名文档',
    filename: doc.filename || doc.title || fallback.filename || '未命名文档',
    status: String(doc.status || fallback.status || 'uploaded').toLowerCase(),
    visibility: doc.visibility || 'internal',
    uploader,
    owner,
    uploaderName: uploader?.displayName || '未设置',
    ownerName: owner?.displayName || '未设置',
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
  async listDocuments(params = {}) {
    const query = new URLSearchParams(buildKnowledgebaseQuery(params));
    const path = query.toString()
      ? `/api/knowledgebase/documents?${query.toString()}`
      : '/api/knowledgebase/documents';
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, path), {
      method: 'GET',
      headers: getHeaders(),
      auth: true,
    });
    const data = await parseResponse(response);
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

  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);
    formData.append('source_date', new Date().toISOString().split('T')[0]);

    const headers = getHeaders();
    delete headers['Content-Type'];

    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents'), {
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

  async ingestDocument(documentId) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents/${documentId}/ingest`), {
      method: 'POST',
      headers: getHeaders(),
      auth: true,
    });
    const data = await parseResponse(response);
    return {
      ...data,
      document: data.document ? normalizeDocument(data.document) : null,
    };
  },

  async getDocumentDetail(documentId) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents/${documentId}`), {
      method: 'GET',
      headers: getHeaders(),
      auth: true,
    });
    const data = await parseResponse(response);
    const doc = data.document || data.data || data;
    return normalizeDocument(doc);
  },

  async getDocumentChunks(documentId) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents/${documentId}/chunks`), {
      method: 'GET',
      headers: getHeaders(),
      auth: true,
    });
    const data = await parseResponse(response);
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
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents/batch/ingest'), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ document_ids: documentIds }),
      auth: true,
    });
    return parseResponse(response);
  },

  async batchDeleteDocuments(documentIds) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents/batch/delete'), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ document_ids: documentIds }),
      auth: true,
    });
    return parseResponse(response);
  },

  isProcessingStatus(status) {
    return ['queued', 'parsing', 'chunking', 'indexing', 'running'].includes(
      String(status || '').toLowerCase(),
    );
  },
};
