<script setup>
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
</script>

<template>
  <div class="app-shell">
    <AppSidebar area="workspace" />
    <div class="app-shell__main">
      <AppTopbar title="业务工作区" />
      <FlashStack />
      <div class="app-shell__content">
        <RouterView />
      </div>
    </div>
  </div>
</template>
