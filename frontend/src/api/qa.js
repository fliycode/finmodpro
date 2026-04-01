import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

export const qaApi = {
  async askQuestion(query, filters = {}, top_k = 5) {
    const data = await apiConfig.fetchJson('/api/chat/ask', {
      method: 'POST',
      auth: true,
      body: JSON.stringify({ question: query, filters, top_k }),
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
  },
};
