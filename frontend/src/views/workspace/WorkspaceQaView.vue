<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import FinancialQA from '../../components/FinancialQA.vue';

const route = useRoute();
const sessionId = computed(() => route.query.session ?? null);
</script>

<template>
  <div class="page-stack workspace-page">
    <section class="page-hero workspace-page__hero">
      <div>
        <div class="page-hero__eyebrow">问答工作台</div>
        <h1 class="page-hero__title">智能问答</h1>
        <p class="page-hero__subtitle">
          以输入问题、延续会话和回看引用证据为主，减少无关监控信息，让分析动作保持连续。
        </p>
      </div>
    </section>

    <FinancialQA :session-id="sessionId" />
  </div>
</template>

<style scoped>
.workspace-page__hero {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}
</style>
