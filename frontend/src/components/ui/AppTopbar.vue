<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import AppIcon from './AppIcon.vue';
import { getTopbarActions } from '../../config/navigation.js';
import { authSession } from '../../lib/auth-session.js';
import { AUTH_EXPIRED_MESSAGE, authStorage } from '../../lib/auth-storage.js';
import { useFlash } from '../../lib/flash.js';
import ThemeToggle from './ThemeToggle.vue';

const props = defineProps({
  area: {
    type: String,
    default: 'workspace',
  },
  title: {
    type: String,
    default: '',
  },
  subtitle: {
    type: String,
    default: '',
  },
});

const router = useRouter();
const flash = useFlash();
const profile = computed(() => authStorage.getProfile());
const profileName = computed(() => profile.value?.user?.username || '当前用户');
const profileEmail = computed(() => profile.value?.user?.email || '');
const profileInitial = computed(() => profileName.value.trim().slice(0, 1).toUpperCase() || 'U');
const roleLabel = computed(() => (props.area === 'admin' ? '管理员端' : '用户端'));

const dropdownOpen = ref(false);
const searchQuery = ref('');

const toggleDropdown = () => {
  dropdownOpen.value = !dropdownOpen.value;
};

const closeDropdown = () => {
  dropdownOpen.value = false;
};

const handleClickOutside = (event) => {
  const dropdown = document.querySelector('.app-topbar__dropdown');
  const trigger = document.querySelector('.app-topbar__avatar-trigger');
  if (
    dropdown &&
    trigger &&
    !dropdown.contains(event.target) &&
    !trigger.contains(event.target)
  ) {
    closeDropdown();
  }
};

const actions = computed(() => {
  return getTopbarActions(props.area, profile.value);
});

const handleLogout = async () => {
  closeDropdown();
  await authSession.logout();
  await router.replace('/login');
};

const handleAuthExpired = async (event) => {
  flash.error(event?.detail?.message || AUTH_EXPIRED_MESSAGE);
};

onMounted(() => {
  window.addEventListener('finmodpro:auth-expired', handleAuthExpired);
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  window.removeEventListener('finmodpro:auth-expired', handleAuthExpired);
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <header :class="['app-topbar', `app-topbar--${props.area}`]">
    <div v-if="props.title" class="app-topbar__title-group">
      <h1 class="app-topbar__page-title">{{ props.title }}</h1>
      <p v-if="props.subtitle" class="app-topbar__page-subtitle">{{ props.subtitle }}</p>
    </div>

    <div class="app-topbar__actions">
      <div class="app-topbar__search">
        <AppIcon name="search" class="app-topbar__search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          class="app-topbar__search-input"
          placeholder="搜索金融资讯、知识条目..."
        />
      </div>

      <ThemeToggle />

      <div class="app-topbar__avatar-group">
        <button
          type="button"
          class="app-topbar__avatar-trigger"
          :aria-label="`账号菜单：${profileName}`"
          @click.stop="toggleDropdown"
        >
          <span class="app-topbar__avatar">{{ profileInitial }}</span>
        </button>

        <Transition name="dropdown">
          <div v-if="dropdownOpen" class="app-topbar__dropdown" role="menu">
            <div class="app-topbar__dropdown-summary">
              <span class="app-topbar__avatar app-topbar__avatar--lg">{{ profileInitial }}</span>
              <div>
                <strong>{{ profileName }}</strong>
                <span v-if="profileEmail">{{ profileEmail }}</span>
                <em>{{ roleLabel }}</em>
              </div>
            </div>
            <div class="app-topbar__dropdown-divider"></div>
            <RouterLink
              :to="'/workspace/profile'"
              class="app-topbar__dropdown-item"
              role="menuitem"
              @click="closeDropdown"
            >
              个人信息
            </RouterLink>
            <template v-for="action in actions" :key="action.id">
              <button
                v-if="action.id === 'logout'"
                type="button"
                class="app-topbar__dropdown-item"
                role="menuitem"
                @click="handleLogout"
              >
                {{ action.label }}
              </button>
              <RouterLink
                v-else
                :to="action.to"
                class="app-topbar__dropdown-item"
                role="menuitem"
                @click="closeDropdown"
              >
                {{ action.label }}
              </RouterLink>
            </template>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>
