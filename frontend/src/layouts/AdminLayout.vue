<script setup>
import { ref } from 'vue';
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';

const sidebarRef = ref(null);
</script>

<template>
  <div class="app-shell app-shell--admin">
    <AppSidebar ref="sidebarRef" area="admin" />
    <main class="admin-frame">
      <AppTopbar area="admin" @toggle-sidebar="sidebarRef?.toggleMobile()" />
      <FlashStack />
      <section class="admin-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
