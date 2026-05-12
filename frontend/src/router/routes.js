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
        meta: { title: '知识检索与文档管理', subtitle: '多源金融文档的统一检索、解析与知识库管理。' },
      },
      {
        path: 'knowledge/documents/:id',
        component: () => import('../views/workspace/WorkspaceKnowledgeDetailView.vue'),
        meta: { title: '文档详情' },
      },
      {
        path: 'history',
        component: () => import('../views/workspace/WorkspaceHistoryView.vue'),
        meta: { title: '历史会话', subtitle: '检索、回看、导出真实会话记录' },
      },
      {
        path: 'profile',
        component: () => import('../views/workspace/WorkspaceProfileView.vue'),
        meta: { title: '个人信息', subtitle: '查看与编辑个人账户信息、权限与安全设置。' },
      },
      {
        path: 'risk',
        component: () => import('../views/workspace/WorkspaceRiskView.vue'),
        meta: { title: '风险与摘要', subtitle: '多维风险指标监控、异常检测与智能摘要生成。' },
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
        meta: { title: '数据看板', subtitle: '聚焦模型调用、审计操作与知识资产入库节奏。', breadcrumb: [{ label: '数据看板' }] },
      },
      {
        path: 'users',
        component: () => import('../views/admin/AdminUsersView.vue'),
        meta: { title: '用户管理', subtitle: '管理平台用户账号、角色分配与访问权限。', breadcrumb: [{ label: '治理审阅' }, { label: '用户管理' }] },
      },
      {
        path: 'knowledge',
        component: () => import('../views/admin/AdminKnowledgeView.vue'),
        meta: { title: '知识库管理', subtitle: '管理员视角查看知识资产、入库链路、存储和向量资源指标。', breadcrumb: [] },
      },
      {
        path: 'knowledge/documents/:id',
        component: () => import('../views/admin/AdminKnowledgeDetailView.vue'),
        meta: { title: '文档详情', breadcrumb: [{ label: '知识库管理', to: '/admin/knowledge' }, { label: '文档详情' }] },
      },
      {
        path: 'llm',
        redirect: '/admin/llm/models',
      },
      {
        path: 'llm/models',
        component: () => import('../views/admin/AdminLlmModelsView.vue'),
        meta: { title: '模型总览', subtitle: '管理模型启停、基础信息与调用概况。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '模型管理' }, { label: '模型总览' }] },
      },
      {
        path: 'llm/logs',
        component: () => import('../views/admin/AdminLlmObservabilityView.vue'),
        meta: { title: '模型日志', subtitle: '按模型查看调用记录、错误分布与链路细节。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '模型管理' }, { label: '模型日志' }] },
      },
      {
        path: 'llm/observability',
        redirect: '/admin/llm/logs',
      },
      {
        path: 'llm/usage',
        component: () => import('../views/admin/AdminLlmCostsView.vue'),
        meta: { title: '用量统计', subtitle: '按模型和时间窗口追踪调用量、Token 与成本。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '模型管理' }, { label: '用量统计' }] },
      },
      {
        path: 'llm/costs',
        redirect: '/admin/llm/usage',
      },
      {
        path: 'llm/knowledge',
        component: () => import('../views/admin/AdminLlmKnowledgeView.vue'),
        meta: { title: '知识库解析与入库链路', subtitle: '文档解析链路可用性与入库治理。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '知识库解析' }] },
      },
      {
        path: 'llm/rag-evaluation',
        component: () => import('../views/admin/AdminRagEvalView.vue'),
        meta: { title: 'RAG 评测', subtitle: '运行检索与生成质量评测，查看 Recall、MRR、忠实度等指标。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '模型管理' }, { label: 'RAG 评测' }] },
      },
      {
        path: 'graph',
        redirect: '/admin/knowledge',
      },
      {
        path: 'monitoring',
        component: () => import('../views/admin/AdminMonitoringView.vue'),
        meta: { title: '系统监控', subtitle: '系统资源、服务健康与告警管理。', breadcrumb: [{ label: '数据看板' }, { label: '系统监控' }] },
      },
      {
        path: 'notifications',
        component: () => import('../views/admin/AdminAlertNotificationsView.vue'),
        meta: { title: '告警中心', subtitle: '集中查看站内告警通知、确认处理与回看最近告警。', breadcrumb: [{ label: '数据看板' }, { label: '告警中心' }] },
      },
      {
        path: 'cleaning',
        component: () => import('../views/admin/AdminCleaningView.vue'),
        meta: { title: '数据清洗', subtitle: '管理清洗规则。', breadcrumb: [{ label: '知识库管理' }, { label: '数据清洗' }] },
      },
      {
        path: 'audit-logs',
        component: () => import('../views/admin/AdminAuditLogsView.vue'),
        meta: { title: '操作日志', subtitle: '', breadcrumb: [{ label: '治理审阅' }, { label: '操作日志' }] },
      },
      {
        path: ':pathMatch(.*)*',
        component: () => import('../views/admin/AdminNotFoundView.vue'),
        meta: { title: '页面未找到', breadcrumb: [{ label: '404' }] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login',
  },
];
