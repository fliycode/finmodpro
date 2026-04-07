import { createRouter, createWebHistory } from 'vue-router';

import { authStorage } from '../lib/auth-storage.js';
import { canAccessRoute, resolveHomeRoute } from '../lib/session-state.js';
import { appRoutes } from './routes.js';

const router = createRouter({
  history: createWebHistory(),
  routes: appRoutes,
});

router.beforeEach((to) => {
  const token = authStorage.getToken();
  const profile = authStorage.getProfile();

  if (to.path === '/') {
    return resolveHomeRoute(profile);
  }

  if (to.meta?.public && token) {
    return resolveHomeRoute(profile);
  }

  if (to.meta?.requiresAuth && !token) {
    return '/login';
  }

  if (!canAccessRoute(to, profile)) {
    return resolveHomeRoute(profile);
  }

  return true;
});

export default router;
