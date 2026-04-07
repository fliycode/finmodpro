<script setup>
import KnowledgeBase from '../../components/KnowledgeBase.vue';
</script>

<template>
  <div class="page-stack workspace-page">
    <section class="page-hero workspace-page__hero">
      <div>
        <div class="page-hero__eyebrow">知识工作台</div>
        <h1 class="page-hero__title">知识检索与文档管理</h1>
        <p class="page-hero__subtitle">
          面向文档入库、状态跟踪和明细核查，优先突出检索效率与知识资产质量。
        </p>
      </div>
    </section>

    <KnowledgeBase />
  </div>
</template>

<style scoped>
.workspace-page__hero {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}
</style>
