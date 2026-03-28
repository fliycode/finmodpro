const TOKEN_KEY = 'finmodpro_token';
const USER_KEY = 'finmodpro_user';
const GROUPS_KEY = 'finmodpro_groups';
const PERMISSIONS_KEY = 'finmodpro_permissions';

export const authStorage = {
  saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  saveProfile(profile) {
    localStorage.setItem(USER_KEY, JSON.stringify({
      id: profile.id,
      username: profile.username,
      email: profile.email
    }));
    localStorage.setItem(GROUPS_KEY, JSON.stringify(profile.groups || []));
    localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(profile.permissions || []));
  },
  getProfile() {
    try {
      return {
        user: JSON.parse(localStorage.getItem(USER_KEY) || '{}'),
        groups: JSON.parse(localStorage.getItem(GROUPS_KEY) || '[]'),
        permissions: JSON.parse(localStorage.getItem(PERMISSIONS_KEY) || '[]')
      };
    } catch (e) {
      return { user: {}, groups: [], permissions: [] };
    }
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(GROUPS_KEY);
    localStorage.removeItem(PERMISSIONS_KEY);
  }
};
