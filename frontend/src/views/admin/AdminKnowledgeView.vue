<script setup>
import KnowledgeBase from '../../components/KnowledgeBase.vue';
</script>

<template>
  <section class="admin-knowledge-page">
    <KnowledgeBase show-admin-metrics />
  </section>
</template>

<style scoped>
.admin-knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
