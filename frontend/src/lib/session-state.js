import { hasAnyProfileGroup, hasAnyProfilePermission } from './permission.js';

export const ADMIN_PROFILE_PERMISSIONS = [
  'view_dashboard',
  'view_user',
  'view_role',
  'view_monitoring',
  'view_audit_log',
  'manage_model_config',
  'manage_cleaning_rules',
];

const ADMIN_HOME_ROUTE_CANDIDATES = [
  { to: '/admin/overview', requiredPermissions: ['view_dashboard'] },
  { to: '/admin/users', requiredPermissions: ['view_user'] },
  { to: '/admin/roles', requiredPermissions: ['view_role'] },
  { to: '/admin/monitoring', requiredPermissions: ['view_monitoring'] },
  { to: '/admin/audit-logs', requiredPermissions: ['view_audit_log'] },
  { to: '/admin/knowledge', requiredPermissions: ['view_document'] },
  { to: '/admin/llm/models', requiredPermissions: ['manage_model_config'] },
  { to: '/admin/cleaning', requiredPermissions: ['manage_cleaning_rules'] },
];

export const isAdminProfile = (profile = {}) => (
  hasAnyProfileGroup(profile, ['admin', 'super_admin'])
  || hasAnyProfilePermission(profile, ADMIN_PROFILE_PERMISSIONS)
);

export const resolveAdminHomeRoute = (profile = {}) => {
  const match = ADMIN_HOME_ROUTE_CANDIDATES.find((entry) => (
    hasAnyProfilePermission(profile, entry.requiredPermissions)
  ));

  return match?.to ?? '/workspace/qa';
};

export const resolveHomeRoute = (profile) => (
  isAdminProfile(profile) ? resolveAdminHomeRoute(profile) : '/workspace/qa'
);

export const resolveEntryRoute = (token, profile) => (
  token ? resolveHomeRoute(profile) : '/login'
);

export const canAccessRoute = (route, profile) => {
  if (route.meta?.requiresAdmin && !isAdminProfile(profile)) {
    return false;
  }

  if (route.meta?.requiredPermissions?.length) {
    return hasAnyProfilePermission(profile, route.meta.requiredPermissions);
  }

  if (route.meta?.requiredGroups?.length) {
    return hasAnyProfileGroup(profile, route.meta.requiredGroups);
  }

  return true;
};
