import { isAdminProfile } from '../lib/session-state.js';
import { hasAnyProfileGroup, hasAnyProfilePermission } from '../lib/permission.js';

export const navigationMap = {
  workspace: [
    { id: 'qa', label: '智能问答', to: '/workspace/qa', icon: 'spark', group: 'workspace-core' },
    { id: 'knowledge', label: '知识库管理', to: '/workspace/knowledge', icon: 'database', group: 'workspace-core' },
    { id: 'history', label: '历史会话', to: '/workspace/history', icon: 'history', group: 'workspace-support' },
    { id: 'risk', label: '风险与摘要', to: '/workspace/risk', icon: 'shield', group: 'workspace-core' },
  ],
  admin: [
    {
      id: 'admin-overview',
      label: '数据看板',
      to: '/admin/overview',
      icon: 'dashboard',
      group: 'admin-overview',
      requiredPermissions: ['view_dashboard'],
    },
    {
      id: 'admin-knowledge',
      label: '知识库管理',
      to: '/admin/knowledge',
      icon: 'database',
      group: 'admin-overview',
      requiredPermissions: ['view_document'],
    },
    {
      id: 'admin-users',
      label: '用户管理',
      to: '/admin/users',
      icon: 'users',
      group: 'admin-governance',
      requiredPermissions: ['view_user'],
    },
    {
      id: 'admin-roles',
      label: '权限管理',
      to: '/admin/roles',
      icon: 'shield',
      group: 'admin-governance',
      requiredPermissions: ['view_role'],
    },
    {
      id: 'admin-monitoring',
      label: '系统监控',
      to: '/admin/monitoring',
      icon: 'activity',
      group: 'admin-overview',
      requiredPermissions: ['view_monitoring'],
    },
    {
      id: 'admin-cleaning',
      label: '数据清洗',
      to: '/admin/cleaning',
      icon: 'sparkles',
      group: 'admin-overview',
      requiredPermissions: ['manage_cleaning_rules'],
    },
    {
      id: 'admin-llm-management',
      label: '模型管理',
      to: '/admin/llm/models',
      icon: 'brain-circuit',
      group: 'admin-llm',
      requiredPermissions: ['manage_model_config', 'view_evaluation', 'run_evaluation'],
      children: [
        { id: 'admin-llm-model-overview', label: '模型总览', to: '/admin/llm/models', requiredPermissions: ['manage_model_config'] },
        { id: 'admin-llm-logs', label: '模型日志', to: '/admin/llm/logs', requiredPermissions: ['manage_model_config'] },
        { id: 'admin-llm-usage', label: '用量统计', to: '/admin/llm/usage', requiredPermissions: ['manage_model_config'] },
        { id: 'admin-llm-rag-eval', label: 'RAG 评测', to: '/admin/llm/rag-evaluation', requiredPermissions: ['view_evaluation', 'run_evaluation'] },
      ],
    },
    {
      id: 'admin-audit-logs',
      label: '操作日志',
      to: '/admin/audit-logs',
      icon: 'clipboard',
      group: 'admin-governance',
      requiredPermissions: ['view_audit_log'],
    },
  ],
};

const hasItemAccess = (item, profile) => {
  if (item.requiredPermissions?.length && !hasAnyProfilePermission(profile, item.requiredPermissions)) {
    return false;
  }

  if (item.requiredGroups?.length && !hasAnyProfileGroup(profile, item.requiredGroups)) {
    return false;
  }

  return true;
};

const filterNavItems = (items, profile) => items.reduce((visibleItems, item) => {
  const children = item.children?.length ? filterNavItems(item.children, profile) : [];
  const nextItem = children.length
    ? {
        ...item,
        children,
        to: children.some((child) => child.to === item.to) ? item.to : children[0].to,
      }
    : item;

  if (!hasItemAccess(nextItem, profile) && !children.length) {
    return visibleItems;
  }

  if (children.length && !hasItemAccess(nextItem, profile)) {
    return visibleItems;
  }

  visibleItems.push(nextItem);
  return visibleItems;
}, []);

export const getNavItems = (area, profile) => {
  if (area === 'admin' && !isAdminProfile(profile)) {
    return [];
  }

  return filterNavItems(navigationMap[area] ?? [], profile);
};

export const getTopbarActions = (area, profile) => {
  const actions = [];
  const isAdmin = isAdminProfile(profile);

  if (area === 'admin' && isAdmin) {
    actions.push({ id: 'go-workspace', label: '返回工作区', to: '/workspace/qa' });
  }

  if (area === 'workspace' && isAdmin) {
    actions.push({ id: 'go-admin', label: '进入管理台', to: '/admin/overview' });
  }

  actions.push({ id: 'logout', label: '退出登录', to: '/login' });
  return actions;
};
