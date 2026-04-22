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
    currentProfile = {
      user: {
        id: profile?.id ?? profile?.user?.id,
        username: profile?.username ?? profile?.user?.username,
        email: profile?.email ?? profile?.user?.email,
      },
      groups: profile?.groups || [],
      permissions: profile?.permissions || [],
    };

    if (currentProfile.user.id === undefined) {
      currentProfile = EMPTY_PROFILE;
    }
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
