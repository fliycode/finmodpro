<script setup>
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
</script>

<template>
  <div class="app-shell app-shell--admin">
    <AppSidebar area="admin" />
    <main class="admin-frame">
      <AppTopbar
        eyebrow="War room"
        title="Model operations"
        subtitle="Routing, observability, governance, and review surfaces."
        area="admin"
        switch-target="/workspace/qa"
        switch-label="进入工作区"
      />
      <FlashStack />
      <section class="admin-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
