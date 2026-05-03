<script setup>
import { computed } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

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

const router = useRouter();
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
      label: 'FinGPT-RAG',
      sublabel: '金融风险洞察引擎',
      eyebrow: 'Risk console',
    };
  }

  return {
    label: 'Dossier workspace',
    sublabel: '结论优先的金融分析台',
    eyebrow: 'Case-led flow',
  };
});

const groupCatalog = computed(() => {
  if (props.area === 'admin') {
    return [
      { id: 'admin-overview', label: '风险看板' },
      { id: 'admin-governance', label: '治理审阅' },
      { id: 'admin-llm', label: 'Gateway ops' },
    ];
  }

  return [
    { id: 'workspace-core', label: '核心档案' },
    { id: 'workspace-support', label: '辅助记录' },
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
</script>

<template>
  <aside
    :class="[
      'app-sidebar',
      `app-sidebar--${props.area}`,
      `app-sidebar--${sidebarPresentation.mode}`,
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
          <RouterLink
            v-for="item in group.items"
            :key="item.id"
            :to="item.to"
            class="app-sidebar__item"
            :title="sidebarPresentation.showItemLabels ? undefined : item.label"
            :aria-label="sidebarPresentation.showItemLabels ? undefined : item.label"
          >
            <span class="app-sidebar__item-icon">
              <AppIcon :name="item.icon" />
            </span>
            <span v-if="sidebarPresentation.showItemLabels" class="app-sidebar__item-label">
              {{ item.label }}
            </span>
          </RouterLink>
        </div>
      </section>
    </nav>

    <div v-if="props.area === 'workspace'" class="app-sidebar__profile">
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
