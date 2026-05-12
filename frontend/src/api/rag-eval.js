import { createApiConfig } from './config.js';

const unwrap = (payload) => {
  if (payload && payload.code !== undefined) {
    if (payload.code !== 0 && payload.code !== 200 && payload.code !== 201) {
      throw new Error(payload.message || '请求失败');
    }
    return payload.data;
  }
  return payload;
};

export const createRagEvalApi = (overrides = {}) => {
  const apiConfig = createApiConfig(overrides);
  const fetchJson = overrides.fetchJson || apiConfig.fetchJson;

  return {
    async getEvaluationHistory() {
      return unwrap(await fetchJson('/api/ops/evaluations/', {
        method: 'GET',
        auth: true,
      }));
    },

    async runEvaluation(mode = 'all') {
      return unwrap(await fetchJson('/api/rag/evaluations/', {
        method: 'POST',
        auth: true,
        body: JSON.stringify({ mode }),
      }));
    },

    async getEvaluationStatus(taskId) {
      return unwrap(await fetchJson(`/api/rag/evaluations/${taskId}/status`, {
        method: 'GET',
        auth: true,
      }));
    },

    async runEvaluationWithPolling(mode = 'all', { timeout = 300000, interval = 3000 } = {}) {
      const submitResult = await this.runEvaluation(mode);

      if (submitResult.task_id) {
        const deadline = Date.now() + timeout;
        while (Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, interval));
          const statusResult = await this.getEvaluationStatus(submitResult.task_id);
          if (statusResult.status === 'SUCCESS') {
            return statusResult.result;
          }
          if (statusResult.status === 'FAILURE') {
            throw new Error(statusResult.message || '评测任务失败');
          }
        }
        throw new Error('评测任务超时，请稍后查看结果');
      }

      return submitResult;
    },
  };
};

export const ragEvalApi = createRagEvalApi();
