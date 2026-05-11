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

  const requestJson = async (path, { method = 'GET', body, signal } = {}) => {
    return apiConfig.fetchJson(path, {
      method,
      body: body ? JSON.stringify(body) : undefined,
      auth: true,
      signal,
    });
  };

  return {
    getEvents(params = {}, { signal } = {}) {
      const queryString = buildQueryString(params);
      const path = queryString ? `/api/risk/events?${queryString}` : '/api/risk/events';
      return requestJson(path, { signal });
    },

    reviewEvent(eventId, reviewStatus, { signal } = {}) {
      return requestJson(`/api/risk/events/${eventId}/review`, {
        method: 'POST',
        body: { review_status: reviewStatus },
        signal,
      });
    },

    extractDocument(documentId) {
      return requestJson(`/api/risk/documents/${documentId}/extract`, {
        method: 'POST',
        body: {},
      });
    },

    getExtractStatus(taskId) {
      return requestJson(`/api/risk/documents/extract/status/${taskId}`, {
        method: 'GET',
      });
    },

    async extractDocumentWithPolling(documentId, { timeout = 300000, interval = 3000 } = {}) {
      const submitResult = await this.extractDocument(documentId);
      const data = submitResult.data || submitResult;

      if (data.task_id) {
        const deadline = Date.now() + timeout;
        while (Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, interval));
          const statusResult = await this.getExtractStatus(data.task_id);
          const statusData = statusResult.data || statusResult;
          if (statusData.status === 'SUCCESS') {
            return statusData.result;
          }
          if (statusData.status === 'FAILURE') {
            throw new Error(statusData.message || '风险抽取任务失败');
          }
        }
        throw new Error('风险抽取任务超时，请稍后查看结果');
      }

      return data;
    },

    generateCompanyReport(data, { signal } = {}) {
      return requestJson('/api/risk/reports/company', {
        method: 'POST',
        body: data,
        signal,
      });
    },

    generateTimeRangeReport(data, { signal } = {}) {
      return requestJson('/api/risk/reports/time-range', {
        method: 'POST',
        body: data,
        signal,
      });
    },

    getAnalytics(params = {}, { signal } = {}) {
      const queryString = buildQueryString(params);
      const path = queryString
        ? `/api/risk/analytics/overview?${queryString}`
        : '/api/risk/analytics/overview';
      return requestJson(path, { signal });
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
