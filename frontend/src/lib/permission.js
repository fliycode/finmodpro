import { authStorage } from './auth-storage.js';

export const permissionHelper = {
  hasPermission(permission) {
    const { permissions } = authStorage.getProfile();
    return permissions.includes(permission);
  },
  
  hasAnyPermission(requiredPermissions = []) {
    const { permissions } = authStorage.getProfile();
    return requiredPermissions.some(p => permissions.includes(p));
  },

  hasGroup(group) {
    const { groups } = authStorage.getProfile();
    return groups.includes(group);
  },

  hasAnyGroup(requiredGroups = []) {
    const { groups } = authStorage.getProfile();
    return requiredGroups.some(g => groups.includes(g));
  },

  isAdmin() {
    return this.hasAnyGroup(['admin', 'super_admin']);
  }
};
