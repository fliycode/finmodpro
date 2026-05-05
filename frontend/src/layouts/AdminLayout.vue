<script setup>
import { computed, ref } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';

const route = useRoute();
const pageTitle = computed(() => route.meta?.title || '');
const sidebarRef = ref(null);

const breadcrumbs = computed(() => {
  const crumbs = route.meta?.breadcrumb;
  if (Array.isArray(crumbs) && crumbs.length > 0) return crumbs;
  if (pageTitle.value) return [{ label: pageTitle.value }];
  return [];
});
</script>

<template>
  <div class="app-shell app-shell--admin">
    <AppSidebar ref="sidebarRef" area="admin" />
    <main class="admin-frame">
      <AppTopbar area="admin" :title="pageTitle" @toggle-sidebar="sidebarRef?.toggleMobile()" />
      <FlashStack />
      <div v-if="breadcrumbs.length > 0" class="admin-breadcrumb">
        <span v-for="(crumb, i) in breadcrumbs" :key="i" class="admin-breadcrumb__item">
          <RouterLink v-if="crumb.to" :to="crumb.to">{{ crumb.label }}</RouterLink>
          <span v-else>{{ crumb.label }}</span>
          <span v-if="i < breadcrumbs.length - 1" class="admin-breadcrumb__sep">/</span>
        </span>
      </div>
      <section class="admin-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
