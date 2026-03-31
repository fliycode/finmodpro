import { reactive, readonly } from 'vue';

export const createFlashStore = () => reactive({ items: [] });

export const appFlashStore = createFlashStore();

export const pushFlash = (store, entry) => {
  store.items.push({
    id: `${Date.now()}-${store.items.length + 1}`,
    ...entry,
  });
};

export const useFlash = () => ({
  items: readonly(appFlashStore.items),
  success(message) {
    pushFlash(appFlashStore, { type: 'success', message });
  },
  error(message) {
    pushFlash(appFlashStore, { type: 'error', message });
  },
  dismiss(id) {
    const index = appFlashStore.items.findIndex((item) => item.id === id);
    if (index >= 0) {
      appFlashStore.items.splice(index, 1);
    }
  },
});
