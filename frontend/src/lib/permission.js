import { authStorage } from './auth-storage.js';

export const hasProfilePermission = (profile = {}, permission) => {
  const permissions = profile?.permissions ?? [];
  return permissions.includes(permission);
};

export const hasAnyProfilePermission = (profile = {}, requiredPermissions = []) => {
  const permissions = profile?.permissions ?? [];
  return requiredPermissions.some((permission) => permissions.includes(permission));
};

export const hasProfileGroup = (profile = {}, group) => {
  const groups = profile?.groups ?? [];
  return groups.includes(group);
};

export const hasAnyProfileGroup = (profile = {}, requiredGroups = []) => {
  const groups = profile?.groups ?? [];
  return requiredGroups.some((group) => groups.includes(group));
};

export const permissionHelper = {
  hasPermission(permission) {
    return hasProfilePermission(authStorage.getProfile(), permission);
  },

  hasAnyPermission(requiredPermissions = []) {
    return hasAnyProfilePermission(authStorage.getProfile(), requiredPermissions);
  },

  hasGroup(group) {
    return hasProfileGroup(authStorage.getProfile(), group);
  },

  hasAnyGroup(requiredGroups = []) {
    return hasAnyProfileGroup(authStorage.getProfile(), requiredGroups);
  },

  isAdmin() {
    return this.hasAnyGroup(['admin', 'super_admin']);
  }
};
