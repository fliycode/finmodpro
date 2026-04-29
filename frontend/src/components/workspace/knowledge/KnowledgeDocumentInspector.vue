<script setup>
defineProps({
  title: {
    type: String,
    default: '文档详情与切块',
  },
  subtitle: {
    type: String,
    default: '状态、版本、切块与原文入口保持在同一侧栏内。',
  },
});
</script>

<template>
  <section class="knowledge-document-inspector">
    <header class="knowledge-document-inspector__header">
      <p class="knowledge-document-inspector__eyebrow">Inspector</p>
      <h2>{{ title }}</h2>
      <p>{{ subtitle }}</p>
    </header>
    <div class="knowledge-document-inspector__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.knowledge-document-inspector {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 22px;
  background: rgba(248, 241, 229, 0.94);
  box-shadow: 0 18px 52px -40px rgba(80, 54, 20, 0.26);
  overflow: hidden;
}

.knowledge-document-inspector__header {
  padding: 20px 20px 16px;
  border-bottom: 1px solid rgba(95, 69, 35, 0.12);
}

.knowledge-document-inspector__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.knowledge-document-inspector h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.15;
  color: #2f2418;
}

.knowledge-document-inspector p {
  margin: 8px 0 0;
  color: #6f5a42;
  line-height: 1.6;
}

.knowledge-document-inspector__body {
  flex: 1;
  min-height: 0;
  padding: 18px;
}
</style>
