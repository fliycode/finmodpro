const ACTION_LABELS = Object.freeze({
  'knowledgebase.ingest': '知识入库',
  'knowledgebase.dataset.create': '创建数据集',
  'knowledgebase.document.upload': '上传文档',
  'knowledgebase.document.delete': '删除文档',
  'knowledgebase.document.batch_ingest': '批量提交入库',
  'knowledgebase.document.batch_delete': '批量删除文档',
  'knowledgebase.document_version.upload': '上传文档新版本',
  'knowledgebase.cleaning_rule.create': '新增清洗规则',
  'knowledgebase.cleaning_rule.update': '更新清洗规则',
  'knowledgebase.cleaning_rule.delete': '删除清洗规则',
  'knowledgebase.document.clean': '执行文档清洗',
  'risk.extract': '风险提取',
  'risk.extract.retry': '重试风险提取',
  'risk.batch_extract': '批量风险提取',
  'risk.batch_extract.retry': '重试批量提取',
  'risk.sentiment': '舆情分析',
  'rbac.user.create': '创建用户',
  'rbac.user.update': '更新用户',
  'rbac.user.delete': '删除用户',
  'rbac.user.groups.replace': '调整用户角色',
  'llm.model_config.create': '新增模型配置',
  'llm.model_config.update': '更新模型配置',
  'llm.model_config.delete': '删除模型配置',
  'llm.model_config.set_active_state': '切换模型启用状态',
  'llm.model_config.test_connection': '测试模型连接',
  'llm.prompt_config.update': '更新 Prompt 模板',
  'llm.evaluation.run': '执行模型评测',
  'llm.fine_tune_runner_server.create': '新增训练服务器',
  'llm.fine_tune_runner_server.update': '更新训练服务器',
  'llm.fine_tune_runner_server.delete': '删除训练服务器',
  'llm.fine_tune_run.create': '创建微调任务',
  'llm.fine_tune_run.update': '更新微调任务',
  'llm.fine_tune_run.dispatch': '派发微调任务',
});

const STATUS_LABELS = Object.freeze({
  submitted: '已提交',
  queued: '排队中',
  running: '进行中',
  succeeded: '成功',
  failed: '失败',
  pending: '待处理',
  approved: '已通过',
  rejected: '已驳回',
  retried: '已重试',
  skipped: '已跳过',
});

const ACTION_TONES = Object.freeze({
  'knowledgebase.ingest': 'brand',
  'knowledgebase.dataset.create': 'brand',
  'knowledgebase.document.upload': 'brand',
  'knowledgebase.document.delete': 'risk',
  'knowledgebase.document.batch_ingest': 'accent',
  'knowledgebase.document.batch_delete': 'risk',
  'knowledgebase.document_version.upload': 'brand',
  'knowledgebase.cleaning_rule.create': 'brand',
  'knowledgebase.cleaning_rule.update': 'accent',
  'knowledgebase.cleaning_rule.delete': 'risk',
  'knowledgebase.document.clean': 'accent',
  'risk.extract': 'risk',
  'risk.extract.retry': 'risk',
  'risk.batch_extract': 'risk',
  'risk.batch_extract.retry': 'risk',
  'risk.sentiment': 'accent',
  'rbac.user.create': 'brand',
  'rbac.user.update': 'brand',
  'rbac.user.delete': 'risk',
  'rbac.user.groups.replace': 'accent',
  'llm.model_config.create': 'brand',
  'llm.model_config.update': 'brand',
  'llm.model_config.delete': 'risk',
  'llm.model_config.set_active_state': 'accent',
  'llm.model_config.test_connection': 'accent',
  'llm.prompt_config.update': 'brand',
  'llm.evaluation.run': 'accent',
  'llm.fine_tune_runner_server.create': 'brand',
  'llm.fine_tune_runner_server.update': 'brand',
  'llm.fine_tune_runner_server.delete': 'risk',
  'llm.fine_tune_run.create': 'brand',
  'llm.fine_tune_run.update': 'accent',
  'llm.fine_tune_run.dispatch': 'accent',
});

const DETAIL_LABELS = Object.freeze({
  username: '用户',
  email: '邮箱',
  groups: '角色组',
  previous_groups: '原角色组',
  is_staff: '后台账号',
  is_superuser: '超级管理员',
  name: '名称',
  title: '标题',
  filename: '文件名',
  doc_type: '文档类型',
  visibility: '可见性',
  file_size: '文件大小',
  capability: '能力',
  provider: '供应商',
  model_name: '模型',
  parameter_scale: '参数规模',
  endpoint: '地址',
  is_active: '已启用',
  has_api_key: '已配置密钥',
  has_auth_token: '已配置令牌',
  price_currency: '币种',
  key: 'Key',
  category: '分类',
  variable_names: '变量',
  template_length: '模板长度',
  task_type: '任务类型',
  evaluation_mode: '评测模式',
  target_name: '目标',
  model_config_id: '模型配置 ID',
  dataset_name: '数据集',
  dataset_version: '数据集版本',
  description_length: '描述长度',
  owner_id: '归属人 ID',
  uploader_id: '上传人 ID',
  document_count: '文档数',
  document_ids: '文档 ID',
  document_id_overflow: '更多文档数',
  accepted_count: '接受数',
  skipped_count: '跳过数',
  failed_count: '失败',
  deleted_count: '删除数',
  root_document_id: '根文档 ID',
  version_number: '版本号',
  source_date: '源日期',
  source_type: '来源类型',
  source_label: '来源标签',
  source_metadata_keys: '来源元数据键',
  processing_notes_present: '含处理备注',
  priority: '优先级',
  enabled: '启用',
  config_keys: '配置键',
  rules_applied_count: '应用规则数',
  issues_found_count: '发现问题数',
  quality_score: '质量分',
  original_length: '原文长度',
  cleaned_length: '清洗后长度',
  dedup_count: '去重数',
  version: '版本',
  base_model_id: '基础模型 ID',
  base_model_name: '基础模型',
  strategy: '策略',
  status: '业务状态',
  runner_server_id: '训练服务器 ID',
  runner_server_name: '训练服务器',
  runner_name: 'Runner',
  job_id: '任务号',
  dispatch_status: '派发状态',
  default_work_dir: '工作目录',
  error: '错误',
});

const DETAIL_ORDER = Object.freeze([
  'username',
  'name',
  'title',
  'task_type',
  'base_model_name',
  'model_name',
  'provider',
  'groups',
  'previous_groups',
  'capability',
  'dataset_name',
  'dataset_version',
  'document_count',
  'accepted_count',
  'deleted_count',
  'skipped_count',
  'failed_count',
  'strategy',
  'runner_server_name',
  'runner_name',
  'job_id',
  'dispatch_status',
  'is_active',
  'has_api_key',
  'has_auth_token',
  'template_length',
  'variable_names',
  'version_number',
  'source_type',
  'source_label',
  'quality_score',
  'version',
  'error',
]);

function hasDisplayValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
}

function formatDetailValue(value) {
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (typeof value === 'object' && value !== null) {
    return `${Object.keys(value).length} 项`;
  }
  return String(value);
}

export function formatAuditAction(action) {
  return ACTION_LABELS[action] || action || '--';
}

export function formatAuditStatus(status) {
  return STATUS_LABELS[status] || status || '--';
}

export function getAuditActionTone(action) {
  return ACTION_TONES[action] || 'neutral';
}

export function formatAuditDetail(detailPayload) {
  if (!detailPayload || typeof detailPayload !== 'object' || Array.isArray(detailPayload)) {
    return '--';
  }

  const entries = Object.entries(detailPayload)
    .filter(([, value]) => hasDisplayValue(value))
    .sort(([keyA], [keyB]) => {
      const indexA = DETAIL_ORDER.indexOf(keyA);
      const indexB = DETAIL_ORDER.indexOf(keyB);
      const safeIndexA = indexA === -1 ? DETAIL_ORDER.length : indexA;
      const safeIndexB = indexB === -1 ? DETAIL_ORDER.length : indexB;
      if (safeIndexA !== safeIndexB) {
        return safeIndexA - safeIndexB;
      }
      return keyA.localeCompare(keyB, 'zh-CN');
    })
    .slice(0, 4);

  if (!entries.length) {
    return '--';
  }

  return entries
    .map(([key, value]) => `${DETAIL_LABELS[key] || key}: ${formatDetailValue(value)}`)
    .join(' · ');
}
