import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatAuditAction,
  formatAuditDetail,
  formatAuditStatus,
  getAuditActionTone,
} from '../admin-audit.js';

test('formatAuditAction localizes new admin governance audit actions', () => {
  assert.equal(formatAuditAction('rbac.user.create'), '创建用户');
  assert.equal(formatAuditAction('llm.model_config.test_connection'), '测试模型连接');
  assert.equal(formatAuditAction('llm.fine_tune_run.dispatch'), '派发微调任务');
  assert.equal(formatAuditAction('knowledgebase.document.batch_delete'), '批量删除文档');
});

test('formatAuditStatus covers submitted and skipped states', () => {
  assert.equal(formatAuditStatus('submitted'), '已提交');
  assert.equal(formatAuditStatus('skipped'), '已跳过');
  assert.equal(formatAuditStatus('failed'), '失败');
});

test('getAuditActionTone distinguishes destructive and neutral admin actions', () => {
  assert.equal(getAuditActionTone('rbac.user.delete'), 'risk');
  assert.equal(getAuditActionTone('rbac.user.groups.replace'), 'accent');
  assert.equal(getAuditActionTone('llm.model_config.create'), 'brand');
  assert.equal(getAuditActionTone('knowledgebase.document.clean'), 'accent');
});

test('formatAuditDetail summarizes safe payload fields and hides noise', () => {
  assert.equal(
    formatAuditDetail({
      title: 'Q1 风险纪要',
      dataset_name: '2025 年报数据集',
      accepted_count: 3,
      failed_count: 1,
      document_ids: [101, 102, 103],
    }),
    '标题: Q1 风险纪要 · 数据集: 2025 年报数据集 · 接受数: 3 · 失败: 1',
  );
});
