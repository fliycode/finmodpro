import { isAdminProfile } from '../lib/session-state.js';

export const navigationMap = {
  workspace: [
    { id: 'qa', label: '智能问答', to: '/workspace/qa', icon: 'spark', group: 'workspace-core' },
    { id: 'knowledge', label: '知识库管理', to: '/workspace/knowledge', icon: 'database', group: 'workspace-core' },
    { id: 'history', label: '历史会话', to: '/workspace/history', icon: 'history', group: 'workspace-support' },
    { id: 'risk', label: '风险与摘要', to: '/workspace/risk', icon: 'shield', group: 'workspace-core' },
    { id: 'sentiment', label: '舆情分析', to: '/workspace/sentiment', icon: 'trending-up', group: 'workspace-core' },
  ],
  admin: [
    { id: 'admin-overview', label: '数据看板', to: '/admin/overview', icon: 'dashboard', group: 'admin-overview' },
    { id: 'admin-knowledge', label: '知识库管理', to: '/admin/knowledge', icon: 'database', group: 'admin-overview' },
    { id: 'admin-users', label: '用户管理', to: '/admin/users', icon: 'users', group: 'admin-governance' },
    { id: 'admin-llm-overview', label: '网关总览', to: '/admin/llm', icon: 'network', group: 'admin-llm' },
    { id: 'admin-llm-models', label: '模型路由', to: '/admin/llm/models', icon: 'sliders', group: 'admin-llm' },
    { id: 'admin-llm-observability', label: '观测与日志', to: '/admin/llm/observability', icon: 'eye', group: 'admin-llm' },
    { id: 'admin-llm-costs', label: '成本与用量', to: '/admin/llm/costs', icon: 'bar-chart', group: 'admin-llm' },
    { id: 'admin-llm-fine-tunes', label: '微调管理', to: '/admin/llm/fine-tunes', icon: 'microscope', group: 'admin-llm' },
    { id: 'admin-evaluation', label: '评测结果', to: '/admin/evaluation', icon: 'check', group: 'admin-governance' },
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
