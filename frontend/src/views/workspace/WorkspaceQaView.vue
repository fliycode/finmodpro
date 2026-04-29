<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import FinancialQA from '../../components/FinancialQA.vue';

const route = useRoute();
const sessionId = computed(() => route.query.session ?? null);
</script>

<template>
  <div class="qa-page">
    <section class="qa-page__hero">
      <div class="qa-page__header">
        <p class="qa-page__eyebrow">核心工作</p>
        <h1 class="qa-page__title">智能问答</h1>
        <p class="qa-page__subtitle">基于知识库的金融建模与风险分析对话</p>
      </div>
      <span class="qa-page__hint">
        {{ sessionId ? '继续会话中' : '新对话将自动创建会话' }}
      </span>
    </section>
    <FinancialQA :session-id="sessionId" />
  </div>
</template>

<style scoped>
.qa-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.qa-page__hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 0 14px;
  border-bottom: 1px solid var(--line-soft);
  flex-shrink: 0;
}

.qa-page__header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.qa-page__eyebrow {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--brand);
}

.qa-page__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-2xl);
  font-weight: 600;
  line-height: var(--lh-tight);
  letter-spacing: -0.015em;
  color: var(--text-primary);
}

.qa-page__subtitle {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.qa-page__hint {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}
</style>
