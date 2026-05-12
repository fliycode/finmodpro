<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import { monitoringApi } from '../../api/monitoring.js';
import AppAvatar from './AppAvatar.vue';
import AppIcon from './AppIcon.vue';
import { getNavItems, getTopbarActions } from '../../config/navigation.js';
import { authSession } from '../../lib/auth-session.js';
import {
  SEVERITY_LABELS,
  formatAlertTime,
  getMetricLabel,
  normalizeAlertEvent,
  sortAlertEventsByPriority,
  summarizeAlertEvents,
  summarizeAlertSeverities,
} from '../../lib/admin-monitoring.js';
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

const route = useRoute();
const router = useRouter();
const flash = useFlash();
const profile = computed(() => authStorage.getProfile());
const profileName = computed(() => profile.value?.user?.username || '当前用户');
const profileEmail = computed(() => profile.value?.user?.email || '');
const profileInitial = computed(() => profileName.value.trim().slice(0, 1).toUpperCase() || 'U');
const profileAvatarUrl = computed(() => profile.value?.user?.avatar_url || '');
const roleLabel = computed(() => (props.area === 'admin' ? '管理员端' : '用户端'));

const dropdownOpen = ref(false);
const dropdownRef = ref(null);
const avatarTriggerRef = ref(null);
const notificationOpen = ref(false);
const notificationDropdownRef = ref(null);
const notificationTriggerRef = ref(null);
const notificationLoading = ref(false);
const notificationError = ref('');
const notificationEvents = ref([]);
const paletteOpen = ref(false);
const paletteQuery = ref('');
const paletteIndex = ref(0);
let notificationPollHandle = null;

const toggleDropdown = () => {
  notificationOpen.value = false;
  dropdownOpen.value = !dropdownOpen.value;
};

const closeDropdown = () => {
  dropdownOpen.value = false;
};

const normalizedNotificationEvents = computed(() => notificationEvents.value.map(normalizeAlertEvent));
const prioritizedNotificationEvents = computed(() => sortAlertEventsByPriority(normalizedNotificationEvents.value));
const notificationSummary = computed(() => summarizeAlertEvents(normalizedNotificationEvents.value));
const notificationSeveritySummary = computed(() => summarizeAlertSeverities(normalizedNotificationEvents.value));
const notificationBadge = computed(() => {
  const count = notificationSummary.value.firing;
  if (!count) {
    return '';
  }
  return count > 99 ? '99+' : String(count);
});

const openAlertCenter = () => {
  notificationOpen.value = false;
  router.push('/admin/notifications');
};

const closeNotifications = () => {
  notificationOpen.value = false;
};

const loadNotifications = async ({ withSpinner = false } = {}) => {
  if (props.area !== 'admin') {
    return;
  }

  if (withSpinner) {
    notificationLoading.value = true;
  }

  try {
    const payload = await monitoringApi.listAlertEvents({ status: 'firing', limit: 20 });
    notificationEvents.value = Array.isArray(payload) ? payload : [];
    notificationError.value = '';
  } catch (err) {
    notificationError.value = err.message || '加载告警失败';
  } finally {
    if (withSpinner) {
      notificationLoading.value = false;
    }
  }
};

const toggleNotifications = async () => {
  closeDropdown();
  notificationOpen.value = !notificationOpen.value;
  if (notificationOpen.value) {
    await loadNotifications({ withSpinner: true });
  }
};

const handleClickOutside = (event) => {
  if (
    dropdownOpen.value &&
    dropdownRef.value &&
    avatarTriggerRef.value &&
    !dropdownRef.value.contains(event.target) &&
    !avatarTriggerRef.value.contains(event.target)
  ) {
    closeDropdown();
  }

  if (
    notificationOpen.value &&
    notificationDropdownRef.value &&
    notificationTriggerRef.value &&
    !notificationDropdownRef.value.contains(event.target) &&
    !notificationTriggerRef.value.contains(event.target)
  ) {
    closeNotifications();
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

watch(() => route.fullPath, () => {
  closeDropdown();
  closeNotifications();
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
  if (props.area === 'admin') {
    loadNotifications({ withSpinner: true });
    notificationPollHandle = window.setInterval(() => {
      loadNotifications();
    }, 60000);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('finmodpro:auth-expired', handleAuthExpired);
  document.removeEventListener('click', handleClickOutside);
  document.removeEventListener('keydown', onKeydown);
  if (notificationPollHandle) {
    window.clearInterval(notificationPollHandle);
  }
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

        <div v-if="props.area === 'admin'" class="app-topbar__notification-group">
          <button
            ref="notificationTriggerRef"
            type="button"
            class="app-topbar__notification-trigger"
            :aria-label="notificationBadge ? `告警通知：${notificationBadge} 条未处理` : '告警通知'"
            @click.stop="toggleNotifications"
          >
            <AppIcon name="bell" />
            <span v-if="notificationBadge" class="app-topbar__notification-badge">
              {{ notificationBadge }}
            </span>
          </button>

          <Transition name="dropdown">
            <div
              v-if="notificationOpen"
              ref="notificationDropdownRef"
              class="app-topbar__dropdown app-topbar__notification-dropdown"
            >
              <div class="app-topbar__notification-header">
                <div>
                  <strong>告警通知</strong>
                  <span>
                    {{ notificationSummary.firing ? `${notificationSummary.firing} 条待处理` : '当前没有触发中的告警' }}
                  </span>
                </div>
              </div>
              <div
                v-if="notificationSeveritySummary.critical || notificationSeveritySummary.warning || notificationSeveritySummary.info"
                class="app-topbar__notification-summary"
              >
                <span v-if="notificationSeveritySummary.critical" class="app-topbar__notification-chip is-critical">
                  严重 {{ notificationSeveritySummary.critical }}
                </span>
                <span v-if="notificationSeveritySummary.warning" class="app-topbar__notification-chip is-warning">
                  警告 {{ notificationSeveritySummary.warning }}
                </span>
                <span v-if="notificationSeveritySummary.info" class="app-topbar__notification-chip is-info">
                  提示 {{ notificationSeveritySummary.info }}
                </span>
              </div>

              <div v-if="notificationError" class="app-topbar__notification-empty" role="alert">
                {{ notificationError }}
              </div>
              <div v-else-if="notificationLoading" class="app-topbar__notification-empty">
                加载中...
              </div>
              <div v-else-if="prioritizedNotificationEvents.length" class="app-topbar__notification-list">
                <button
                  v-for="event in prioritizedNotificationEvents.slice(0, 5)"
                  :key="event.id"
                  type="button"
                  :class="['app-topbar__notification-item', `is-${event.severity}`]"
                  @click="openAlertCenter"
                >
                  <div class="app-topbar__notification-item-copy">
                    <strong>{{ event.ruleName || '未命名规则' }}</strong>
                    <span>{{ SEVERITY_LABELS[event.severity] || event.severity }} · {{ getMetricLabel(event.metricName) }} · {{ formatAlertTime(event.triggeredAt) }}</span>
                  </div>
                  <span class="app-topbar__notification-item-value">
                    {{ event.triggeredValue?.toFixed(1) }}
                  </span>
                </button>
              </div>
              <div v-else class="app-topbar__notification-empty">
                当前没有触发中的告警
              </div>

              <div class="app-topbar__dropdown-divider"></div>
              <button
                type="button"
                class="app-topbar__dropdown-item app-topbar__dropdown-item--primary"
                @click="openAlertCenter"
              >
                查看告警中心
              </button>
            </div>
          </Transition>
        </div>

        <div class="app-topbar__avatar-group">
          <button
            ref="avatarTriggerRef"
            type="button"
            class="app-topbar__avatar-trigger"
            :aria-label="`账号菜单：${profileName}`"
            @click.stop="toggleDropdown"
          >
            <AppAvatar :src="profileAvatarUrl" :name="profileName" size="sm" />
          </button>

          <Transition name="dropdown">
            <div v-if="dropdownOpen" ref="dropdownRef" class="app-topbar__dropdown" role="menu">
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
