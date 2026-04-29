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
      <AppTopbar
        eyebrow="Research desk"
        title="金融分析控制台"
        subtitle="统一处理智能问答、知识检索、风险研判与会话线索。"
        area="workspace"
      />
      <FlashStack />
      <section class="workspace-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
