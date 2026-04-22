import { createRouter, createWebHistory } from 'vue-router';

import { authStorage } from '../lib/auth-storage.js';
import { authSession } from '../lib/auth-session.js';
import { canAccessRoute, resolveEntryRoute, resolveHomeRoute } from '../lib/session-state.js';
import { appRoutes } from './routes.js';

const router = createRouter({
  history: createWebHistory(),
  routes: appRoutes,
});

router.beforeEach(async (to) => {
  const authenticated = await authSession.ensureSession();
  const token = authenticated ? authStorage.getToken() : null;
  const profile = authStorage.getProfile();

  if (to.path === '/') {
    return resolveEntryRoute(token, profile);
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
