import { createApiConfig } from './config.js';

const parseAttachmentError = async (response) => {
  const data = await response.json().catch(() => ({}));
  throw new Error(data.message || '请求失败，请稍后重试');
};

const buildQueryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value);
    }
  });
  return query.toString();
};

const resolveFilenameFromDisposition = (contentDisposition, fallback) => {
  const match = /filename="([^"]+)"/i.exec(String(contentDisposition || ''));
  return match?.[1] || fallback;
};

export const createRiskApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);

  const requestJson = async (path, { method = 'GET', body } = {}) => {
    return apiConfig.fetchJson(path, {
      method,
      body: body ? JSON.stringify(body) : undefined,
      auth: true,
    });
  };

  return {
    getEvents(params = {}) {
      const queryString = buildQueryString(params);
      const path = queryString ? `/api/risk/events?${queryString}` : '/api/risk/events';
      return requestJson(path);
    },

    reviewEvent(eventId, reviewStatus) {
      return requestJson(`/api/risk/events/${eventId}/review`, {
        method: 'POST',
        body: { review_status: reviewStatus },
      });
    },

    retryExtractDocument(documentId) {
      return requestJson(`/api/risk/documents/${documentId}/extract/retry`, {
        method: 'POST',
        body: {},
      });
    },

    retryBatchExtract(documentIds = []) {
      return requestJson('/api/risk/documents/extract-batch/retry', {
        method: 'POST',
        body: { document_ids: documentIds },
      });
    },

    generateCompanyReport(data) {
      return requestJson('/api/risk/reports/company', {
        method: 'POST',
        body: data,
      });
    },

    generateTimeRangeReport(data) {
      return requestJson('/api/risk/reports/time-range', {
        method: 'POST',
        body: data,
      });
    },

    getAnalytics(params = {}) {
      const queryString = buildQueryString(params);
      const path = queryString
        ? `/api/risk/analytics/overview?${queryString}`
        : '/api/risk/analytics/overview';
      return requestJson(path);
    },

    async exportReport(reportId, { format = 'markdown' } = {}) {
      const queryString = buildQueryString({ format });
      const path = queryString
        ? `/api/risk/reports/${reportId}/export?${queryString}`
        : `/api/risk/reports/${reportId}/export`;

      const response = await apiConfig.fetchWithAuth(path, {
        method: 'GET',
        auth: true,
      });

      if (!response.ok) {
        return parseAttachmentError(response);
      }

      return {
        filename: resolveFilenameFromDisposition(
          response.headers?.get?.('Content-Disposition'),
          `risk-report-${reportId}.${format === 'json' ? 'json' : 'md'}`,
        ),
        contentType: response.headers?.get?.('Content-Type') || 'text/plain; charset=utf-8',
        content: await response.text(),
      };
    },
  };
};

export const riskApi = createRiskApi();
