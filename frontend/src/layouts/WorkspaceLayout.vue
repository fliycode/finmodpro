<script setup>
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
import ThemeToggle from '../components/ui/ThemeToggle.vue';

const route = useRoute();
const isQaPage = computed(() => route.path === '/workspace/qa');
</script>

<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <div class="app-shell__main">
      <div v-if="!isQaPage" class="app-shell__utility-bar" aria-label="页面工具栏">
        <ThemeToggle />
      </div>
      <FlashStack />
      <div class="app-shell__content app-shell__content--workspace">
        <RouterView />
      </div>
    </div>
  </div>
</template>
