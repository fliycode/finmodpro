<script setup>
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';

const route = useRoute();
const pageTitle = computed(() => route.meta?.title || '');
const pageSubtitle = computed(() => route.meta?.subtitle || '');
</script>

<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <main class="workspace-frame">
      <AppTopbar area="workspace" :title="pageTitle" :subtitle="pageSubtitle" />
      <FlashStack />
      <section class="workspace-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
