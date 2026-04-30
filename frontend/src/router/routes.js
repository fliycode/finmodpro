export function getDefaultRouteForRole(profile) {
  const groups = profile?.groups ?? [];
  const permissions = profile?.permissions ?? [];
  const isAdmin = groups.includes('admin') || groups.includes('super_admin') || permissions.includes('admin');

  return isAdmin ? '/admin/overview' : '/workspace/qa';
}

export const appRoutes = [
  {
    path: '/login',
    component: () => import('../layouts/AuthLayout.vue'),
    meta: { public: true },
    children: [
      {
        path: '',
        component: () => import('../views/auth/AuthView.vue'),
      },
    ],
  },
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/workspace',
    component: () => import('../layouts/WorkspaceLayout.vue'),
    meta: { requiresAuth: true },
    beforeEnter: (to) => {
      if (to.path === '/workspace') {
        return '/workspace/qa';
      }

      return true;
    },
    children: [
      {
        path: 'qa',
        component: () => import('../views/workspace/WorkspaceQaView.vue'),
        meta: { title: '智能问答', subtitle: '基于金融领域知识的精准问答与分析' },
      },
      {
        path: 'knowledge',
        component: () => import('../views/workspace/WorkspaceKnowledgeView.vue'),
        meta: { title: '知识检索与文档管理' },
      },
      {
        path: 'history',
        component: () => import('../views/workspace/WorkspaceHistoryView.vue'),
        meta: { title: '历史会话', subtitle: '检索、回看、导出真实会话记录' },
      },
      {
        path: 'profile',
        component: () => import('../views/workspace/WorkspaceProfileView.vue'),
        meta: { title: '个人信息' },
      },
      {
        path: 'risk',
        component: () => import('../views/workspace/WorkspaceRiskView.vue'),
        meta: { title: '风险与摘要' },
      },
      {
        path: 'sentiment',
        component: () => import('../views/workspace/WorkspaceSentimentView.vue'),
        meta: { title: '舆情分析' },
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    beforeEnter: (to) => {
      if (to.path === '/admin') {
        return '/admin/overview';
      }

      return true;
    },
    children: [
      {
        path: 'overview',
        component: () => import('../views/admin/AdminOverviewView.vue'),
        meta: { title: '数据看板', subtitle: '全局风险态势感知，联动知识库、问答链路、风险提取与系统审计。' },
      },
      {
        path: 'users',
        component: () => import('../views/admin/AdminUsersView.vue'),
        meta: { title: '用户管理' },
      },
      {
        path: 'llm',
        component: () => import('../views/admin/AdminLlmOverviewView.vue'),
        meta: { title: 'LLM 中台总览', subtitle: '基础设施接入、模型链路状态与运行摘要。' },
      },
      {
        path: 'llm/models',
        component: () => import('../views/admin/AdminLlmModelsView.vue'),
        meta: { title: 'Models / Routing' },
      },
      {
        path: 'llm/observability',
        component: () => import('../views/admin/AdminLlmObservabilityView.vue'),
        meta: { title: '观测与异常摘要', subtitle: '调用量、命中情况、失败事件与观测入口。' },
      },
      {
        path: 'llm/costs',
        component: () => import('../views/admin/AdminLlmCostsView.vue'),
        meta: { title: 'Cost / Usage' },
      },
      {
        path: 'llm/knowledge',
        component: () => import('../views/admin/AdminLlmKnowledgeView.vue'),
        meta: { title: '知识库解析与入库链路', subtitle: '文档解析链路可用性与入库治理。' },
      },
      {
        path: 'llm/fine-tunes',
        component: () => import('../views/admin/AdminLlmFineTunesView.vue'),
        meta: { title: 'Fine-tunes / LLaMA-Factory' },
      },
      {
        path: 'models',
        redirect: '/admin/llm/models',
      },
      {
        path: 'evaluation',
        component: () => import('../views/admin/AdminEvaluationView.vue'),
        meta: { title: '评测结果' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login',
  },
];
