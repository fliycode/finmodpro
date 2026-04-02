import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

const apiConfig = createApiConfig();

const ACTIVE_PROCESSING_STATUSES = ['uploaded', 'parsed', 'chunked', 'processing', 'pending'];

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
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const normalizeSize = (size, fallbackFileSize) => {
  if (typeof size === 'string' && size.trim()) {
    return size;
  }

  const numericSize = Number(size ?? fallbackFileSize);
  if (!Number.isFinite(numericSize) || numericSize <= 0) {
    return 'N/A';
  }

  if (numericSize >= 1024 * 1024) {
    return `${(numericSize / 1024 / 1024).toFixed(2)}MB`;
  }

  if (numericSize >= 1024) {
    return `${(numericSize / 1024).toFixed(2)}KB`;
  }

  return `${numericSize}B`;
};

const normalizeTime = (value) => {
  if (!value) {
    return 'N/A';
  }

  if (typeof value === 'string') {
    return value;
  }

  try {
    return new Date(value).toLocaleString();
  } catch {
    return 'N/A';
  }
};

const normalizeStatus = (status) => {
  const rawStatus = String(status || 'uploaded').toLowerCase();

  if (rawStatus === 'pending' || rawStatus === 'uploading') return 'uploaded';
  if (rawStatus === 'processing' || rawStatus === 'parsing') return 'parsed';
  if (rawStatus === 'chunking') return 'chunked';
  if (rawStatus === 'completed' || rawStatus === 'success' || rawStatus === 'indexed') return 'indexed';
  if (rawStatus === 'error') return 'failed';

  return ['uploaded', 'parsed', 'chunked', 'indexed', 'failed'].includes(rawStatus)
    ? rawStatus
    : 'uploaded';
};

const getProcessStep = (status) => {
  const normalizedStatus = normalizeStatus(status);

  if (normalizedStatus === 'uploaded') {
    return {
      code: 'uploaded',
      label: '已上传',
      detail: '文档已入库，等待解析任务执行。',
      progress: 20,
      isTerminal: false,
    };
  }

  if (normalizedStatus === 'parsed') {
    return {
      code: 'parsed',
      label: '解析中',
      detail: '正在抽取正文与元数据。',
      progress: 50,
      isTerminal: false,
    };
  }

  if (normalizedStatus === 'chunked') {
    return {
      code: 'chunked',
      label: '切块中',
      detail: '正在切分片段并准备索引。',
      progress: 75,
      isTerminal: false,
    };
  }

  if (normalizedStatus === 'indexed') {
    return {
      code: 'indexed',
      label: '已索引',
      detail: '文档已可用于检索与问答。',
      progress: 100,
      isTerminal: true,
    };
  }

  return {
    code: 'failed',
    label: '处理失败',
    detail: '处理链路中断，请查看失败原因。',
    progress: 100,
    isTerminal: true,
  };
};

const normalizeDocument = (doc, fallback = {}) => {
  const normalizedStatus = normalizeStatus(doc.status || fallback.status);
  const processStep = getProcessStep(normalizedStatus);
  const uploader = doc.uploader || doc.owner || doc.uploaded_by || doc.created_by || doc.createdBy || fallback.uploader || '未知';
  const sourceType = doc.source_type || doc.sourceType || fallback.sourceType || '本地上传';
  const processResult = doc.process_result || doc.result || doc.summary || doc.message || doc.error || fallback.processResult || processStep.detail;
  const originalUrl = doc.original_url || doc.originalUrl || doc.file_url || doc.fileUrl || doc.download_url || doc.downloadUrl || fallback.originalUrl || '';
  const previewUrl = doc.preview_url || doc.previewUrl || doc.viewer_url || doc.viewerUrl || fallback.previewUrl || originalUrl;
  const extractedText = doc.extracted_text || doc.content || doc.text || doc.raw_text || fallback.extractedText || '';
  const chunkCount = doc.chunk_count || doc.chunks || doc.segment_count || fallback.chunkCount || null;

  return {
    id: doc.id || doc._id || doc.doc_id || fallback.id || '',
    name: doc.name || doc.filename || doc.title || fallback.name || '未命名文档',
    status: normalizedStatus,
    uploadTime: normalizeTime(doc.uploadTime || doc.created_at || doc.upload_time || doc.createdAt || fallback.uploadTime),
    size: normalizeSize(doc.size || doc.filesize || doc.file_size, fallback.fileSize),
    uploader: typeof uploader === 'object' ? (uploader.name || uploader.username || uploader.email || '未知') : String(uploader || '未知'),
    owner: typeof uploader === 'object' ? (uploader.name || uploader.username || uploader.email || '未知') : String(uploader || '未知'),
    sourceType,
    processStep,
    processResult: String(processResult || processStep.detail),
    originalUrl,
    previewUrl,
    extractedText,
    chunkCount: chunkCount == null ? null : Number(chunkCount),
  };
};

export const kbApi = {
  async listDocuments() {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents'), {
      method: 'GET',
      headers: getHeaders(),
      auth: true,
    });
    const data = await parseResponse(response);

    const docs = Array.isArray(data) ? data : (data.documents || data.data || []);
    return docs.map((doc) => normalizeDocument(doc));
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
    const doc = data.document || data;

    return {
      success: true,
      document: normalizeDocument(doc, {
        name: file.name,
        status: 'uploaded',
        uploadTime: new Date().toLocaleString(),
        fileSize: file.size,
        uploader: '当前用户',
        processResult: '文档已上传，等待任务执行。',
      }),
    };
  },

  async ingestDocument(documentId) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents/${documentId}/ingest`), {
      method: 'POST',
      headers: getHeaders(),
      auth: true,
    });
    return parseResponse(response);
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

  isProcessingStatus(status) {
    return ACTIVE_PROCESSING_STATUSES.includes(String(status || '').toLowerCase());
  },
};
