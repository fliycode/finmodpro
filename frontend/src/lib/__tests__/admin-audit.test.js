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
});

test('formatAuditDetail summarizes safe payload fields and hides noise', () => {
  assert.equal(
    formatAuditDetail({
      username: 'alice',
      groups: ['admin', 'member'],
      has_api_key: true,
      template_length: 128,
      api_key: '[REDACTED]',
    }),
    '用户: alice · 角色组: admin, member · 已配置密钥: 是 · 模板长度: 128',
  );
});
