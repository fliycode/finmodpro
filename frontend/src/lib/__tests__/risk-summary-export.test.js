import test from 'node:test';
import assert from 'node:assert/strict';

import { buildRiskSummaryExportDownload } from '../risk-summary-export.js';

test('buildRiskSummaryExportDownload renders markdown with grouped and raw risk events', () => {
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
      },
    ],
    exportedAt: '2026-05-14T06:36:00.000Z',
  });

  assert.equal(payload.filename, '示例公告-risk-summary.md');
  assert.match(payload.content, /# 风险提取结果/);
  assert.match(payload.content, /流动性风险/);
  assert.match(payload.content, /风险等级：高/);
  assert.match(payload.content, /FinModPro Holdings/);
  assert.match(payload.content, /本次新增：3 条/);
});

test('buildRiskSummaryExportDownload records empty-state exports', () => {
  const payload = buildRiskSummaryExportDownload({
    documentTitle: '空结果文档.txt',
    statusText: '已完成',
    groupedResults: [],
    resultEvents: [],
  });

  assert.match(payload.content, /当前文档未识别到风险事件/);
  assert.match(payload.content, /无原始事件记录/);
});
