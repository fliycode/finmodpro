<script setup>
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';

const route = useRoute();
const pageTitle = computed(() => route.meta?.title || '');
</script>

<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <main class="workspace-frame">
      <AppTopbar area="workspace" :title="pageTitle" />
      <FlashStack />
      <section class="workspace-frame__body">
        <RouterView v-slot="{ Component }">
          <Transition name="route" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </section>
    </main>
  </div>
</template>
