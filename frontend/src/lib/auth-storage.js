const FLASH_KEY = 'finmodpro_flash_message';

export const AUTH_EXPIRED_MESSAGE = '登录已过期，请重新登录';

const EMPTY_PROFILE = {
  user: {},
  groups: [],
  permissions: [],
};

let currentToken = null;
let currentProfile = EMPTY_PROFILE;

const getStorage = (storageName) => {
  try {
    return globalThis[storageName] ?? null;
  } catch {
    return null;
  }
};

const readFirstValue = (key) => {
  const sessionStorageRef = getStorage('sessionStorage');
  const localStorageRef = getStorage('localStorage');

  for (const storage of [sessionStorageRef, localStorageRef].filter(Boolean)) {
    const value = storage.getItem(key);
    if (value !== null) {
      return value;
    }
  }

  return null;
};

export const authStorage = {
  saveToken(token) {
    currentToken = token;
  },
  getToken() {
    return currentToken;
  },
  saveProfile(profile) {
    const user = profile?.user || profile;
    const id = user?.id ?? profile?.id;
    if (id === undefined || id === null) {
      return;
    }
    currentProfile = {
      user: {
        id,
        username: user?.username ?? profile?.username ?? '',
        email: user?.email ?? profile?.email ?? '',
        avatar_url: user?.avatar_url ?? profile?.avatar_url ?? null,
      },
      groups: profile?.groups || [],
      permissions: profile?.permissions || [],
    };
  },
  getProfile() {
    return currentProfile;
  },
  saveFlashMessage(message) {
    const flashStorage = getStorage('localStorage') || getStorage('sessionStorage');
    flashStorage?.setItem(FLASH_KEY, message);
  },
  consumeFlashMessage() {
    const message = readFirstValue(FLASH_KEY);
    if (message) {
      const sessionStorageRef = getStorage('sessionStorage');
      const localStorageRef = getStorage('localStorage');
      [sessionStorageRef, localStorageRef].filter(Boolean).forEach((storage) => {
        storage.removeItem(FLASH_KEY);
      });
    }
    return message;
  },
  clear() {
    currentToken = null;
    currentProfile = EMPTY_PROFILE;
  },
};
