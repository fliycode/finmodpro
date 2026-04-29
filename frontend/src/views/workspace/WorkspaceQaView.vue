<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import FinancialQA from '../../components/FinancialQA.vue';

const route = useRoute();
const sessionId = computed(() => route.query.session ?? null);
</script>

<template>
  <section class="workspace-dossier-page workspace-dossier-page--qa">
    <header class="workspace-dossier-page__header">
      <div>
        <p class="workspace-dossier-page__eyebrow">Primary canvas</p>
        <h1>智能问答</h1>
      </div>
      <span class="workspace-dossier-page__hint">
        {{ sessionId ? '继续会话中' : '新对话将自动创建会话' }}
      </span>
    </header>
    <FinancialQA :session-id="sessionId" />
  </section>
</template>

<style scoped>
.workspace-dossier-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.workspace-dossier-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 0 2px;
}

.workspace-dossier-page__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.workspace-dossier-page h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: #2f2418;
}

.workspace-dossier-page__hint {
  padding-top: 6px;
  font-size: 12px;
  color: #8b7358;
  flex-shrink: 0;
}

@media (max-width: 720px) {
  .workspace-dossier-page__header {
    flex-direction: column;
  }
}
</style>
