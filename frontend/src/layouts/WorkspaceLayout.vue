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
      <AppTopbar
        eyebrow="用户端"
        title="业务工作区"
        subtitle="问答、检索与风险摘要的连续工作区。"
        area="workspace"
        compact
      />
      <FlashStack />
      <div class="app-shell__content">
        <RouterView />
      </div>
    </div>
  </div>
</template>
