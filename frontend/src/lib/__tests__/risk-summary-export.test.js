import test from 'node:test';
import assert from 'node:assert/strict';

import { buildRiskSummaryExportDownload } from '../risk-summary-export.js';

test('buildRiskSummaryExportDownload returns xlsx with correct filename and type', () => {
  const payload = buildRiskSummaryExportDownload({
    documentTitle: '示例公告.pdf',
    statusText: '已完成',
    detail: '共识别 2 类风险',
    createdCount: 3,
    groupedResults: [
      {
        key: '流动性风险',
        dominantLevel: 'high',
        count: 2,
        summary: '现金流承压，短期偿债能力下降。',
        evidence: '公司披露短期借款集中到期。',
      },
    ],
    resultEvents: [
      {
        risk_level: 'high',
        risk_type: '流动性风险',
        company_name: 'FinModPro Holdings',
        event_date: '2026-05-14',
        summary: '短期偿债压力上升',
        evidence_text: '一年内到期债务显著增加。',
        why_it_matters: '短期债务续作存在不确定性，可能直接影响现金流稳定。',
        requires_human_review: true,
        watchpoints: ['短债续作结果', '现金流覆盖率'],
        citations: [{ chunk_id: 12, page_label: '第 3 页' }],
      },
    ],
    exportedAt: '2026-05-14T06:36:00.000Z',
  });

  assert.equal(payload.filename, '示例公告-risk-summary.xlsx');
  assert.match(payload.contentType, /spreadsheetml/);
  assert.ok(payload.content instanceof Uint8Array);
  assert.ok(payload.content.length > 0);
});

test('buildRiskSummaryExportDownload handles empty-state exports', () => {
  const payload = buildRiskSummaryExportDownload({
    documentTitle: '空结果文档.txt',
    statusText: '已完成',
    groupedResults: [],
    resultEvents: [],
  });

  assert.equal(payload.filename, '空结果文档-risk-summary.xlsx');
  assert.ok(payload.content instanceof Uint8Array);
  assert.ok(payload.content.length > 0);
});
