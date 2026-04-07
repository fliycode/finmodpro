<script setup>
import { useRouter } from 'vue-router';

import ChatHistory from '../../components/ChatHistory.vue';

const router = useRouter();

const openSession = (sessionId) => {
  router.push({ path: '/workspace/qa', query: { session: sessionId } });
};
</script>

<template>
  <div class="page-stack workspace-page">
    <section class="page-hero workspace-page__hero">
      <div>
        <div class="page-hero__eyebrow">工作记录</div>
        <h1 class="page-hero__title">历史会话</h1>
        <p class="page-hero__subtitle">
          用于回看最近分析线索、恢复上下文并继续已有对话，而不是单纯堆叠一页日志列表。
        </p>
      </div>
    </section>

    <ChatHistory @open-session="openSession" />
  </div>
</template>

<style scoped>
.workspace-page__hero {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}
</style>
