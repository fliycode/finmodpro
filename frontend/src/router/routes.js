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
        path: 'lightrag',
        redirect: '/admin/lightrag/query',
      },
      {
        path: 'lightrag/query',
        component: () => import('../views/admin/AdminLightragQueryView.vue'),
        meta: { title: '图谱工作台 / 查询工作台', subtitle: '先发起问题，再用图谱证据回看结论。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '图谱工作台' }, { label: '查询工作台' }] },
      },
      {
        path: 'lightrag/graph',
        component: () => import('../views/admin/AdminLightragGraphView.vue'),
        meta: { title: '图谱工作台 / 图谱浏览', subtitle: '在同一张画布上看结构、筛选和检查细节。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '图谱工作台' }, { label: '图谱浏览' }] },
      },
      {
        path: 'lightrag/documents',
        component: () => import('../views/admin/AdminLightragDocumentsView.vue'),
        meta: { title: '图谱工作台 / 文档管线', subtitle: '把上传、入库和失败队列收敛到一处处理。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '图谱工作台' }, { label: '文档管线' }] },
      },
      {
        path: 'lightrag/legacy',
        component: () => import('../views/admin/AdminLightragView.vue'),
        meta: { title: '图谱工作台 / Legacy WebUI', subtitle: '保留旧版 LightRAG WebUI 作为应急回退入口。', breadcrumb: [{ label: 'Gateway Ops' }, { label: '图谱工作台' }, { label: 'Legacy WebUI' }] },
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
