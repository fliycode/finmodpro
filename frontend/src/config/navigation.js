import { isAdminProfile } from '../lib/session-state.js';

export const navigationMap = {
  workspace: [
    { id: 'qa', label: '智能问答', to: '/workspace/qa', icon: 'spark', group: 'workspace-core' },
    { id: 'knowledge', label: '知识库管理', to: '/workspace/knowledge', icon: 'database', group: 'workspace-core' },
    { id: 'history', label: '历史会话', to: '/workspace/history', icon: 'history', group: 'workspace-support' },
    { id: 'risk', label: '风险与摘要', to: '/workspace/risk', icon: 'shield', group: 'workspace-core' },
  ],
  admin: [
    { id: 'admin-overview', label: '数据看板', to: '/admin/overview', icon: 'dashboard', group: 'admin-overview' },
    { id: 'admin-knowledge', label: '知识库管理', to: '/admin/knowledge', icon: 'database', group: 'admin-overview' },
    { id: 'admin-users', label: '用户管理', to: '/admin/users', icon: 'users', group: 'admin-governance' },
    {
      id: 'admin-llm-management',
      label: '模型管理',
      to: '/admin/llm/models',
      icon: 'brain-circuit',
      group: 'admin-llm',
      children: [
        { id: 'admin-llm-model-overview', label: '模型总览', to: '/admin/llm/models' },
        { id: 'admin-llm-logs', label: '模型日志', to: '/admin/llm/logs' },
        { id: 'admin-llm-usage', label: '用量统计', to: '/admin/llm/usage' },
        { id: 'admin-llm-rag-eval', label: 'RAG 评测', to: '/admin/llm/rag-evaluation' },
      ],
    },
    { id: 'admin-audit-logs', label: '操作日志', to: '/admin/audit-logs', icon: 'clipboard', group: 'admin-governance' },
  ],
};

export const getNavItems = (area, profile) => {
  if (area === 'admin' && !isAdminProfile(profile)) {
    return [];
  }

  return navigationMap[area] ?? [];
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
