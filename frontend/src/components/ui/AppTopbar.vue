<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import AppAvatar from './AppAvatar.vue';
import AppIcon from './AppIcon.vue';
import { getNavItems, getTopbarActions } from '../../config/navigation.js';
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
});

const emit = defineEmits(['toggle-sidebar']);

const router = useRouter();
const flash = useFlash();
const profile = computed(() => authStorage.getProfile());
const profileName = computed(() => profile.value?.user?.username || '当前用户');
const profileEmail = computed(() => profile.value?.user?.email || '');
const profileInitial = computed(() => profileName.value.trim().slice(0, 1).toUpperCase() || 'U');
const profileAvatarUrl = computed(() => profile.value?.user?.avatar_url || '');
const roleLabel = computed(() => (props.area === 'admin' ? '管理员端' : '用户端'));

const dropdownOpen = ref(false);
const paletteOpen = ref(false);
const paletteQuery = ref('');
const paletteIndex = ref(0);

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

// ── Command palette ──
const paletteItems = computed(() => {
  const items = getNavItems(props.area, profile.value);
  const flattened = [];
  const walk = (list, groupLabel) => {
    for (const item of list) {
      if (item.children) {
        walk(item.children, item.label);
      } else if (item.to) {
        flattened.push({ ...item, group: groupLabel });
      }
    }
  };
  walk(items, '');
  return flattened;
});

const filteredPaletteItems = computed(() => {
  const q = paletteQuery.value.toLowerCase().trim();
  if (!q) return paletteItems.value.slice(0, 8);
  return paletteItems.value
    .filter((item) => item.label.toLowerCase().includes(q) || (item.group || '').toLowerCase().includes(q))
    .slice(0, 8);
});

const openPalette = () => {
  paletteOpen.value = true;
  paletteQuery.value = '';
  paletteIndex.value = 0;
};

const closePalette = () => {
  paletteOpen.value = false;
};

const navigatePalette = (item) => {
  closePalette();
  if (item.to) {
    router.push(item.to);
  }
};

const onPaletteKeydown = (e) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    paletteIndex.value = Math.min(paletteIndex.value + 1, filteredPaletteItems.value.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    paletteIndex.value = Math.max(paletteIndex.value - 1, 0);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const item = filteredPaletteItems.value[paletteIndex.value];
    if (item) navigatePalette(item);
  } else if (e.key === 'Escape') {
    closePalette();
  }
};

const onKeydown = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openPalette();
  }
};

watch(paletteQuery, () => {
  paletteIndex.value = 0;
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
  document.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('finmodpro:auth-expired', handleAuthExpired);
  document.removeEventListener('click', handleClickOutside);
  document.removeEventListener('keydown', onKeydown);
});
</script>

<template>
  <header :class="['app-topbar', `app-topbar--${props.area}`]">
    <button
      type="button"
      class="app-topbar__menu-btn"
      aria-label="Toggle navigation"
      @click="emit('toggle-sidebar')"
    >
      <AppIcon name="menu" />
    </button>

    <div v-if="props.title" class="app-topbar__title-group">
      <h1 class="app-topbar__page-title">{{ props.title }}</h1>
    </div>
    <div v-else class="app-topbar__title-spacer" aria-hidden="true"></div>

    <div class="app-topbar__actions">
      <div class="app-topbar__search" @click="openPalette">
        <AppIcon name="search" class="app-topbar__search-icon" />
        <input
          type="text"
          class="app-topbar__search-input"
          placeholder="搜索页面... (Ctrl+K)"
          readonly
          @focus="openPalette"
        />
      </div>

      <div class="app-topbar__utility-group">
        <ThemeToggle />

        <div class="app-topbar__avatar-group">
          <button
            type="button"
            class="app-topbar__avatar-trigger"
            :aria-label="`账号菜单：${profileName}`"
            @click.stop="toggleDropdown"
          >
            <AppAvatar :src="profileAvatarUrl" :name="profileName" size="sm" />
          </button>

          <Transition name="dropdown">
            <div v-if="dropdownOpen" class="app-topbar__dropdown" role="menu">
              <div class="app-topbar__dropdown-summary">
                <AppAvatar :src="profileAvatarUrl" :name="profileName" size="md" />
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
    </div>
  </header>

  <!-- Command Palette -->
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="paletteOpen" class="cmd-palette-overlay" @click.self="closePalette">
        <div class="cmd-palette" @keydown="onPaletteKeydown">
          <div class="cmd-palette__input-row">
            <AppIcon name="search" />
            <input
              ref="paletteInputRef"
              v-model="paletteQuery"
              type="text"
              class="cmd-palette__input"
              placeholder="搜索导航..."
              autofocus
            />
            <kbd>ESC</kbd>
          </div>
          <div class="cmd-palette__results">
            <div
              v-for="(item, index) in filteredPaletteItems"
              :key="item.to"
              class="cmd-palette__item"
              :class="{ 'is-active': index === paletteIndex }"
              @click="navigatePalette(item)"
              @mouseenter="paletteIndex = index"
            >
              <AppIcon :name="item.icon || 'circle'" />
              <span>{{ item.label }}</span>
              <small v-if="item.group">{{ item.group }}</small>
            </div>
            <div v-if="filteredPaletteItems.length === 0" class="cmd-palette__empty">
              无匹配结果
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
