import { isAdminProfile } from '../lib/session-state.js';

export const navigationMap = {
  workspace: [
    { id: 'qa', label: '智能问答', to: '/workspace/qa', icon: 'spark' },
    { id: 'knowledge', label: '知识库管理', to: '/workspace/knowledge', icon: 'database' },
    { id: 'history', label: '历史会话', to: '/workspace/history', icon: 'history' },
    { id: 'risk', label: '风险与摘要', to: '/workspace/risk', icon: 'shield' },
    { id: 'sentiment', label: '舆情分析', to: '/workspace/sentiment', icon: 'trending-up' },
  ],
  admin: [
    { id: 'admin-overview', label: '仪表盘', to: '/admin/overview', icon: 'dashboard', group: 'admin-overview' },
    { id: 'admin-users', label: '用户管理', to: '/admin/users', icon: 'users', group: 'admin-governance' },
    { id: 'admin-llm-overview', label: 'Gateway', to: '/admin/llm', icon: 'network', group: 'admin-llm' },
    { id: 'admin-llm-models', label: 'Models / Routing', to: '/admin/llm/models', icon: 'sliders', group: 'admin-llm' },
    { id: 'admin-llm-observability', label: 'Logs / Observability', to: '/admin/llm/observability', icon: 'eye', group: 'admin-llm' },
    { id: 'admin-llm-costs', label: 'Cost / Usage', to: '/admin/llm/costs', icon: 'bar-chart', group: 'admin-llm' },
    { id: 'admin-llm-fine-tunes', label: 'Fine-tunes / LLaMA-Factory', to: '/admin/llm/fine-tunes', icon: 'microscope', group: 'admin-llm' },
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
