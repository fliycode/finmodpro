<script setup>
import RiskSummary from '../../components/RiskSummary.vue';
</script>

<template>
  <section class="workspace-dossier-page">
    <header class="workspace-dossier-page__header">
      <div>
        <p class="workspace-dossier-page__eyebrow">Risk dossier</p>
        <h1>风险摘要与报告</h1>
      </div>
    </header>
    <RiskSummary />
  </section>
</template>

<style scoped>
.workspace-dossier-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workspace-dossier-page__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7f95bf;
}

.workspace-dossier-page h1 {
  margin: 0;
  color: #eef4ff;
  font-size: 34px;
  line-height: 1.06;
  letter-spacing: -0.03em;
}
</style>
