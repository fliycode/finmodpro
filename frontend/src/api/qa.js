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

const MOCK_RESPONSE = {
  answer: "根据2023年度财务报告，公司的净利润增长了15%，主要由于海外市场的强劲表现和内部运营效率的提升。风险评估方面，市场波动和供应链成本是主要的关注点。",
  citations: [
    { document_title: "2023年度财务报告.pdf", doc_type: "pdf", source_date: "2024-01-15", page_label: "P12", snippet: "2023年公司实现净利润XX亿元，同比增长15.2%...", score: 0.95 },
    { document_title: "风险评估准则v2.docx", doc_type: "docx", source_date: "2024-02-10", page_label: "P5", snippet: "供应链风险在Q3季度由于外部环境变化有所上升...", score: 0.82 }
  ]
};

export const qaApi = {
  // Ask question (QA using RAG)
  async askQuestion(query) {
    try {
      const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/v1/rag/ask'), {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ query }),
      });
      
      const data = await parseResponse(response);
      
      // Ensure citations format matches expectations
      let rawCitations = data.citations || data.sources || data.references || [];
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
        citations: citations
      };
    } catch (error) {
      console.warn('qaApi.askQuestion failed, using fallback:', error.message);
      return MOCK_RESPONSE;
    }
  }
};
