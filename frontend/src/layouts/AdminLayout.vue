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
        subtitle="面向平台治理、风险审查、模型配置与运维判断的统一工作台。"
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
