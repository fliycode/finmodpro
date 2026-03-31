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
      },
      {
        path: 'knowledge',
        component: () => import('../views/workspace/WorkspaceKnowledgeView.vue'),
      },
      {
        path: 'history',
        component: () => import('../views/workspace/WorkspaceHistoryView.vue'),
      },
      {
        path: 'risk',
        component: () => import('../views/workspace/WorkspaceRiskView.vue'),
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
      },
      {
        path: 'users',
        component: () => import('../views/admin/AdminUsersView.vue'),
      },
      {
        path: 'models',
        component: () => import('../views/admin/AdminModelsView.vue'),
      },
      {
        path: 'evaluation',
        component: () => import('../views/admin/AdminEvaluationView.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login',
  },
];
