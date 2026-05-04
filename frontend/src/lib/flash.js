import { reactive, readonly } from 'vue';

export const createFlashStore = () => reactive({ items: [] });

export const appFlashStore = createFlashStore();
export const FLASH_DURATION_MS = 2600;

const dismissFlash = (store, id) => {
  const index = store.items.findIndex((item) => item.id === id);
  if (index >= 0) {
    store.items.splice(index, 1);
  }
};

export const pushFlash = (store, entry) => {
  const payload = {
    id: `${Date.now()}-${store.items.length + 1}`,
    ...entry,
  };

  store.items.push(payload);

  const duration = typeof payload.duration === 'number' ? payload.duration : FLASH_DURATION_MS;

  if (duration > 0 && typeof globalThis.setTimeout === 'function') {
    globalThis.setTimeout(() => dismissFlash(store, payload.id), duration);
  }
};

export const useFlash = () => ({
  items: readonly(appFlashStore.items),
  success(message) {
    pushFlash(appFlashStore, { type: 'success', message });
  },
  error(message) {
    pushFlash(appFlashStore, { type: 'error', message });
  },
  warning(message) {
    pushFlash(appFlashStore, { type: 'warning', message });
  },
  info(message) {
    pushFlash(appFlashStore, { type: 'info', message });
  },
  dismiss(id) {
    dismissFlash(appFlashStore, id);
  },
});
