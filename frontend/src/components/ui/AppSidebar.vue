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
</script>

<template>
  <aside class="app-sidebar">
    <div class="app-sidebar__brand">
      <img class="app-sidebar__brand-logo" :src="finmodproMark" alt="FinModPro" />
      <div>
        <strong>FinModPro</strong>
        <p>{{ props.area === 'admin' ? '管理控制台' : '业务工作区' }}</p>
      </div>
    </div>

    <RouterLink v-for="item in items" :key="item.id" :to="item.to" class="app-sidebar__item">
      <AppIcon :name="item.icon" />
      <span>{{ item.label }}</span>
    </RouterLink>
  </aside>
</template>
