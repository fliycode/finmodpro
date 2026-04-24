import test from 'node:test';
import assert from 'node:assert/strict';

import { createChatApi, normalizeSession } from '../chat.js';

test('normalizeSession maps persisted citations_json to message citations for rendering', () => {
  const session = normalizeSession({
    data: {
      session: {
        id: 9,
        title: '带引用的会话',
        messages: [
          {
            id: 1,
            role: 'assistant',
            content: '根据[1]，资本充足率保持稳定。',
            citations_json: [
              {
                document_title: '压力测试报告',
                doc_type: 'pdf',
                page_label: 'p.3',
                snippet: '资本充足率压力测试结果。',
              },
            ],
          },
        ],
      },
    },
  });

  assert.deepEqual(session.messages[0].citations, [
    {
      document_title: '压力测试报告',
      doc_type: 'pdf',
      page_label: 'p.3',
      snippet: '资本充足率压力测试结果。',
    },
  ]);
});

test('deleteSession sends a DELETE request to the session endpoint', async () => {
  const requests = [];
  const chatApi = createChatApi({
    fetchJson: async (path, options) => {
      requests.push({ path, options });
      return { code: 0, data: { session_id: 12 } };
    },
  });

  const payload = await chatApi.deleteSession(12);

  assert.deepEqual(payload, { code: 0, data: { session_id: 12 } });
  assert.deepEqual(requests, [
    {
      path: '/api/chat/sessions/12',
      options: {
        method: 'DELETE',
        auth: true,
      },
    },
  ]);
});
