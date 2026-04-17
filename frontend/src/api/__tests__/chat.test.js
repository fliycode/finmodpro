import test from 'node:test';
import assert from 'node:assert/strict';

import { createChatApi } from '../chat.js';

test('listHistory normalizes session truth fields from backend payloads', async () => {
  let request;
  const api = createChatApi({
    fetchJson: async (path, options) => {
      request = { path, options };
      return {
        data: {
          sessions: [
            {
              id: 18,
              title: '流动性压力测试结论整理',
              title_status: 'ready',
              title_source: 'ai',
              rolling_summary: '用户正在围绕数据集 7 追问流动性与偿债能力。',
              last_message_preview: '已整理出三项高优先级关注点。',
              message_count: 6,
              last_message_at: '2026-04-16T19:00:00+08:00',
              context_filters: { dataset_id: 7 },
            },
          ],
        },
      };
    },
  });

  const sessions = await api.listHistory();

  assert.equal(request.path, '/api/chat/sessions');
  assert.equal(request.options.method, 'GET');
  assert.equal(request.options.auth, true);
  assert.equal(sessions[0].titleStatus, 'ready');
  assert.equal(sessions[0].titleSource, 'ai');
  assert.equal(sessions[0].rollingSummary, '用户正在围绕数据集 7 追问流动性与偿债能力。');
  assert.equal(sessions[0].messageCount, 6);
  assert.equal(sessions[0].lastMessageAt, '2026-04-16T19:00:00+08:00');
  assert.deepEqual(sessions[0].contextFilters, { dataset_id: 7 });
});

test('listHistory also accepts camelCase session truth fields', async () => {
  const api = createChatApi({
    fetchJson: async () => ({
      data: {
        sessions: [
          {
            id: 19,
            title: '现金流预警跟踪',
            titleStatus: 'failed',
            titleSource: 'system',
            rollingSummary: '摘要任务失败，回退到原始消息。',
            lastMessagePreview: '请继续关注现金流覆盖率。',
            messageCount: 3,
            lastMessageAt: '2026-04-17T09:00:00Z',
            contextFilters: { dataset_id: 9 },
          },
        ],
      },
    }),
  });

  const sessions = await api.listHistory();

  assert.deepEqual(sessions[0], {
    id: 19,
    title: '现金流预警跟踪',
    preview: '请继续关注现金流覆盖率。',
    summaryPreview: '摘要任务失败，回退到原始消息。',
    timestamp: sessions[0].timestamp,
    rawTimestamp: '2026-04-17T09:00:00Z',
    updatedAt: '2026-04-17T09:00:00Z',
    titleStatus: 'failed',
    titleSource: 'system',
    rollingSummary: '摘要任务失败，回退到原始消息。',
    messageCount: 3,
    lastMessageAt: '2026-04-17T09:00:00Z',
    contextFilters: { dataset_id: 9 },
  });
});

test('createSession normalizes backend session truth defaults', async () => {
  const api = createChatApi({
    fetchJson: async () => ({
      data: {
        session: {
          id: 5,
          title: '新会话',
          title_status: 'pending',
          title_source: 'ai',
          rolling_summary: '',
          message_count: 0,
          last_message_at: null,
          context_filters: {},
          messages: [],
        },
      },
    }),
  });

  const session = await api.createSession();

  assert.equal(session.id, 5);
  assert.equal(session.titleStatus, 'pending');
  assert.equal(session.titleSource, 'ai');
  assert.equal(session.rollingSummary, '');
  assert.equal(session.messageCount, 0);
  assert.equal(session.lastMessageAt, null);
});

test('createSession also accepts camelCase session truth fields', async () => {
  const api = createChatApi({
    fetchJson: async () => ({
      data: {
        session: {
          id: 7,
          title: '估值口径校准',
          titleStatus: 'ready',
          titleSource: 'manual',
          rollingSummary: '用户确认后续统一采用最新估值口径。',
          messageCount: 1,
          lastMessageAt: '2026-04-17T10:00:00Z',
          createdAt: '2026-04-17T09:55:00Z',
          updatedAt: '2026-04-17T10:00:00Z',
          contextFilters: { dataset_id: 12 },
          messages: [],
        },
      },
    }),
  });

  const session = await api.createSession();

  assert.equal(session.titleStatus, 'ready');
  assert.equal(session.titleSource, 'manual');
  assert.equal(session.rollingSummary, '用户确认后续统一采用最新估值口径。');
  assert.equal(session.messageCount, 1);
  assert.equal(session.lastMessageAt, '2026-04-17T10:00:00Z');
  assert.equal(session.createdAt, '2026-04-17T09:55:00Z');
  assert.equal(session.updatedAt, '2026-04-17T10:00:00Z');
});

test('getSession keeps session truth fields and message bookkeeping fields', async () => {
  const api = createChatApi({
    fetchJson: async () => ({
      data: {
        session: {
          id: 9,
          title: '偿债能力跟踪',
          title_status: 'ready',
          title_source: 'manual',
          rolling_summary: '用户希望持续跟踪偿债压力指标。',
          message_count: 2,
          last_message_at: '2026-04-17T08:00:00Z',
          context_filters: { dataset_id: 3 },
          messages: [
            {
              id: 21,
              sequence: 1,
              role: 'user',
              message_type: 'text',
              status: 'complete',
              citations_json: [{ id: 'doc-1' }],
              model_metadata_json: { model: 'gpt-5.4' },
              client_message_id: 'client-1',
              content: '请总结偿债能力风险。',
              created_at: '2026-04-17T07:59:00Z',
              updated_at: '2026-04-17T07:59:00Z',
            },
          ],
        },
      },
    }),
  });

  const session = await api.getSession(9);

  assert.equal(session.titleStatus, 'ready');
  assert.equal(session.titleSource, 'manual');
  assert.equal(session.rollingSummary, '用户希望持续跟踪偿债压力指标。');
  assert.equal(session.messageCount, 2);
  assert.equal(session.lastMessageAt, '2026-04-17T08:00:00Z');
  assert.deepEqual(session.contextFilters, { dataset_id: 3 });
  assert.deepEqual(session.messages[0], {
    id: 21,
    sequence: 1,
    role: 'user',
    messageType: 'text',
    status: 'complete',
    citationsJson: [{ id: 'doc-1' }],
    modelMetadataJson: { model: 'gpt-5.4' },
    clientMessageId: 'client-1',
    content: '请总结偿债能力风险。',
    createdAt: '2026-04-17T07:59:00Z',
    updatedAt: '2026-04-17T07:59:00Z',
  });
});

test('getSession accepts camelCase message bookkeeping fields and fallback includes timestamps', async () => {
  const api = createChatApi({
    fetchJson: async () => ({
      data: {
        session: {
          id: 10,
          title: '营运资金周转',
          titleStatus: 'ready',
          titleSource: 'ai',
          rollingSummary: '用户正在追问营运资金周转变化。',
          messageCount: 1,
          lastMessageAt: '2026-04-17T11:00:00Z',
          createdAt: '2026-04-17T10:58:00Z',
          updatedAt: '2026-04-17T11:00:00Z',
          contextFilters: {},
          messages: [
            {
              id: 31,
              sequence: 2,
              role: 'assistant',
              messageType: 'text',
              status: 'complete',
              citationsJson: [],
              modelMetadataJson: { model: 'gpt-5.4-mini' },
              clientMessageId: 'client-2',
              content: '周转天数上升主要来自存货积压。',
              createdAt: '2026-04-17T10:59:00Z',
              updatedAt: '2026-04-17T11:00:00Z',
            },
          ],
        },
      },
    }),
  });

  const session = await api.getSession(10);

  assert.equal(session.createdAt, '2026-04-17T10:58:00Z');
  assert.equal(session.updatedAt, '2026-04-17T11:00:00Z');
  assert.deepEqual(session.messages[0], {
    id: 31,
    sequence: 2,
    role: 'assistant',
    messageType: 'text',
    status: 'complete',
    citationsJson: [],
    modelMetadataJson: { model: 'gpt-5.4-mini' },
    clientMessageId: 'client-2',
    content: '周转天数上升主要来自存货积压。',
    createdAt: '2026-04-17T10:59:00Z',
    updatedAt: '2026-04-17T11:00:00Z',
  });
});

test('getSession fallback matches the normalized session shape fully', async () => {
  const api = createChatApi({
    fetchJson: async () => null,
  });

  const session = await api.getSession(88);

  assert.deepEqual(session, {
    id: 88,
    title: '新会话',
    titleStatus: 'pending',
    titleSource: 'ai',
    rollingSummary: '',
    messageCount: 0,
    lastMessageAt: null,
    createdAt: '',
    updatedAt: '',
    contextFilters: {},
    messages: [],
  });
});
