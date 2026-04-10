<script setup>
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import AppTopbar from '../components/ui/AppTopbar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
</script>

<template>
  <div class="app-shell">
    <AppSidebar area="admin" />
    <div class="app-shell__main">
      <AppTopbar
        eyebrow="管理员端"
        title="管理控制台"
        subtitle="平台治理、风险审查与模型运维总览。"
        area="admin"
        switch-target="/workspace/qa"
        switch-label="进入工作区"
      />
      <FlashStack />
      <div class="app-shell__content">
        <RouterView />
      </div>
    </div>
  </div>
</template>
