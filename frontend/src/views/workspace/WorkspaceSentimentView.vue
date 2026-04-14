<script setup>
import SentimentAnalysis from '../../components/SentimentAnalysis.vue';
</script>

<template>
  <div class="page-stack workspace-page">
    <section class="page-hero workspace-page__hero">
      <div>
        <div class="page-hero__eyebrow">舆情工作台</div>
        <h1 class="page-hero__title">舆情分析</h1>
        <p class="page-hero__subtitle">
          复用现有数据集与文档范围，对已入库文本生成情绪判断、风险倾向与证据摘要。
        </p>
      </div>
    </section>

    <SentimentAnalysis />
  </div>
</template>

<style scoped>
.workspace-page__hero {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}
</style>
