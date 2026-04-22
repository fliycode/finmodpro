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

const normalizeCitations = (rawCitations) => {
  if (!Array.isArray(rawCitations)) {
    return [];
  }

  return rawCitations.map((cite) => ({
    document_title: cite.document_title || cite.title || cite.filename || 'Unknown Document',
    doc_type: cite.doc_type || (cite.filename ? cite.filename.split('.').pop() : 'document'),
    source_date: cite.source_date || cite.date || cite.created_at || 'N/A',
    page_label: cite.page_label || cite.page || (cite.metadata && (cite.metadata.page || cite.metadata.page_label)) || 'N/A',
    snippet: cite.snippet || cite.text || cite.content || '',
    score: Number(cite.score || cite.rerank_score || cite.similarity || 0),
  }));
};

const normalizeAnswerPayload = (data) => ({
  answer: data.answer || data.content || data.response || data.text || '',
  citations: normalizeCitations(data.citations),
  answer_mode: data.answer_mode || 'cited',
  answer_notice: data.answer_notice || '',
  duration_ms: data.duration_ms || 0,
});

const parseSse = (buffer, onEvent) => {
  let remaining = buffer;
  let boundaryIndex = remaining.indexOf('\n\n');

  while (boundaryIndex >= 0) {
    const rawEvent = remaining.slice(0, boundaryIndex);
    remaining = remaining.slice(boundaryIndex + 2);
    boundaryIndex = remaining.indexOf('\n\n');

    if (!rawEvent.trim()) {
      continue;
    }

    let eventName = 'message';
    const dataLines = [];
    rawEvent.split('\n').forEach((line) => {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    });

    const dataText = dataLines.join('\n');
    let data = {};
    try {
      data = dataText ? JSON.parse(dataText) : {};
    } catch {
      data = { message: dataText };
    }
    onEvent(eventName, data);
  }

  return remaining;
};

const normalizeAskOptions = (filtersOrOptions = {}, topKOverride) => {
  if (
    filtersOrOptions
    && !Array.isArray(filtersOrOptions)
    && typeof filtersOrOptions === 'object'
    && (
      Object.prototype.hasOwnProperty.call(filtersOrOptions, 'filters')
      || Object.prototype.hasOwnProperty.call(filtersOrOptions, 'top_k')
      || Object.prototype.hasOwnProperty.call(filtersOrOptions, 'sessionId')
      || Object.prototype.hasOwnProperty.call(filtersOrOptions, 'session_id')
    )
  ) {
    return {
      filters: filtersOrOptions.filters ?? {},
      top_k: filtersOrOptions.top_k ?? topKOverride ?? 5,
      sessionId: filtersOrOptions.sessionId ?? filtersOrOptions.session_id ?? null,
    };
  }

  return {
    filters: filtersOrOptions ?? {},
    top_k: topKOverride ?? 5,
    sessionId: null,
  };
};

export const qaApi = {
  async askQuestion(query, filtersOrOptions = {}, top_k = 5) {
    const options = normalizeAskOptions(filtersOrOptions, top_k);
    const payload = {
      question: query,
      filters: options.filters,
      top_k: options.top_k,
      ...(options.sessionId ? { session_id: options.sessionId } : {}),
    };

    try {
      const data = await apiConfig.fetchJson('/api/chat/ask', {
        method: 'POST',
        auth: true,
        body: JSON.stringify(payload),
      });
      return normalizeAnswerPayload(data);
    } catch (error) {
      throw new Error(normalizeErrorMessage({ message: error?.message }, error?.message));
    }
  },

  async streamQuestion(
    query,
    { filters = {}, top_k = 5, sessionId = null, onMeta, onChunk, onDone } = {},
  ) {
    const payload = {
      question: query,
      filters,
      top_k,
      ...(sessionId ? { session_id: sessionId } : {}),
    };
    const response = await apiConfig.fetchWithAuth('/api/chat/ask/stream', {
      method: 'POST',
      body: JSON.stringify(payload),
      auth: true,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(normalizeErrorMessage(data, data?.message));
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('当前浏览器不支持流式响应。');
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    const aggregated = {
      answer: '',
      citations: [],
      answer_mode: 'cited',
      answer_notice: '',
      duration_ms: 0,
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      buffer = parseSse(buffer, (eventName, data) => {
        if (eventName === 'meta') {
          aggregated.citations = normalizeCitations(data.citations);
          aggregated.answer_mode = data.answer_mode || aggregated.answer_mode;
          aggregated.answer_notice = data.answer_notice || '';
          aggregated.duration_ms = data.duration_ms || 0;
          onMeta?.({
            citations: aggregated.citations,
            answer_mode: aggregated.answer_mode,
            answer_notice: aggregated.answer_notice,
            duration_ms: aggregated.duration_ms,
          });
          return;
        }

        if (eventName === 'chunk') {
          const content = String(data.content || '');
          aggregated.answer += content;
          onChunk?.(content, { ...aggregated });
          return;
        }

        if (eventName === 'done') {
          const normalized = normalizeAnswerPayload({
            ...data,
            answer: data.answer || aggregated.answer,
          });
          aggregated.answer = normalized.answer;
          aggregated.citations = normalized.citations;
          aggregated.answer_mode = normalized.answer_mode;
          aggregated.answer_notice = normalized.answer_notice;
          aggregated.duration_ms = normalized.duration_ms;
          onDone?.({ ...aggregated });
        }
      });
    }

    return aggregated;
  },
};
