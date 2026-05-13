import test from 'node:test';
import assert from 'node:assert/strict';

import { createRiskApi } from '../risk.js';

test('extractDocumentWithPolling emits task progress updates before resolving', async () => {
  const responses = [
    {
      ok: true,
      json: async () => ({
        data: {
          task_id: 'risk-task-1',
          status: 'QUEUED',
          progress: 6,
          message: '风险抽取任务已排队。',
        },
      }),
    },
    {
      ok: true,
      json: async () => ({
        data: {
          task_id: 'risk-task-1',
          status: 'RUNNING',
          progress: 72,
          message: '正在分析文档中的风险事件。',
        },
      }),
    },
    {
      ok: true,
      json: async () => ({
        data: {
          task_id: 'risk-task-1',
          status: 'SUCCESS',
          progress: 100,
          result: {
            document_id: 12,
            created_count: 2,
            risk_events: [],
          },
        },
      }),
    },
  ];

  const seenProgress = [];
  const riskApi = createRiskApi({
    baseURL: 'http://example.test',
    fetchImpl: async () => responses.shift(),
  });

  const result = await riskApi.extractDocumentWithPolling(12, {
    interval: 0,
    onProgress: (payload) => seenProgress.push(`${payload.status}:${payload.progress}`),
  });

  assert.deepEqual(seenProgress, ['QUEUED:6', 'RUNNING:72', 'SUCCESS:100']);
  assert.equal(result.document_id, 12);
  assert.equal(result.created_count, 2);
});

test('extractDocumentWithPolling surfaces busy payloads before throwing', async () => {
  const responses = [
    {
      ok: false,
      status: 429,
      json: async () => ({
        code: 429,
        message: '风险提取队列繁忙，请稍后再试。',
        data: {
          status: 'BUSY',
          progress: 100,
          error_code: 'risk_extraction_busy',
          message: '风险提取队列繁忙，请稍后再试。',
        },
      }),
    },
  ];

  const seenProgress = [];
  const riskApi = createRiskApi({
    baseURL: 'http://example.test',
    fetchImpl: async () => responses.shift(),
  });

  await assert.rejects(
    () => riskApi.extractDocumentWithPolling(12, {
      interval: 0,
      onProgress: (payload) => seenProgress.push(`${payload.status}:${payload.error_code}`),
    }),
    (error) => {
      assert.equal(error.code, 'risk_extraction_busy');
      assert.equal(error.message, '风险提取队列繁忙，请稍后再试。');
      return true;
    },
  );

  assert.deepEqual(seenProgress, ['BUSY:risk_extraction_busy']);
});
