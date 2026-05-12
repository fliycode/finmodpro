const SYSTEM_ROLE_PRIORITY = {
  super_admin: 0,
  admin: 1,
  member: 2,
};

const ROLE_FALLBACK_DESCRIPTIONS = {
  super_admin: '负责全局治理与最高权限控制，默认保留角色和用户管理能力。',
  admin: '负责运营、模型、监控与治理执行，是日常管理的主角色。',
  member: '面向普通业务成员，默认只保留基础工作台访问能力。',
};

const PERMISSION_DOMAIN_RULES = [
  {
    key: 'governance',
    label: '治理与权限',
    codenames: ['view_dashboard', 'view_role', 'assign_role', 'view_user', 'add_user', 'change_user', 'delete_user', 'view_audit_log'],
  },
  {
    key: 'knowledge',
    label: '知识资产',
    codenames: ['upload_document', 'view_document', 'trigger_ingest', 'delete_document'],
  },
  {
    key: 'qa',
    label: '问答与会话',
    codenames: ['ask_financial_qa', 'view_chat_session'],
  },
  {
    key: 'risk',
    label: '风险治理',
    codenames: ['review_risk_event'],
  },
  {
    key: 'llm',
    label: '模型与评测',
    codenames: ['manage_model_config', 'view_evaluation', 'run_evaluation'],
  },
  {
    key: 'monitoring',
    label: '监控与告警',
    codenames: ['view_monitoring', 'manage_alert_rules', 'acknowledge_alerts'],
  },
  {
    key: 'cleaning',
    label: '数据清洗',
    codenames: ['manage_cleaning_rules', 'trigger_cleaning'],
  },
];

export const getRoleDescription = (role) => (
  role?.description
  || ROLE_FALLBACK_DESCRIPTIONS[role?.name]
  || '自定义角色，可按治理边界自由组合权限。'
);

export const decorateRole = (role) => ({
  ...role,
  description: getRoleDescription(role),
  member_count: Number(role?.member_count ?? 0),
});

export const sortRolesByPriority = (roles = []) => [...roles].sort((left, right) => {
  const leftRank = SYSTEM_ROLE_PRIORITY[left.name] ?? 100;
  const rightRank = SYSTEM_ROLE_PRIORITY[right.name] ?? 100;
  if (leftRank !== rightRank) {
    return leftRank - rightRank;
  }

  return left.name.localeCompare(right.name, 'zh-CN');
});

export const resolvePermissionDomain = (codename) => (
  PERMISSION_DOMAIN_RULES.find((rule) => rule.codenames.includes(codename))
  || { key: 'other', label: '其他能力' }
);

export const groupPermissionsCatalog = (permissions = []) => {
  const buckets = new Map();

  permissions.forEach((permission) => {
    const domain = resolvePermissionDomain(permission.codename);
    if (!buckets.has(domain.key)) {
      buckets.set(domain.key, {
        key: domain.key,
        label: domain.label,
        items: [],
      });
    }

    buckets.get(domain.key).items.push(permission);
  });

  return [...buckets.values()].map((bucket) => ({
    ...bucket,
    items: [...bucket.items].sort((left, right) => left.codename.localeCompare(right.codename, 'en')),
  }));
};

export const roleMatchesQuery = (role, query) => {
  const keyword = query.trim().toLowerCase();
  if (!keyword) {
    return true;
  }

  return [
    role.name,
    role.label,
    role.description,
    role.role_type,
  ].filter(Boolean).join(' ').toLowerCase().includes(keyword);
};
