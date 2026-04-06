<script setup>
import RiskSummary from '../../components/RiskSummary.vue';
</script>

<template>
  <div class="page-stack workspace-page">
    <section class="page-hero workspace-page__hero">
      <div>
        <div class="page-hero__eyebrow">风险工作台</div>
        <h1 class="page-hero__title">风险摘要与报告</h1>
        <p class="page-hero__subtitle">
          把事件筛选、人工复核和报告生成整合到一个更安静的工作界面里，强调结论、证据与来源。
        </p>
      </div>
    </section>

    <RiskSummary />
  </div>
</template>

<style scoped>
.workspace-page__hero {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}
</style>
