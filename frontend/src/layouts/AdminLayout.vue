<script setup>
import { computed, ref } from 'vue';
import { RouterView, useRoute } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';

const route = useRoute();
const sidebarRef = ref(null);
const pageTitle = computed(() => route.meta?.title || '');
</script>

<template>
  <div class="app-shell app-shell--admin">
    <AppSidebar ref="sidebarRef" area="admin" />
    <main class="admin-frame">
      <AppTopbar area="admin" :title="pageTitle" @toggle-sidebar="sidebarRef?.toggleMobile()" />
      <FlashStack />
      <section class="admin-frame__body">
        <RouterView v-slot="{ Component }">
          <Transition name="route" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </section>
    </main>
  </div>
</template>
