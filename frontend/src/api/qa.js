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

export const qaApi = {
  // Ask question (QA using RAG)
  async askQuestion(query, filters = {}, top_k = 5) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/chat/ask'), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ question: query, filters, top_k }),
    });
    
    const data = await parseResponse(response);
    
    // Ensure citations format matches expectations
    let rawCitations = data.citations || [];
    if (!Array.isArray(rawCitations)) rawCitations = [];

    const citations = rawCitations.map(cite => ({
      document_title: cite.document_title || cite.title || cite.filename || cite.doc_name || 'Unknown Document',
      doc_type: cite.doc_type || (cite.filename ? cite.filename.split('.').pop() : (cite.type || 'document')),
      source_date: cite.source_date || cite.date || cite.upload_time || cite.created_at || 'N/A',
      page_label: cite.page_label || cite.page || (cite.metadata && (cite.metadata.page || cite.metadata.page_label)) || 'N/A',
      snippet: cite.snippet || cite.text || cite.content || cite.preview || '',
      score: Number(cite.score || cite.rerank_score || cite.similarity || 0)
    }));
    
    return {
      answer: data.answer || data.content || data.response || data.text || '',
      citations: citations,
      duration_ms: data.duration_ms || 0
    };
  }
};
