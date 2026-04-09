export const isAdminProfile = (profile = {}) => {
  const groups = profile.groups ?? [];
  const permissions = profile.permissions ?? [];

  return groups.includes('admin') || groups.includes('super_admin') || permissions.includes('admin');
};

export const resolveHomeRoute = (profile) => (
  isAdminProfile(profile) ? '/admin/overview' : '/workspace/qa'
);

export const resolveEntryRoute = (token, profile) => (
  token ? resolveHomeRoute(profile) : '/login'
);

export const canAccessRoute = (route, profile) => {
  if (!route.meta?.requiresAdmin) {
    return true;
  }

  return isAdminProfile(profile);
};
