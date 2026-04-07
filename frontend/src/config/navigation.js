import { isAdminProfile } from '../lib/session-state.js';

export const navigationMap = {
  workspace: [
    { id: 'qa', label: '智能问答', to: '/workspace/qa', icon: 'spark' },
    { id: 'knowledge', label: '知识库管理', to: '/workspace/knowledge', icon: 'database' },
    { id: 'history', label: '历史会话', to: '/workspace/history', icon: 'history' },
    { id: 'risk', label: '风险与摘要', to: '/workspace/risk', icon: 'shield' },
  ],
  admin: [
    { id: 'admin-overview', label: '仪表盘', to: '/admin/overview', icon: 'dashboard' },
    { id: 'admin-users', label: '用户管理', to: '/admin/users', icon: 'users' },
    { id: 'admin-models', label: '模型配置', to: '/admin/models', icon: 'sliders' },
    { id: 'admin-evaluation', label: '评测结果', to: '/admin/evaluation', icon: 'beaker' },
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
