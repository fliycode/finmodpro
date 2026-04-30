<script setup>
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
</script>

<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <main class="workspace-frame">
      <AppTopbar area="workspace" />
      <FlashStack />
      <section class="workspace-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
