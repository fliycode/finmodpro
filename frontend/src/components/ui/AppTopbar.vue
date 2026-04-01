<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import { getTopbarActions } from '../../config/navigation.js';
import { AUTH_EXPIRED_MESSAGE, authStorage } from '../../lib/auth-storage.js';
import { useFlash } from '../../lib/flash.js';

const props = defineProps({
  title: {
    type: String,
    default: 'FinModPro',
  },
  area: {
    type: String,
    default: 'workspace',
  },
  switchTarget: {
    type: String,
    default: '',
  },
  switchLabel: {
    type: String,
    default: '',
  },
});

const router = useRouter();
const flash = useFlash();
const profile = computed(() => authStorage.getProfile());
const actions = computed(() => {
  const base = getTopbarActions(props.area, profile.value);
  if (props.switchTarget && props.switchLabel && !base.some((item) => item.to === props.switchTarget)) {
    return [{ id: 'legacy-switch', label: props.switchLabel, to: props.switchTarget }, ...base];
  }
  return base;
});
const authExpiredMessage = ref('');

const handleLogout = async () => {
  authStorage.clear();
  await router.replace('/login');
};

const handleAuthExpired = async (event) => {
  authExpiredMessage.value = event?.detail?.message || AUTH_EXPIRED_MESSAGE;
  flash.error(authExpiredMessage.value);
};

onMounted(() => {
  window.addEventListener('finmodpro:auth-expired', handleAuthExpired);
});

onBeforeUnmount(() => {
  window.removeEventListener('finmodpro:auth-expired', handleAuthExpired);
});
</script>

<template>
  <header class="app-topbar">
    <div>
      <p class="app-topbar__eyebrow">FinModPro</p>
      <h2>{{ props.title }}</h2>
    </div>

    <div class="app-topbar__actions">
      <span class="app-topbar__user">{{ profile.user.username || '当前用户' }}</span>
      <template v-for="action in actions" :key="action.id">
        <button v-if="action.id === 'logout'" type="button" class="app-topbar__button" @click="handleLogout">
          {{ action.label }}
        </button>
        <RouterLink v-else :to="action.to">{{ action.label }}</RouterLink>
      </template>
    </div>
  </header>
</template>
