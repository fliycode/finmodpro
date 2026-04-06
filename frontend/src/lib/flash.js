import { reactive, readonly } from 'vue';
import { ElMessage } from 'element-plus';

export const createFlashStore = () => reactive({ items: [] });

export const appFlashStore = createFlashStore();

export const pushFlash = (store, entry) => {
  const payload = {
    id: `${Date.now()}-${store.items.length + 1}`,
    ...entry,
  };

  store.items.push(payload);

  if (payload.message) {
    ElMessage({
      type: payload.type || 'info',
      message: payload.message,
      duration: 2600,
      showClose: true,
    });
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
    const index = appFlashStore.items.findIndex((item) => item.id === id);
    if (index >= 0) {
      appFlashStore.items.splice(index, 1);
    }
  },
});
