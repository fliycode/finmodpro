import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

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
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const kbApi = {
  // List documents from backend
  async listDocuments() {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents'), {
      method: 'GET',
      headers: getHeaders(),
    });
    const data = await parseResponse(response);
    
    // Normalize data structure
    const docs = Array.isArray(data) ? data : (data.documents || data.data || []);
    return docs.map(doc => {
      // Map common backend statuses to required frontend statuses
      let status = (doc.status || 'uploaded').toLowerCase();
      if (status === 'pending' || status === 'uploading') status = 'uploaded';
      if (status === 'processing' || status === 'parsing') status = 'parsed';
      if (status === 'chunking') status = 'chunked';
      if (status === 'completed' || status === 'success') status = 'indexed';
      if (status === 'error') status = 'failed';

      // Ensure status is one of the allowed values
      const validStatuses = ['uploaded', 'parsed', 'chunked', 'indexed', 'failed'];
      if (!validStatuses.includes(status)) status = 'uploaded';

      return {
        id: doc.id || doc._id || doc.doc_id || String(Math.random()),
        name: doc.name || doc.filename || doc.title || '未命名文档',
        status: status,
        uploadTime: doc.uploadTime || doc.created_at || doc.upload_time || 'N/A',
        size: doc.size || (doc.filesize ? (doc.filesize / 1024 / 1024).toFixed(2) + 'MB' : 'N/A')
      };
    });
  },
  
  // Upload document (Single file)
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);
    formData.append('source_date', new Date().toISOString().split('T')[0]);
    
    const headers = getHeaders();
    // Browser will automatically set Content-Type with boundary for FormData
    delete headers['Content-Type'];

    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/knowledgebase/documents'), {
      method: 'POST',
      headers: headers,
      body: formData,
    });
    
    const data = await parseResponse(response);
    const doc = data.document || data;
    
    return {
      success: true,
      document: {
        id: doc.id || doc._id || String(Math.random()),
        name: doc.name || doc.filename || file.name,
        status: doc.status || 'uploaded',
        uploadTime: doc.uploadTime || doc.created_at || doc.upload_time || new Date().toLocaleString(),
        size: doc.size || (file.size / 1024 / 1024).toFixed(2) + 'MB'
      }
    };
  },

  // Ingest document
  async ingestDocument(documentId) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/knowledgebase/documents/${documentId}/ingest`), {
      method: 'POST',
      headers: getHeaders(),
    });
    return parseResponse(response);
  }
};
