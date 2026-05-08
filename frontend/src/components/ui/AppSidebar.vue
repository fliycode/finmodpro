<script setup>
import { computed, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import AppIcon from './AppIcon.vue';
import finmodproMark from '../../assets/finmodpro-mark.svg';
import { getNavItems, getTopbarActions } from '../../config/navigation.js';
import { authSession } from '../../lib/auth-session.js';
import { authStorage } from '../../lib/auth-storage.js';
import { getSidebarPresentation } from '../../lib/workspace-shell.js';

const props = defineProps({
  area: {
    type: String,
    required: true,
  },
});

const route = useRoute();
const router = useRouter();

const mobileOpen = ref(false);
const toggleMobile = () => { mobileOpen.value = !mobileOpen.value; };
const closeMobile = () => { mobileOpen.value = false; };

defineExpose({ toggleMobile });
const profile = computed(() => authStorage.getProfile());
const items = computed(() => getNavItems(props.area, profile.value));
const sidebarPresentation = computed(() => getSidebarPresentation(props.area));
const profileName = computed(() => profile.value?.user?.username || '当前用户');
const profileEmail = computed(() => profile.value?.user?.email || '未设置邮箱');
const roleLabel = computed(() => (props.area === 'admin' ? '管理员端' : '用户端'));
const profileInitial = computed(() => profileName.value.trim().slice(0, 1).toUpperCase() || 'U');
const profileActions = computed(() => [
  { id: 'profile', label: '个人信息', to: '/workspace/profile' },
  ...getTopbarActions(props.area, profile.value),
]);

const areaMeta = computed(() => {
  if (props.area === 'admin') {
    return {
      label: 'FinModPro',
      sublabel: '',
      eyebrow: '',
    };
  }

  return {
    label: 'FinModPro',
    sublabel: '',
    eyebrow: '',
  };
});

const groupCatalog = computed(() => {
  if (props.area === 'admin') {
    return [
      { id: 'admin-overview', label: '' },
      { id: 'admin-governance', label: '' },
      { id: 'admin-llm', label: '' },
    ];
  }

  return [
    { id: 'workspace-core', label: '' },
    { id: 'workspace-support', label: '' },
  ];
});

const navGroups = computed(() => {
  return groupCatalog.value
    .map((group) => ({
      ...group,
      items: items.value.filter((item) => item.group === group.id),
    }))
    .filter((group) => group.items.length > 0);
});

const handleLogout = async () => {
  await authSession.logout();
  await router.replace('/login');
};

const isItemActive = (item) => {
  if (!item?.to) {
    return false;
  }

  if (item.children?.length) {
    return route.path === item.to || route.path.startsWith(`${item.to}/`) || item.children.some((child) => isItemActive(child));
  }

  return route.path === item.to;
};
</script>

<template>
  <aside
    :class="[
      'app-sidebar',
      `app-sidebar--${props.area}`,
      `app-sidebar--${sidebarPresentation.mode}`,
      { 'app-sidebar--open': mobileOpen },
    ]"
  >
    <div
      class="app-sidebar__brand"
      :title="sidebarPresentation.showBrandCopy ? undefined : areaMeta.label"
    >
      <div class="app-sidebar__brand-mark">
        <img class="app-sidebar__brand-logo" :src="finmodproMark" alt="FinModPro" />
      </div>
      <div v-if="sidebarPresentation.showBrandCopy" class="app-sidebar__brand-copy">
        <span class="app-sidebar__brand-eyebrow">{{ areaMeta.eyebrow }}</span>
        <strong>{{ areaMeta.label }}</strong>
        <p>{{ areaMeta.sublabel }}</p>
      </div>
    </div>

    <nav class="app-sidebar__nav" aria-label="Primary">
      <section v-for="group in navGroups" :key="group.id" class="app-sidebar__group">
        <p v-if="sidebarPresentation.showGroupLabels" class="app-sidebar__group-label">
          {{ group.label }}
        </p>
        <div class="app-sidebar__group-items">
          <div v-for="item in group.items" :key="item.id" class="app-sidebar__entry">
            <RouterLink
              :to="item.to"
              :class="['app-sidebar__item', { 'app-sidebar__item--active': isItemActive(item), 'app-sidebar__item--with-children': item.children?.length }]"
              :title="sidebarPresentation.showItemLabels ? undefined : item.label"
              :aria-label="sidebarPresentation.showItemLabels ? undefined : item.label"
            >
              <span class="app-sidebar__item-icon">
                <AppIcon :name="item.icon" />
              </span>
              <span v-if="sidebarPresentation.showItemLabels" class="app-sidebar__item-label">
                {{ item.label }}
              </span>
              <span v-if="sidebarPresentation.showItemLabels && item.children?.length" class="app-sidebar__item-chevron">
                <AppIcon name="chevron-right" />
              </span>
            </RouterLink>

            <div
              v-if="sidebarPresentation.showItemLabels && item.children?.length && isItemActive(item)"
              class="app-sidebar__subnav"
            >
              <RouterLink
                v-for="child in item.children"
                :key="child.id"
                :to="child.to"
                :class="['app-sidebar__subitem', { 'app-sidebar__subitem--active': isItemActive(child) }]"
              >
                {{ child.label }}
              </RouterLink>
            </div>
          </div>
        </div>
      </section>
    </nav>

    <div v-if="props.area === 'workspace' || props.area === 'admin'" class="app-sidebar__profile">
      <button class="app-sidebar__profile-trigger" type="button" :aria-label="`账号菜单：${profileName}`">
        <span class="app-sidebar__avatar">{{ profileInitial }}</span>
        <span class="app-sidebar__profile-copy">
          <strong>{{ profileName }}</strong>
          <span>{{ profileEmail }}</span>
        </span>
      </button>

      <div class="app-sidebar__profile-menu" role="menu">
        <div class="app-sidebar__profile-summary">
          <span class="app-sidebar__avatar app-sidebar__avatar--menu">{{ profileInitial }}</span>
          <div>
            <strong>{{ profileName }}</strong>
            <span>{{ profileEmail }}</span>
            <em>{{ roleLabel }}</em>
          </div>
        </div>
        <template v-for="action in profileActions" :key="action.id">
          <button
            v-if="action.id === 'logout'"
            type="button"
            class="app-sidebar__profile-action"
            role="menuitem"
            @click="handleLogout"
          >
            {{ action.label }}
          </button>
          <RouterLink
            v-else
            :to="action.to"
            class="app-sidebar__profile-action"
            role="menuitem"
          >
            {{ action.label }}
          </RouterLink>
        </template>
      </div>
    </div>

  </aside>
</template>
