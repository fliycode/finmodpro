<script setup>
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
</script>

<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <div class="app-shell__main">
      <FlashStack />
      <div class="app-shell__content app-shell__content--workspace">
        <RouterView />
      </div>
    </div>
  </div>
</template>
