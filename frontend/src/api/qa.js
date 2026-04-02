import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

const normalizeErrorMessage = (data, fallback) => {
  const rawMessage = data?.message || data?.error || data?.detail || fallback || '请求失败，请稍后重试';
  const message = String(rawMessage).trim();

  if (/model|llm|配置|未启用|未配置/i.test(message)) {
    return '当前未配置可用的对话模型，请先在管理后台启用聊天模型。';
  }

  return message;
};

export const qaApi = {
  async askQuestion(query, filters = {}, top_k = 5) {
    const payload = { question: query, filters, top_k };

    try {
      const data = await apiConfig.fetchJson('/api/chat/ask', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      });

      let rawCitations = data.citations || [];
      if (!Array.isArray(rawCitations)) rawCitations = [];

      const citations = rawCitations.map((cite) => ({
        document_title: cite.document_title || cite.title || cite.filename || cite.doc_name || 'Unknown Document',
        doc_type: cite.doc_type || (cite.filename ? cite.filename.split('.').pop() : (cite.type || 'document')),
        source_date: cite.source_date || cite.date || cite.upload_time || cite.created_at || 'N/A',
        page_label: cite.page_label || cite.page || (cite.metadata && (cite.metadata.page || cite.metadata.page_label)) || 'N/A',
        snippet: cite.snippet || cite.text || cite.content || cite.preview || '',
        score: Number(cite.score || cite.rerank_score || cite.similarity || 0),
      }));

      return {
        answer: data.answer || data.content || data.response || data.text || '',
        citations,
        duration_ms: data.duration_ms || 0,
      };
    } catch (error) {
      throw new Error(normalizeErrorMessage({ message: error?.message }, error?.message));
    }
  },
};
