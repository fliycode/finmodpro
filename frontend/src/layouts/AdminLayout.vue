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
        eyebrow="Risk console"
        title="FinGPT-RAG 管理台"
        subtitle="风险态势、知识治理、模型网关与审计运行面。"
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
