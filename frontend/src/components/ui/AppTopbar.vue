<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import finmodproMark from '../../assets/finmodpro-mark.svg';
import { getTopbarActions } from '../../config/navigation.js';
import { authSession } from '../../lib/auth-session.js';
import { AUTH_EXPIRED_MESSAGE, authStorage } from '../../lib/auth-storage.js';
import { useFlash } from '../../lib/flash.js';

const props = defineProps({
  title: {
    type: String,
    default: 'FinModPro',
  },
  eyebrow: {
    type: String,
    default: 'FinModPro',
  },
  subtitle: {
    type: String,
    default: '',
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
  compact: {
    type: Boolean,
    default: false,
  },
});

const router = useRouter();
const flash = useFlash();
const profile = computed(() => authStorage.getProfile());
const profileName = computed(() => profile.value?.user?.username || '当前用户');
const roleLabel = computed(() => (props.area === 'admin' ? '管理员端' : '用户端'));
const actions = computed(() => {
  const base = getTopbarActions(props.area, profile.value);
  if (props.switchTarget && props.switchLabel && !base.some((item) => item.to === props.switchTarget)) {
    return [{ id: 'legacy-switch', label: props.switchLabel, to: props.switchTarget }, ...base];
  }
  return base;
});

const handleLogout = async () => {
  await authSession.logout();
  await router.replace('/login');
};

const handleAuthExpired = async (event) => {
  flash.error(event?.detail?.message || AUTH_EXPIRED_MESSAGE);
};

onMounted(() => {
  window.addEventListener('finmodpro:auth-expired', handleAuthExpired);
});

onBeforeUnmount(() => {
  window.removeEventListener('finmodpro:auth-expired', handleAuthExpired);
});
</script>

<template>
  <header class="app-topbar" :class="{ 'app-topbar--compact': props.compact }">
    <div class="app-topbar__title-group">
      <img class="app-topbar__brand-logo" :src="finmodproMark" alt="FinModPro" />
      <div class="app-topbar__copy">
        <p class="app-topbar__eyebrow">{{ props.eyebrow }}</p>
        <h2>{{ props.title }}</h2>
        <p v-if="props.subtitle" class="app-topbar__subtitle">{{ props.subtitle }}</p>
      </div>
    </div>

    <div class="app-topbar__actions">
      <div class="app-topbar__identity">
        <span class="app-topbar__role">{{ roleLabel }}</span>
        <span class="app-topbar__user">{{ profileName }}</span>
      </div>
      <template v-for="action in actions" :key="action.id">
        <button v-if="action.id === 'logout'" type="button" class="app-topbar__button" @click="handleLogout">
          {{ action.label }}
        </button>
        <RouterLink v-else :to="action.to">{{ action.label }}</RouterLink>
      </template>
    </div>
  </header>
</template>
