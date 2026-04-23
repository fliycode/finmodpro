import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeSession } from '../chat.js';

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
