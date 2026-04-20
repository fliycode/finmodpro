<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import AppIcon from './AppIcon.vue';
import finmodproMark from '../../assets/finmodpro-mark.svg';
import { getNavItems } from '../../config/navigation.js';
import { authStorage } from '../../lib/auth-storage.js';

const props = defineProps({
  area: {
    type: String,
    required: true,
  },
});

const profile = computed(() => authStorage.getProfile());
const items = computed(() => getNavItems(props.area, profile.value));
const isWorkspaceCompact = computed(() => props.area === 'workspace');

const areaMeta = computed(() => {
  if (props.area === 'admin') {
    return {
      label: '管理控制台',
      sublabel: '治理与运维总览',
    };
  }

  return {
    label: '业务工作区',
    sublabel: '分析、检索与持续工作',
  };
});

const navGroups = computed(() => {
  if (props.area === 'admin') {
    return [
      {
        id: 'admin-overview',
        label: '总览',
        items: items.value.filter((item) => item.group === 'admin-overview'),
      },
      {
        id: 'admin-governance',
        label: '治理',
        items: items.value.filter((item) => item.group === 'admin-governance'),
      },
      {
        id: 'admin-llm',
        label: 'LLM 中台',
        items: items.value.filter((item) => item.group === 'admin-llm'),
      },
    ].filter((group) => group.items.length > 0);
  }

  return [
    {
      id: 'workspace-core',
      label: '核心工作',
      items: items.value.filter((item) => ['qa', 'knowledge', 'risk', 'sentiment'].includes(item.id)),
    },
    {
      id: 'workspace-context',
      label: '工作记录',
      items: items.value.filter((item) => item.id === 'history'),
    },
  ].filter((group) => group.items.length > 0);
});
</script>

<template>
  <aside class="app-sidebar">
    <div class="app-sidebar__brand" :title="isWorkspaceCompact ? areaMeta.label : undefined">
      <div class="app-sidebar__brand-mark">
        <img class="app-sidebar__brand-logo" :src="finmodproMark" alt="FinModPro" />
      </div>
      <div class="app-sidebar__brand-copy">
        <span class="app-sidebar__brand-eyebrow">FinModPro</span>
        <strong>{{ areaMeta.label }}</strong>
        <p>{{ areaMeta.sublabel }}</p>
      </div>
    </div>

    <nav class="app-sidebar__nav" aria-label="Primary">
      <section v-for="group in navGroups" :key="group.id" class="app-sidebar__group">
        <p class="app-sidebar__group-label">{{ group.label }}</p>
        <div class="app-sidebar__group-items">
          <RouterLink
            v-for="item in group.items"
            :key="item.id"
            :to="item.to"
            class="app-sidebar__item"
            :title="isWorkspaceCompact ? item.label : undefined"
            :aria-label="isWorkspaceCompact ? item.label : undefined"
          >
            <span class="app-sidebar__item-icon">
              <AppIcon :name="item.icon" />
            </span>
            <span class="app-sidebar__item-label">{{ item.label }}</span>
          </RouterLink>
        </div>
      </section>
    </nav>
  </aside>
</template>
