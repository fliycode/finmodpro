const THEME_STORAGE_KEY = 'finmodpro_theme';
const THEMES = new Set(['light', 'dark']);
const DEFAULT_THEME = 'light';

const getStorage = () => {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
};

export const getSystemTheme = () => {
  try {
    return globalThis.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light';
  } catch {
    return 'light';
  }
};

export const normalizeTheme = (theme) => (
  THEMES.has(theme) ? theme : DEFAULT_THEME
);

export const getStoredTheme = () => {
  const storedTheme = getStorage()?.getItem(THEME_STORAGE_KEY);
  return THEMES.has(storedTheme) ? storedTheme : null;
};

export const applyTheme = (theme) => {
  const normalizedTheme = normalizeTheme(theme);
  const root = globalThis.document?.documentElement;

  if (root) {
    root.dataset.theme = normalizedTheme;
    root.style.colorScheme = normalizedTheme;
    root.classList.toggle('dark', normalizedTheme === 'dark');
  }

  return normalizedTheme;
};

export const persistTheme = (theme) => {
  const normalizedTheme = normalizeTheme(theme);
  getStorage()?.setItem(THEME_STORAGE_KEY, normalizedTheme);
  return normalizedTheme;
};

export const initializeTheme = () => applyTheme(getStoredTheme() || DEFAULT_THEME);
